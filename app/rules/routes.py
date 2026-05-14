from flask import Blueprint, render_template
from flask_login import login_required
from app.auth.decorators import role_required
from app.models import MatchRule

rules_bp = Blueprint("rules", __name__, template_folder="../templates")


@rules_bp.route("/rules", methods=["GET"])
@login_required
@role_required("administrator")
def index():
    """List all match rules ordered by field name."""
    rules = MatchRule.query.order_by(MatchRule.field_name).all()
    return render_template("rules/index.html", rules=rules)
