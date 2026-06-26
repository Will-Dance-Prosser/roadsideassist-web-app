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
@role_required("data_steward")
def approve(id):
    candidate = db.session.get(MatchCandidate, id)
    if candidate is None:
        abort(404)

    if candidate.status != "pending":
        flash("This candidate has already been reviewed and cannot be changed.", "warning")
        return redirect(url_for("match_queue.detail", id=id))

    primary = request.form.get("primary_record", "a")
    if primary not in ("a", "b"):
        flash("Invalid primary record selection.", "danger")
        return redirect(url_for("match_queue.detail", id=id))
    if primary == "b":
        base, other = candidate.record_b, candidate.record_a
    else:
        base, other = candidate.record_a, candidate.record_b

    MERGE_FIELDS = ("first_name", "last_name", "email", "date_of_birth", "postcode", "phone")

    now = datetime.utcnow()

    decision = MergeDecision(
        candidate_id=candidate.id,
        decided_by_id=current_user.id,
        decision="approved",
    )
    db.session.add(decision)

    # Check if either source record is already linked to a golden record
    base_link = GoldenRecordLink.query.filter_by(source_record_id=base.id).first()
    other_link = GoldenRecordLink.query.filter_by(source_record_id=other.id).first()

    if base_link and other_link:
        # Both already have golden records — merge the secondary into the primary's golden record
        primary_golden = base_link.golden_record
        secondary_golden = other_link.golden_record

        if primary_golden.id != secondary_golden.id:
            # Fill any missing fields on the primary golden record from the secondary
            for field in MERGE_FIELDS:
                if not getattr(primary_golden, field):
                    setattr(primary_golden, field, getattr(secondary_golden, field))

            # Re-link all source records from the secondary golden record to the primary
            for link in secondary_golden.source_links:
                if not GoldenRecordLink.query.filter_by(
                    golden_record_id=primary_golden.id,
                    source_record_id=link.source_record_id,
                ).first():
                    link.golden_record_id = primary_golden.id
                else:
                    db.session.delete(link)

            db.session.flush()
            db.session.delete(secondary_golden)

        golden = primary_golden
        outcome = f"merged into existing golden record GR-{golden.id:04d}"

    elif base_link:
        # Base already has a golden record — add the other source record to it
        golden = base_link.golden_record
        for field in MERGE_FIELDS:
            if not getattr(golden, field):
                setattr(golden, field, getattr(other, field))
        if not GoldenRecordLink.query.filter_by(
            golden_record_id=golden.id, source_record_id=other.id
        ).first():
            db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=other.id))
        outcome = f"added to existing golden record GR-{golden.id:04d}"

    elif other_link:
        # Other already has a golden record — add the base source record to it
        golden = other_link.golden_record
        for field in MERGE_FIELDS:
            if not getattr(golden, field):
                setattr(golden, field, getattr(base, field))
        if not GoldenRecordLink.query.filter_by(
            golden_record_id=golden.id, source_record_id=base.id
        ).first():
            db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=base.id))
        outcome = f"added to existing golden record GR-{golden.id:04d}"

    else:
        # Neither is linked — create a new golden record
        golden = GoldenRecord(**{
            field: getattr(base, field) or getattr(other, field)
            for field in MERGE_FIELDS
        })
        db.session.add(golden)
        db.session.flush()
        db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=candidate.record_a_id))
        db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=candidate.record_b_id))
        outcome = f"new golden record GR-{golden.id:04d} created"

    db.session.add(AuditLog(
        user_id=current_user.id,
        action="match_approved",
        target_type="match_candidate",
        target_id=candidate.id,
        detail=f"Candidate MC-{candidate.id:04d} approved by {current_user.username} — primary: {base.external_id}, {outcome}",
    ))

    candidate.status = "approved"
    candidate.reviewed_at = now
    candidate.reviewed_by_id = current_user.id

    db.session.commit()
    flash(f"Match candidate MC-{candidate.id:04d} approved. {outcome.capitalize()}.", "success")

    return redirect(url_for("match_queue.index"))


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
    return redirect(url_for("match_queue.index"))


@match_queue_bp.route("/match-candidates/<int:id>/reopen", methods=["POST"])
@role_required("data_steward")
def reopen(id):
    # Return a rejected candidate to the pending review queue
    candidate = db.session.get(MatchCandidate, id)
    if candidate is None:
        abort(404)

    if candidate.status == "pending":
        flash("This candidate is already pending review.", "info")
        return redirect(url_for("match_queue.detail", id=id))

    if candidate.status == "approved":
        # Approved candidates own a golden record. Revoking the approval safely
        # requires deleting that golden record, which is done from the golden
        # record screen (that flow already reopens its candidates).
        flash(
            "Approved matches cannot be reopened here. Delete the linked golden record "
            "from the Golden Records screen to reopen the candidate for review.",
            "warning",
        )
        return redirect(url_for("match_queue.detail", id=id))

    previous_status = candidate.status
    candidate.status = "pending"
    candidate.reviewed_at = None
    candidate.reviewed_by_id = None

    db.session.add(AuditLog(
        user_id=current_user.id,
        action="match_reopened",
        target_type="match_candidate",
        target_id=candidate.id,
        detail=(
            f"Candidate MC-{candidate.id:04d} reopened by {current_user.username} "
            f"(previous status: {previous_status})."
        ),
    ))

    db.session.commit()
    flash(f"Match candidate MC-{candidate.id:04d} reopened for review.", "success")
    return redirect(url_for("match_queue.index"))