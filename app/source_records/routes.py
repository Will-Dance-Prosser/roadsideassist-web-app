from flask import Blueprint, render_template
from flask_login import login_required
from app.auth.decorators import role_required
from app.models import SourceRecord

source_records_bp = Blueprint("source_records", __name__)


@source_records_bp.route("/source-records", methods=["GET"])
@login_required
@role_required("administrator", "data_steward", "data_analyst")
def index():
    """List all source records ordered by most recently created."""
    records = SourceRecord.query.order_by(SourceRecord.created_at.desc()).all()
    return render_template("source_records/index.html", records=records)
