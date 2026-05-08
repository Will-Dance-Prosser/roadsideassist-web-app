from flask import Blueprint, render_template
from flask_login import login_required
from app.auth.decorators import role_required
from app.models import MatchCandidate


match_queue_bp = Blueprint("match_queue", __name__)


@match_queue_bp.route("/match-queue", methods=["GET"])
@login_required
@role_required("administrator", "data_steward", "data_analyst")

def index():
    # lists the pending match candidates by match score decesding
    candidates = (MatchCandidate.query.filter_by(status="pending").order_by(MatchCandidate.match_score.desc()).all())

    return render_template("match_queue/index.html", candidates=candidates)