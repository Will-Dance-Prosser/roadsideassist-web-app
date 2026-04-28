from flask import Blueprint, render_template

dashboard_bp = Blueprint("dashboard", __name__)



#temp dashboard page to test succesful Flask app
@dashboard_bp.route("/")
def index():

    return render_template("dashboard/index.html")