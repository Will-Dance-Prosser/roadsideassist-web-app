from flask import Blueprint, render_template
from app.auth.decorators import role_required
from app.models import AuditLog

audit_log_bp = Blueprint("audit_log", __name__)


@audit_log_bp.route("/audit-log", methods=["GET"])
@role_required("administrator")
def index(): #list all log entries in descendign date order   
    entries = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
    return render_template("audit_log/index.html", entries=entries)
