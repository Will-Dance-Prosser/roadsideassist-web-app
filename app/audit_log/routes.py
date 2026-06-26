from flask import Blueprint, render_template, request
from app.auth.decorators import role_required
from app.models import AuditLog, User

audit_log_bp = Blueprint("audit_log", __name__)

PAGE_SIZE = 20


@audit_log_bp.route("/audit-log", methods=["GET"])
@role_required("administrator")
def index():
    q           = request.args.get("q", "").strip()[:200]
    user_id     = request.args.get("user_id", type=int)
    action      = request.args.get("action", "").strip()
    target_type = request.args.get("target_type", "").strip()
    sort        = request.args.get("sort", "created_desc")
    page        = max(1, request.args.get("page", 1, type=int))

    query = AuditLog.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            AuditLog.action.ilike(like)
            | AuditLog.target_type.ilike(like)
            | AuditLog.detail.ilike(like)
        )
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)

    if sort == "created_asc":
        query = query.order_by(AuditLog.created_at.asc())
    else:
        query = query.order_by(AuditLog.created_at.desc())

    pagination = query.paginate(page=page, per_page=PAGE_SIZE, error_out=False)

    # Populate filter dropdowns from distinct values already in the table
    users        = User.query.order_by(User.username).all()
    actions      = [r[0] for r in AuditLog.query.with_entities(AuditLog.action).distinct().order_by(AuditLog.action).all()]
    target_types = [r[0] for r in AuditLog.query.with_entities(AuditLog.target_type).filter(AuditLog.target_type.isnot(None)).distinct().order_by(AuditLog.target_type).all()]

    return render_template(
        "audit_log/index.html",
        pagination=pagination,
        entries=pagination.items,
        q=q,
        user_id=user_id,
        action=action,
        target_type=target_type,
        sort=sort,
        users=users,
        actions=actions,
        target_types=target_types,
    )
