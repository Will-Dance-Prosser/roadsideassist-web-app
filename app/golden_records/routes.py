from flask import Blueprint, render_template, abort, redirect, url_for, flash, request
from flask_login import current_user
from app.auth.decorators import role_required
from app.extensions import db
from app.models import AuditLog, GoldenRecord, GoldenRecordLink, MatchCandidate

golden_records_bp = Blueprint("golden_records", __name__)

ALLOWED_ROLES = ("administrator", "data_steward", "data_analyst")


@golden_records_bp.route("/golden-records", methods=["GET"])
@role_required(*ALLOWED_ROLES)
def index():
    # List all golden records ordered by most recently created
    records = GoldenRecord.query.order_by(GoldenRecord.created_at.desc()).all()
    return render_template("golden_records/index.html", records=records)


@golden_records_bp.route("/golden-records/<int:id>", methods=["GET"])
@role_required(*ALLOWED_ROLES)
def detail(id):
    # Show detail page for a specific golden record
    record = GoldenRecord.query.get_or_404(id)
    return render_template("golden_records/detail.html", record=record)


@golden_records_bp.route("/golden-records/<int:id>/delete", methods=["POST"])
@role_required("administrator")
def delete(id):
    # Permanently delete a golden record - removes consolidated view only
    record = GoldenRecord.query.get_or_404(id)

    confirmation = request.form.get("confirmation", "").strip()
    if confirmation != "DELETE":
        flash("Type DELETE exactly to confirm permanent deletion.", "warning")
        return redirect(url_for("golden_records.detail", id=id))

    # Collect linked source record IDs before removing the links
    linked_ids = [
        link.source_record_id
        for link in GoldenRecordLink.query.filter_by(golden_record_id=id).all()
    ]

    # Reopen approved candidates that paired any two of these source records
    reopened = []
    if len(linked_ids) >= 2:
        candidates = MatchCandidate.query.filter(
            MatchCandidate.status == "approved",
            MatchCandidate.record_a_id.in_(linked_ids),
            MatchCandidate.record_b_id.in_(linked_ids),
        ).all()
        for candidate in candidates:
            candidate.status = "pending"
            candidate.reviewed_at = None
            candidate.reviewed_by_id = None
            reopened.append(candidate.id)

    reopen_note = ""
    if reopened:
        ids_str = ", ".join(f"MC-{cid:04d}" for cid in reopened)
        reopen_note = f" Reopened candidate(s) for review: {ids_str}."

    # Audit before deleting
    db.session.add(AuditLog(
        user_id=current_user.id,
        action="golden_record_deleted",
        target_type="golden_record",
        target_id=record.id,
        detail=(
            f"Golden record GR-{record.id:04d} permanently deleted by {current_user.username}."
            f" Linked source records retained.{reopen_note}"
        ),
    ))

    # Remove links then the golden record itself; source records are left intact
    GoldenRecordLink.query.filter_by(golden_record_id=id).delete()
    db.session.delete(record)
    db.session.commit()

    flash(f"Golden record GR-{id:04d} permanently deleted.", "success")
    return redirect(url_for("golden_records.index"))
