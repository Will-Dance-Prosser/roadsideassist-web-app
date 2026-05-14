from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import AuditLog, GoldenRecord, MatchCandidate, SourceRecord

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
@login_required
def index():
    pending_count = MatchCandidate.query.filter_by(status="pending").count()

    # Highest pending match score, expressed as an integer percentage or None
    highest_score_row = (
        db.session.query(func.max(MatchCandidate.match_score))
        .filter(MatchCandidate.status == "pending")
        .scalar()
    )
    highest_score = int(highest_score_row * 100) if highest_score_row is not None else None

    stats = {
        "pending_review":      pending_count,
        "approved_matches":    MatchCandidate.query.filter_by(status="approved").count(),
        "rejected_matches":    MatchCandidate.query.filter_by(status="rejected").count(),
        "golden_records":      GoldenRecord.query.count(),
        "active_records":      SourceRecord.query.filter_by(is_archived=False).count(),
        "archived_records":    SourceRecord.query.filter_by(is_archived=True).count(),
        "highest_score":       highest_score,
    }
    priority_queue = (
        MatchCandidate.query
        .filter_by(status="pending")
        .order_by(MatchCandidate.match_score.desc())
        .limit(5)
        .all()
    )
    # Audit log data is only surfaced to administrators
    user_role = current_user.role
    recent_activity = (
        AuditLog.query.order_by(AuditLog.created_at.desc()).limit(5).all()
        if user_role == "administrator"
        else None
    )
    return render_template(
        "dashboard/index.html",
        stats=stats,
        priority_queue=priority_queue,
        recent_activity=recent_activity,
        user_role=user_role,
    )