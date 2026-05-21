from datetime import datetime
from flask import Blueprint, render_template, abort, redirect, url_for, flash, request
from flask_login import current_user
from app.auth.decorators import role_required
from app.extensions import db
from app.models import AuditLog, GoldenRecord, GoldenRecordLink, MatchCandidate, MergeDecision
from app.match_queue.explain import build_explanation


match_queue_bp = Blueprint("match_queue", __name__)



@match_queue_bp.route("/match-queue", methods=["GET"])
@role_required("administrator", "data_steward", "data_analyst")
def index():
    # lists the pending match candidates by match score descending
    candidates = (MatchCandidate.query.filter_by(status="pending").order_by(MatchCandidate.match_score.desc()).all())
    return render_template("match_queue/index.html", candidates=candidates)



@match_queue_bp.route("/match-candidates/<int:id>", methods=["GET"])
@role_required("administrator", "data_steward", "data_analyst")
def detail(id):
    # Show full details of a single match candidate
    candidate = db.session.get(MatchCandidate, id)
    if candidate is None:
        abort(404)
    explanation = build_explanation(candidate)

    # Other candidates that share either source record — helps spot clusters
    related = MatchCandidate.query.filter(
        MatchCandidate.id != id,
        (MatchCandidate.record_a_id == candidate.record_a_id)
        | (MatchCandidate.record_b_id == candidate.record_a_id)
        | (MatchCandidate.record_a_id == candidate.record_b_id)
        | (MatchCandidate.record_b_id == candidate.record_b_id),
    ).order_by(MatchCandidate.match_score.desc()).all()

    return render_template("match_queue/detail.html", candidate=candidate, explanation=explanation, related=related)



@match_queue_bp.route("/match-candidates/<int:id>/approve", methods=["POST"])
@role_required("data_steward")  # only data_steward can approve
def approve(id):
    candidate = db.session.get(MatchCandidate, id)
    if candidate is None:
        abort(404)

    if candidate.status != "pending":
        flash("This candidate has already been reviewed and cannot be changed.", "warning")
        return redirect(url_for("match_queue.detail", id=id))

    # Steward picks which record is the primary (base) for the golden record
    primary = request.form.get("primary_record", "a")
    if primary == "b":
        base, other = candidate.record_b, candidate.record_a
    else:
        base, other = candidate.record_a, candidate.record_b

    # Fields defined on GoldenRecord — fill from base, fall back to other where base is missing
    MERGE_FIELDS = ("first_name", "last_name", "email", "date_of_birth", "postcode", "phone")

    now = datetime.utcnow()

    decision = MergeDecision(
        candidate_id=candidate.id,
        decided_by_id=current_user.id,
        decision="approved",
    )
    db.session.add(decision)

    golden = GoldenRecord(**{
        field: getattr(base, field) or getattr(other, field)
        for field in MERGE_FIELDS
    })
    db.session.add(golden)
    db.session.flush()

    link_a = GoldenRecordLink(golden_record_id=golden.id, source_record_id=candidate.record_a_id)
    link_b = GoldenRecordLink(golden_record_id=golden.id, source_record_id=candidate.record_b_id)
    db.session.add(link_a)
    db.session.add(link_b)

    db.session.add(AuditLog(
        user_id=current_user.id,
        action="match_approved",
        target_type="match_candidate",
        target_id=candidate.id,
        detail=f"Candidate MC-{candidate.id:04d} approved by {current_user.username} — primary record: {base.external_id}",
    ))

    candidate.status = "approved"
    candidate.reviewed_at = now
    candidate.reviewed_by_id = current_user.id

    db.session.commit()
    flash(f"Match candidate MC-{candidate.id:04d} approved. Golden record created from {base.external_id}.", "success")
    return redirect(url_for("match_queue.detail", id=id))


@match_queue_bp.route("/match-candidates/<int:id>/reject", methods=["POST"])
@role_required("data_steward")  # only data_steward can reject
def reject(id):
    # Reject a pending match candidate
    candidate = db.session.get(MatchCandidate, id)
    if candidate is None:
        abort(404)

    if candidate.status != "pending":
        flash("This candidate has already been reviewed and cannot be changed.", "warning")
        return redirect(url_for("match_queue.detail", id=id))

    now = datetime.utcnow()

    # Create merge decision
    decision = MergeDecision(
        candidate_id=candidate.id,
        decided_by_id=current_user.id,
        decision="rejected",
    )
    db.session.add(decision)

    # Audit log
    db.session.add(AuditLog(
        user_id=current_user.id,
        action="match_rejected",
        target_type="match_candidate",
        target_id=candidate.id,
        detail=f"Candidate MC-{candidate.id:04d} rejected by {current_user.username}",
    ))

    # Update candidate
    candidate.status = "rejected"
    candidate.reviewed_at = now
    candidate.reviewed_by_id = current_user.id

    db.session.commit()
    flash(f"Match candidate MC-{candidate.id:04d} rejected.", "success")
    return redirect(url_for("match_queue.detail", id=id))