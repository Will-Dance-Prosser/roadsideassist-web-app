from datetime import datetime
from flask import Blueprint, render_template, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from app.auth.decorators import role_required
from app.extensions import db
from app.models import AuditLog, GoldenRecord, GoldenRecordLink, MatchCandidate, MergeDecision
from app.match_queue.explain import build_explanation


match_queue_bp = Blueprint("match_queue", __name__)

#Decorators run bottom up closest to function, swapped order.

@match_queue_bp.route("/match-queue", methods=["GET"])
@login_required # make sure logged in
@role_required("administrator", "data_steward", "data_analyst")
def index():
    # lists the pending match candidates by match score descending
    candidates = (MatchCandidate.query.filter_by(status="pending").order_by(MatchCandidate.match_score.desc()).all())
    return render_template("match_queue/index.html", candidates=candidates)



@match_queue_bp.route("/match-candidates/<int:id>", methods=["GET"])
@login_required
@role_required("administrator", "data_steward", "data_analyst")
def detail(id):
    """Show full details of a single match candidate."""
    candidate = db.session.get(MatchCandidate, id)
    if candidate is None:
        abort(404)
    explanation = build_explanation(candidate)
    return render_template("match_queue/detail.html", candidate=candidate, explanation=explanation)



@match_queue_bp.route("/match-candidates/<int:id>/approve", methods=["POST"])
@login_required
@role_required("data_steward")  # only data_steward can approve
def approve(id): # approve and create golden record
    
    #prechecks
    candidate = db.session.get(MatchCandidate, id)
    if candidate is None:
        abort(404)

    if candidate.status != "pending":
        flash("This candidate has already been reviewed and cannot be changed.", "warning")
        return redirect(url_for("match_queue.detail", id=id))

    now = datetime.utcnow() # get current time for audit/history


    # Create merge decision
    decision = MergeDecision(
        candidate_id=candidate.id,
        decided_by_id=current_user.id,
        decision="approved",
    )
    db.session.add(decision)

    # Create golden record from record_a as the base
    rec_a = candidate.record_a
    golden = GoldenRecord(
        first_name=rec_a.first_name,
        last_name=rec_a.last_name,
        email=rec_a.email,
        date_of_birth=rec_a.date_of_birth,
        postcode=rec_a.postcode,
        phone=rec_a.phone,
    )
    db.session.add(golden)
    db.session.flush()  # get golden.id before linking

    # Link both source records to the golden record
    db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=candidate.record_a_id))
    db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=candidate.record_b_id))

    # Audit log
    db.session.add(AuditLog(
        user_id=current_user.id,
        action="match_approved",
        target_type="match_candidate",
        target_id=candidate.id,
        detail=f"Candidate MC-{candidate.id:04d} approved by {current_user.username}",
    ))

    # Update candidate last - ensure no updates without auditing
    candidate.status = "approved"
    candidate.reviewed_at = now
    candidate.reviewed_by_id = current_user.id

    db.session.commit()
    flash(f"Match candidate MC-{candidate.id:04d} approved. Golden record created.", "success")
    return redirect(url_for("match_queue.detail", id=id))


@match_queue_bp.route("/match-candidates/<int:id>/reject", methods=["POST"])
@login_required
@role_required("data_steward")  # only data_steward can reject
def reject(id):
    """Reject a pending match candidate."""
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