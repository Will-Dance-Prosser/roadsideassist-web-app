import re

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import GoldenRecord, MatchCandidate, SourceRecord

search_bp = Blueprint("search", __name__)


def _parse_candidate_id(q):
    """Return an integer candidate ID if q looks like 1, 0001 or MC-0001, else None."""
    q = q.strip()
    # MC-0001 or mc-0001
    m = re.fullmatch(r"(?i)mc-?(\d+)", q)
    if m:
        return int(m.group(1))
    # plain digits
    if re.fullmatch(r"\d+", q):
        return int(q)
    return None


@search_bp.route("/search")
@login_required
def index():
    q = request.args.get("q", "").strip()

    if not q:
        return render_template("search/index.html", q=q, empty=True,
                               source_records=[], match_candidates=[], golden_records=[])

    like = f"%{q}%"

    # Source Records -------------------------------------------------------
    source_records = SourceRecord.query.filter(
        db.false() |
        SourceRecord.external_id.ilike(like) |
        SourceRecord.first_name.ilike(like) |
        SourceRecord.last_name.ilike(like) |
        SourceRecord.email.ilike(like) |
        SourceRecord.postcode.ilike(like) |
        SourceRecord.phone.ilike(like)
    ).order_by(SourceRecord.last_name, SourceRecord.first_name).limit(50).all()

    # Match Candidates -----------------------------------------------------
    candidate_id = _parse_candidate_id(q)
    if candidate_id is not None:
        match_candidates = MatchCandidate.query.filter_by(id=candidate_id).all()
    else:
        match_candidates = []

    # Golden Records -------------------------------------------------------
    golden_records = GoldenRecord.query.filter(
        db.false() |
        GoldenRecord.first_name.ilike(like) |
        GoldenRecord.last_name.ilike(like) |
        GoldenRecord.email.ilike(like) |
        GoldenRecord.postcode.ilike(like) |
        GoldenRecord.phone.ilike(like)
    ).order_by(GoldenRecord.last_name, GoldenRecord.first_name).limit(50).all()

    return render_template(
        "search/index.html",
        q=q,
        empty=False,
        source_records=source_records,
        match_candidates=match_candidates,
        golden_records=golden_records,
    )


# db must be imported after blueprint definition to avoid circular imports
from app.extensions import db  # noqa: E402
