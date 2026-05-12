from flask import Blueprint, render_template, abort
from flask_login import login_required
from app.auth.decorators import role_required
from app.extensions import db
from app.models import MatchCandidate


match_queue_bp = Blueprint("match_queue", __name__)


@match_queue_bp.route("/match-queue", methods=["GET"])
@login_required
@role_required("administrator", "data_steward", "data_analyst")
def index():
    # lists the pending match candidates by match score descending
    candidates = (MatchCandidate.query.filter_by(status="pending").order_by(MatchCandidate.match_score.desc()).all())
    return render_template("match_queue/index.html", candidates=candidates)


@match_queue_bp.route("/match-candidates/<int:id>", methods=["GET"])
@login_required
@role_required("administrator", "data_steward", "data_analyst")
def detail(id):
    """Show full details of a single match candidate."""
    candidate = db.session.get(MatchCandidate, id)
    if candidate is None:
        abort(404)
    return render_template("match_queue/detail.html", candidate=candidate)