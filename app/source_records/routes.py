from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required
from app.auth.decorators import role_required
from app.extensions import db
from app.models import SourceRecord, SourceSystem
from app.source_records.forms import SourceRecordForm

source_records_bp = Blueprint("source_records", __name__)


def _populate_system_choices(form):
    """Fill the source_system_id dropdown from the database."""
    form.source_system_id.choices = [
        (s.id, s.name) for s in SourceSystem.query.order_by(SourceSystem.name).all()
    ]


@source_records_bp.route("/source-records", methods=["GET"])
@login_required
@role_required("administrator", "data_steward", "data_analyst")
def index():
    """List all source records ordered by most recently created."""
    records = SourceRecord.query.order_by(SourceRecord.created_at.desc()).all()
    return render_template("source_records/index.html", records=records)


@source_records_bp.route("/source-records/new", methods=["GET", "POST"])
@login_required
@role_required("administrator", "data_steward")
def create():
    """Create a new source record."""
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
            first_name=form.first_name.data or None,
            last_name=form.last_name.data or None,
            email=form.email.data or None,
            date_of_birth=form.date_of_birth.data or None,
            postcode=form.postcode.data or None,
            phone=form.phone.data or None,
            raw_data=form.raw_data.data or None,
        )
        db.session.add(record)
        db.session.commit()
        flash(f"Source record {record.external_id} created successfully.", "success")
        return redirect(url_for("source_records.index"))

    return render_template("source_records/form.html", form=form, title="New Source Record")


@source_records_bp.route("/source-records/<int:id>", methods=["GET"])
@login_required
@role_required("administrator", "data_steward", "data_analyst")
def detail(id):
    """Read-only detail view for a source record."""
    record = db.session.get(SourceRecord, id)
    if record is None:
        abort(404)
    return render_template("source_records/detail.html", record=record)


@source_records_bp.route("/source-records/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("administrator", "data_steward")
def edit(id):
    """Edit an existing source record."""
    record = db.session.get(SourceRecord, id)
    if record is None:
        abort(404)

    form = SourceRecordForm(obj=record)
    _populate_system_choices(form)

    if form.validate_on_submit():
        # Duplicate check: same system + external_id, but not this record itself
        duplicate = SourceRecord.query.filter(
            SourceRecord.source_system_id == form.source_system_id.data,
            SourceRecord.external_id == form.external_id.data,
            SourceRecord.id != id,
        ).first()
        if duplicate:
            flash("Another record with that External ID already exists in this Source System.", "warning")
            return render_template("source_records/form.html", form=form, title="Edit Source Record", record=record)

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
        flash(f"Source record {record.external_id} updated successfully.", "success")
        return redirect(url_for("source_records.index"))

    return render_template("source_records/form.html", form=form, title="Edit Source Record", record=record)


@source_records_bp.route("/source-records/<int:id>/archive", methods=["POST"])
@login_required
@role_required("administrator", "data_steward")
def archive(id):
    """Archive a source record (soft delete)."""
    record = db.session.get(SourceRecord, id)
    if record is None:
        abort(404)
    if record.is_archived:
        flash("Record is already archived.", "warning")
    else:
        record.is_archived = True
        record.archived_at = datetime.utcnow()
        db.session.commit()
        flash(f"Source record {record.external_id} archived.", "success")
    return redirect(url_for("source_records.index"))

