from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import current_user
from app.auth.decorators import role_required
from app.extensions import db
from app.models import AuditLog, GoldenRecordLink, MatchCandidate, SourceRecord, SourceSystem
from app.source_records.forms import SourceRecordForm

source_records_bp = Blueprint("source_records", __name__)


def _populate_system_choices(form):
    # Fill the source system dropdown - called before every GET and failed POST
    form.source_system_id.choices = [
        (s.id, s.name) for s in SourceSystem.query.order_by(SourceSystem.name).all()
    ]


@source_records_bp.route("/source-records", methods=["GET"])
@role_required("administrator", "data_steward", "data_analyst")
def index():
    status = request.args.get("status", "active")
    source_system_id = request.args.get("source_system_id", type=int)

    q = SourceRecord.query
    if status == "archived":
        q = q.filter_by(is_archived=True)
    elif status == "all":
        pass  # no filter
    else:
        # default: active only
        status = "active"
        q = q.filter_by(is_archived=False)

    # Source system filter — silently ignore invalid/missing values
    systems = SourceSystem.query.order_by(SourceSystem.name).all()
    valid_ids = {s.id for s in systems}
    if source_system_id not in valid_ids:
        source_system_id = None
    if source_system_id:
        q = q.filter_by(source_system_id=source_system_id)

    records = q.order_by(SourceRecord.created_at.desc()).all()
    return render_template(
        "source_records/index.html",
        records=records,
        status=status,
        systems=systems,
        source_system_id=source_system_id,
    )


@source_records_bp.route("/source-records/new", methods=["GET", "POST"])
@role_required("administrator", "data_steward")
def create():
    # Handle new source record form - GET shows blank form, POST validates and saves
    form = SourceRecordForm()
    _populate_system_choices(form)

    if form.validate_on_submit():
        # Duplicate check: same system + same external_id
        duplicate = SourceRecord.query.filter_by(
            source_system_id=form.source_system_id.data,
            external_id=form.external_id.data,
        ).first()
        if duplicate:
            flash("A record with that External ID already exists in this Source System.", "warning")
            return render_template("source_records/form.html", form=form, title="New Source Record")

        record = SourceRecord(
            source_system_id=form.source_system_id.data,
            external_id=form.external_id.data,
            first_name=form.first_name.data or None,   # store None instead of empty string
            last_name=form.last_name.data or None,
            email=form.email.data or None,
            date_of_birth=form.date_of_birth.data or None,
            postcode=form.postcode.data or None,
            phone=form.phone.data or None,
            raw_data=form.raw_data.data or None,
        )
        db.session.add(record)
        db.session.commit()
        from app.services.match_scoring import generate_candidates_for_source_record
        generate_candidates_for_source_record(record, triggered_by="source_record_created")
        db.session.add(AuditLog(
            user_id=current_user.id,
            action="source_record_created",
            target_type="source_record",
            target_id=record.id,
            detail=f"Source record {record.external_id} created in {record.source_system.name} by {current_user.username}",
        ))
        db.session.commit()
        flash(f"Source record {record.external_id} created successfully.", "success")
        return redirect(url_for("source_records.index"))

    return render_template("source_records/form.html", form=form, title="New Source Record")


@source_records_bp.route("/source-records/<int:id>", methods=["GET"])
@role_required("administrator", "data_steward", "data_analyst")
def detail(id):
    # Read-only view - no editing from here
    record = db.session.get(SourceRecord, id)
    if record is None:
        abort(404)

    # Pre-calculate delete eligibility so the template can show a clear blocked/safe state
    match_links = []
    golden_links = []
    if record.is_archived and current_user.role == "administrator":
        match_links = MatchCandidate.query.filter(
            (MatchCandidate.record_a_id == id) | (MatchCandidate.record_b_id == id)
        ).all()
        golden_links = GoldenRecordLink.query.filter_by(source_record_id=id).all()

    can_delete = record.is_archived and len(match_links) == 0 and len(golden_links) == 0

    return render_template(
        "source_records/detail.html",
        record=record,
        match_link_count=len(match_links),
        golden_link_count=len(golden_links),
        match_links=match_links,
        golden_links=golden_links,
        can_delete=can_delete,
    )


