from flask import Blueprint, render_template
from flask_login import login_required
from app.auth.decorators import role_required

rules_bp = Blueprint("rules", __name__, template_folder="../templates")


@rules_bp.route("/rules", methods=["GET"]) # returns rules page if user is logged in and matches the admin role
@role_required("administrator")
@login_required
def index():
    return render_template("rules/index.html")
