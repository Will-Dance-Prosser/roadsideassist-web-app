from flask import Blueprint, render_template, abort
from flask_login import login_required
from app.auth.decorators import role_required
from app.models import GoldenRecord

golden_records_bp = Blueprint("golden_records", __name__)


@golden_records_bp.route("/golden-records", methods=["GET"])
@login_required
@role_required("administrator", "data_steward", "data_analyst")
def index(): #List all golden records ordered by most recently created.
    records = GoldenRecord.query.order_by(GoldenRecord.created_at.desc()).all()
    return render_template("golden_records/index.html", records=records)


@golden_records_bp.route("/golden-records/<int:id>", methods=["GET"])
@login_required
@role_required("administrator", "data_steward", "data_analyst")
def detail(id):
    """Show the detail page for a single golden record."""
    record = GoldenRecord.query.get_or_404(id)
    return render_template("golden_records/detail.html", record=record)
