"""Match scoring service.

Calculates match scores between two SourceRecord objects using active MatchRules.
Only pending candidates are recalculated; approved/rejected keep historical scores
for auditability.
"""

from difflib import SequenceMatcher

from app.extensions import db
from app.models import AuditLog, MatchCandidate, MatchRule, SourceRecord

# Minimum score for a pair to become a pending match candidate
REVIEW_THRESHOLD = 0.60


def _digits(value):
    """Return only digit characters from a string, normalising UK numbers.

    Converts local UK format (07...) to international (447...) so that
    '07700 900004' and '+447700900004' produce the same digit string.
    """
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    # UK local mobile/landline → international: 07... → 447...
    if digits.startswith("0") and len(digits) == 11:
        digits = "44" + digits[1:]
    return digits


def _normalise(value):
    """Strip, uppercase and remove spaces."""
    if not value:
        return None
    return str(value).strip().upper().replace(" ", "")


def _compare_field(rule, record_a, record_b):
    """Apply one rule to two records. Returns True if the field comparison passes."""
    a_val = getattr(record_a, rule.field_name, None)
    b_val = getattr(record_b, rule.field_name, None)
    if a_val is None or b_val is None:
        return False

    if rule.match_method == "exact":
        return str(a_val).strip().lower() == str(b_val).strip().lower()

    if rule.match_method == "normalised":
        if rule.field_name == "phone":
            return _digits(str(a_val)) == _digits(str(b_val))
        # postcode and anything else normalised
        return _normalise(str(a_val)) == _normalise(str(b_val))

    if rule.match_method == "fuzzy":
        ratio = SequenceMatcher(
            None, str(a_val).strip().lower(), str(b_val).strip().lower()
        ).ratio()
        return ratio >= 0.8

    return False


def calculate_match_score(record_a, record_b):
    """Calculate a match score between two SourceRecords using active rules.

    Returns a float in the range 0.0–1.0 rounded to 2 decimal places.
    """
    rules = MatchRule.query.filter_by(is_active=True).all()
    if not rules:
        return 0.0
    score = sum(
        rule.weight for rule in rules if _compare_field(rule, record_a, record_b)
    )
    return round(min(score, 1.0), 2)


def recalculate_candidate_score(candidate):
    """Recalculate and update the score for a single candidate.

    Only pending candidates are updated; approved/rejected keep their historical
    scores for auditability.
    """
    if candidate.status != "pending":
        return
    candidate.match_score = calculate_match_score(
        candidate.record_a, candidate.record_b
    )


def recalculate_scores_for_source_record(source_record_id):
    """Recalculate pending candidates that involve the given source record.

    Called after a source record is edited.
    """
    candidates = MatchCandidate.query.filter(
        MatchCandidate.status == "pending",
        (MatchCandidate.record_a_id == source_record_id)
        | (MatchCandidate.record_b_id == source_record_id),
    ).all()
    for candidate in candidates:
        recalculate_candidate_score(candidate)


def recalculate_all_candidate_scores():
    """Recalculate all pending candidate scores.

    Called when match rules are created or edited.
    """
    for candidate in MatchCandidate.query.filter_by(status="pending").all():
        recalculate_candidate_score(candidate)


def generate_candidates_for_source_record(record, triggered_by="source_record_created"):
    """Compare record against all other active records and create/update/remove pending candidates.

    Called after a source record is created or edited.
    Returns the number of candidates created.
    """
    if record.is_archived:
        return 0

    others = SourceRecord.query.filter(
        SourceRecord.id != record.id,
        SourceRecord.is_archived == False,  # noqa: E712
    ).all()

    created = 0
    for other in others:
        score = calculate_match_score(record, other)

        # Keep pair order consistent — lower id is always record_a
        a_id, b_id = (record.id, other.id) if record.id < other.id else (other.id, record.id)

        existing = MatchCandidate.query.filter_by(
            record_a_id=a_id, record_b_id=b_id
        ).first()

        if score >= REVIEW_THRESHOLD:
            if existing is None:
                candidate = MatchCandidate(
                    record_a_id=a_id,
                    record_b_id=b_id,
                    match_score=score,
                    status="pending",
                )
                db.session.add(candidate)
                db.session.flush()  # get candidate.id for audit log
                db.session.add(AuditLog(
                    user_id=None,
                    action="match_candidate_created",
                    target_type="match_candidate",
                    target_id=candidate.id,
                    detail=f"Candidate MC-{candidate.id:04d} auto-generated after {triggered_by} (score {score:.0%})",
                ))
                created += 1
            elif existing.status == "pending":
                # Update score if the candidate hasn't been reviewed
                existing.match_score = score
        else:
            # Score dropped below threshold — remove the pending candidate if it has no decisions
            if existing and existing.status == "pending" and not existing.decisions:
                db.session.delete(existing)

    return created
