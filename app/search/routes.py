import re

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import GoldenRecord, MatchCandidate, SourceRecord

search_bp = Blueprint("search", __name__)


def _parse_candidate_id(q):
    # Return an integer candidate ID if q looks like 1, 0001 or MC-0001, else None
    q = q.strip()
    # MC-0001 or mc-0001
    m = re.fullmatch(r"(?i)mc-?(\d+)", q)
    if m:
        return int(m.group(1))
    # plain digits
    if re.fullmatch(r"\d+", q):
        return int(q)
    return None


@search_bp.route("/search", methods=["GET"])
@login_required
def index():
    # Handle the global search — searches source records, match candidates, and golden records
    q = request.args.get("q", "").strip()

    if not q:
        # nothing typed yet, just show the empty search page
        return render_template(
            "search/index.html",
            q=q,
            empty=True,
            source_records=[],
            match_candidates=[],
            golden_records=[],
        )

    ilike_pattern = f"%{q}%"  # wrap in wildcards for SQL ILIKE matching

    # Source Records -- search across name, email, postcode, phone and external ID
    # db.false() is just a clean way to start the OR chain
    source_records = SourceRecord.query.filter(
        db.false() |
        SourceRecord.external_id.ilike(ilike_pattern) |
        SourceRecord.first_name.ilike(ilike_pattern) |
        SourceRecord.last_name.ilike(ilike_pattern) |
        SourceRecord.email.ilike(ilike_pattern) |
        SourceRecord.postcode.ilike(ilike_pattern) |
        SourceRecord.phone.ilike(ilike_pattern)
    ).order_by(SourceRecord.last_name, SourceRecord.first_name).limit(50).all()  # 50 should be plenty

    # Match Candidates -- only match by ID since there's no name/email on candidates
    candidate_id = _parse_candidate_id(q)
    if candidate_id is not None:
        match_candidates = MatchCandidate.query.filter_by(id=candidate_id).all()
    else:
        match_candidates = []

    # Golden Records -- same fields as source records minus external_id
    golden_records = GoldenRecord.query.filter(
        db.false() |
        GoldenRecord.first_name.ilike(ilike_pattern) |
        GoldenRecord.last_name.ilike(ilike_pattern) |
        GoldenRecord.email.ilike(ilike_pattern) |
        GoldenRecord.postcode.ilike(ilike_pattern) |
        GoldenRecord.phone.ilike(ilike_pattern)
    ).order_by(GoldenRecord.last_name, GoldenRecord.first_name).limit(50).all()

    return render_template(
        "search/index.html",
        q=q,
        empty=False,
        source_records=source_records,
        match_candidates=match_candidates,
        golden_records=golden_records,
    )


# db imported down here to avoid circular import with app.extensions
from app.extensions import db  # noqa: E402
