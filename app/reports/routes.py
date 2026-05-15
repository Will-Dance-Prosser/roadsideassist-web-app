from flask import Blueprint, render_template
from app.auth.decorators import role_required
from app.models import AuditLog, GoldenRecord, MatchCandidate, SourceRecord, SourceSystem

reports_bp = Blueprint("reports", __name__)

ALLOWED_ROLES = ("administrator", "data_steward", "data_analyst")


@reports_bp.route("/reports", methods=["GET"])
@role_required(*ALLOWED_ROLES)
def index():
    # Builds summary stats for the reports page

    # Match Outcomes
    match_outcomes = {
        "pending":  MatchCandidate.query.filter_by(status="pending").count(),
        "approved": MatchCandidate.query.filter_by(status="approved").count(),
        "rejected": MatchCandidate.query.filter_by(status="rejected").count(),
    }

    # Data Quality
    data_quality = {
        "active_records":   SourceRecord.query.filter_by(is_archived=False).count(),
        "archived_records": SourceRecord.query.filter_by(is_archived=True).count(),
        "golden_records":   GoldenRecord.query.count(),
        "source_systems":   SourceSystem.query.count(),
    }

    # Stewardship Activity — latest 10 approve/reject audit entries - 10 feels enough for now
    stewardship = (
        AuditLog.query.filter(AuditLog.action.in_(["match_approved", "match_rejected"])).order_by(AuditLog.created_at.desc()).limit(10).all()
    )

    return render_template(
        "reports/index.html",
        match_outcomes=match_outcomes,
        data_quality=data_quality,
        stewardship=stewardship,
    )