@source_records_bp.route("/source-records/<int:id>/edit", methods=["GET", "POST"])
@role_required("administrator", "data_steward")
def edit(id):
    # Edit an existing source record
    record = db.session.get(SourceRecord, id)
    if record is None:
        abort(404)
    if record.is_archived:
        flash("Archived records cannot be edited. Restore the record first.", "warning")
        return redirect(url_for("source_records.detail", id=id))

    form = SourceRecordForm(obj=record)
    _populate_system_choices(form)

    if form.validate_on_submit():
        # Duplicate check: same system + external_id, but not this record itself
        # using .filter() not .filter_by() because we need the != condition
        duplicate = SourceRecord.query.filter(
            SourceRecord.source_system_id == form.source_system_id.data,
            SourceRecord.external_id == form.external_id.data,
            SourceRecord.id != id,
        ).first()
        if duplicate:
            flash("Another record with that External ID already exists in this Source System.", "warning")
            return render_template("source_records/form.html", form=form, title="Edit Source Record", record=record)

        # Track which fields changed before committing
        TRACKED = ("source_system_id", "external_id", "first_name", "last_name",
                   "email", "date_of_birth", "postcode", "phone")
        changes = [
            f"{field}: {getattr(record, field)!r} -> {getattr(form, field).data!r}"
            for field in TRACKED
            if str(getattr(record, field) or "") != str(getattr(form, field).data or "")
        ]

        record.source_system_id = form.source_system_id.data
        record.external_id = form.external_id.data
        record.first_name = form.first_name.data or None
        record.last_name = form.last_name.data or None
        record.email = form.email.data or None
        record.date_of_birth = form.date_of_birth.data or None
        record.postcode = form.postcode.data or None
        record.phone = form.phone.data or None
        record.raw_data = form.raw_data.data or None
        db.session.commit()
        from app.services.match_scoring import generate_candidates_for_source_record
        generate_candidates_for_source_record(record, triggered_by="source_record_edited")
        change_summary = "; ".join(changes) if changes else "no field changes detected"
        db.session.add(AuditLog(
            user_id=current_user.id,
            action="source_record_updated",
            target_type="source_record",
            target_id=record.id,
            detail=f"Source record {record.external_id} updated by {current_user.username}: {change_summary}",
        ))
        db.session.commit()
        flash(f"Source record {record.external_id} updated successfully.", "success")
        return redirect(url_for("source_records.index"))

    return render_template("source_records/form.html", form=form, title="Edit Source Record", record=record)


@source_records_bp.route("/source-records/<int:id>/archive", methods=["POST"])
@role_required("administrator", "data_steward")
def archive(id):
    # Soft delete - sets is_archived flag rather than removing the row
    record = db.session.get(SourceRecord, id)
    if record is None:
        abort(404)
    if record.is_archived:
        flash("Record is already archived.", "warning")
    else:
        record.is_archived = True
        record.archived_at = datetime.utcnow()
        db.session.add(AuditLog(
            user_id=current_user.id,
            action="source_record_archived",
            target_type="source_record",
            target_id=record.id,
            detail=f"Source record {record.external_id} archived by {current_user.username}",
        ))
        db.session.commit()
        flash(f"Source record {record.external_id} archived.", "success")
    return redirect(url_for("source_records.index"))


@source_records_bp.route("/source-records/<int:id>/unarchive", methods=["POST"])
@role_required("administrator")
def unarchive(id):
    # Restore a soft-deleted record - administrator only
    record = db.session.get(SourceRecord, id)
    if record is None:
        abort(404)
    if not record.is_archived:
        flash("Record is not archived.", "warning")
    else:
        record.is_archived = False
        record.archived_at = None
        db.session.add(AuditLog(
            user_id=current_user.id,
            action="source_record_restored",
            target_type="source_record",
            target_id=record.id,
            detail=f"Source record {record.external_id} restored by {current_user.username}",
        ))
        db.session.commit()
        flash(f"Source record {record.external_id} restored successfully.", "success")
    return redirect(url_for("source_records.index", status="archived"))


@source_records_bp.route("/source-records/<int:id>/delete", methods=["POST"])
@role_required("administrator")
def delete(id):
    # Permanent delete - only allowed for archived, unlinked records
    record = db.session.get(SourceRecord, id)
    if record is None:
        abort(404)

    if not record.is_archived:
        flash("Only archived records can be permanently deleted.", "danger")
        return redirect(url_for("source_records.detail", id=id))

    confirmation = request.form.get("confirmation", "").strip()
    if confirmation != "DELETE":
        flash("Type DELETE exactly to confirm permanent deletion.", "warning")
        return redirect(url_for("source_records.detail", id=id))

    # Block if the record is referenced in match or golden record history
    in_match = MatchCandidate.query.filter(
        (MatchCandidate.record_a_id == id) | (MatchCandidate.record_b_id == id)
    ).first()
    in_golden = GoldenRecordLink.query.filter_by(source_record_id=id).first()
    if in_match or in_golden:
        flash(
            f"Source record {record.external_id} is part of match or golden record history and cannot be deleted.",
            "danger",
        )
        return redirect(url_for("source_records.detail", id=id))

    # Audit before deleting
    db.session.add(AuditLog(
        user_id=current_user.id,
        action="source_record_deleted",
        target_type="source_record",
        target_id=record.id,
        detail=f"Source record {record.external_id} permanently deleted by {current_user.username}",
    ))
    db.session.delete(record)
    db.session.commit()
    flash(f"Source record {record.external_id} permanently deleted.", "success")
    return redirect(url_for("source_records.index", status="archived"))

