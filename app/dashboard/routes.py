from flask import Blueprint, render_template
from flask_login import login_required

from app.extensions import db
from app.models import AuditLog, GoldenRecord, MatchCandidate, SourceRecord

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
@login_required
def index():
    stats = {
        "source_records":   SourceRecord.query.filter_by(is_archived=False).count(),
        "pending_review":   MatchCandidate.query.filter_by(status="pending").count(),
        "golden_records":   GoldenRecord.query.count(),
        "archived_records": SourceRecord.query.filter_by(is_archived=True).count(),
    }
    recent_activity = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(5).all()
    return render_template("dashboard/index.html", stats=stats, recent_activity=recent_activity)