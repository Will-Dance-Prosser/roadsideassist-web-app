# Field-level match explanation helpers.
# Each function compares a single field from two SourceRecord objects and returns
# a dict with:
#   field  - human-readable field label
#   a_val  - display value from Record A
#   b_val  - display value from Record B
#   match  - True / False / None (None = not enough data to compare)
#   result - display label: "Match", "Similar", "Mismatch", or "Unknown"
#   note   - short explanation shown in the UI

from difflib import SequenceMatcher

FUZZY_THRESHOLD = 0.8  # must match app/services/match_scoring.py


def _normalise(value):
    # Strip whitespace and convert to uppercase for loose comparison
    if value is None:
        return None
    return value.strip().upper().replace(" ", "")


def explain_date_of_birth(rec_a, rec_b):
    a, b = rec_a.date_of_birth, rec_b.date_of_birth
    if a is None or b is None:
        return {
            "field": "Date of Birth",
            "a_val": str(a) if a else "—",
            "b_val": str(b) if b else "—",
            "match": None,
            "result": "Unknown",
            "note": "Cannot compare — one or both dates are missing.",
        }
    matched = a == b
    return {
        "field": "Date of Birth",
        "a_val": a.strftime("%d %b %Y"),
        "b_val": b.strftime("%d %b %Y"),
        "match": matched,
        "result": "Match" if matched else "Mismatch",
        "note": "Exact date of birth match." if matched else "Dates of birth differ.",
    }


def explain_postcode(rec_a, rec_b):
    a, b = _normalise(rec_a.postcode), _normalise(rec_b.postcode)
    if a is None or b is None:
        return {
            "field": "Postcode",
            "a_val": rec_a.postcode or "—",
            "b_val": rec_b.postcode or "—",
            "match": None,
            "result": "Unknown",
            "note": "Cannot compare — one or both postcodes are missing.",
        }
    matched = a == b
    return {
        "field": "Postcode",
        "a_val": rec_a.postcode,
        "b_val": rec_b.postcode,
        "match": matched,
        "result": "Match" if matched else "Mismatch",
        "note": "Postcodes match (after normalisation)." if matched else "Postcodes differ.",
    }


def explain_phone(rec_a, rec_b):
    # Strip everything except digits and normalise UK numbers before comparing
    def digits(v):
        if v is None:
            return None
        d = "".join(ch for ch in v if ch.isdigit())
        # UK local mobile/landline → international: 07... → 447...
        if d.startswith("0") and len(d) == 11:
            d = "44" + d[1:]
        return d

    a, b = digits(rec_a.phone), digits(rec_b.phone)
    if a is None or b is None:
        return {
            "field": "Phone",
            "a_val": rec_a.phone or "—",
            "b_val": rec_b.phone or "—",
            "match": None,
            "result": "Unknown",
            "note": "Cannot compare — one or both phone numbers are missing.",
        }
    matched = a == b
    return {
        "field": "Phone",
        "a_val": rec_a.phone,
        "b_val": rec_b.phone,
        "match": matched,
        "result": "Match" if matched else "Mismatch",
        "note": "Phone numbers match (digits only)." if matched else "Phone numbers differ.",
    }


def explain_email(rec_a, rec_b):
    a, b = _normalise(rec_a.email), _normalise(rec_b.email)
    if a is None or b is None:
        return {
            "field": "Email",
            "a_val": rec_a.email or "—",
            "b_val": rec_b.email or "—",
            "match": None,
            "result": "Unknown",
            "note": "Cannot compare — one or both emails are missing.",
        }
    matched = a == b
    return {
        "field": "Email",
        "a_val": rec_a.email,
        "b_val": rec_b.email,
        "match": matched,
        "result": "Match" if matched else "Mismatch",
        "note": "Email addresses match." if matched else "Email addresses differ.",
    }


def explain_last_name(rec_a, rec_b):
    # Fuzzy comparison using SequenceMatcher (ratio >= FUZZY_THRESHOLD).
    # Matches "Ahmed" vs "Ahmad", "Smith" vs "Smyth", etc.
    a_raw, b_raw = rec_a.last_name, rec_b.last_name
    a, b = _normalise(a_raw), _normalise(b_raw)
    if a is None or b is None:
        return {
            "field": "Last Name",
            "a_val": a_raw or "—",
            "b_val": b_raw or "—",
            "match": None,
            "result": "Unknown",
            "note": "Cannot compare — one or both last names are missing.",
        }
    ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    passed = ratio >= FUZZY_THRESHOLD
    if passed and a == b:
        # Exact match that also satisfies the fuzzy rule — show as a plain Match
        return {
            "field": "Last Name",
            "a_val": a_raw,
            "b_val": b_raw,
            "match": True,
            "result": "Match",
            "note": "Last names match exactly.",
        }
    pct = f"{ratio:.0%}"
    threshold_pct = f"{FUZZY_THRESHOLD:.0%}"
    if passed:
        note = f"Fuzzy rule passed. Similarity {pct}, threshold {threshold_pct}."
    else:
        note = f"Fuzzy rule failed. Similarity {pct}, threshold {threshold_pct}."
    return {
        "field": "Last Name",
        "a_val": a_raw,
        "b_val": b_raw,
        "match": passed,
        "result": "Similar" if passed else "Mismatch",
        "note": note,
    }


def build_explanation(candidate):
    # Build the full list of field comparisons for the match detail page
    a, b = candidate.record_a, candidate.record_b
    return [
        explain_email(a, b),
        explain_date_of_birth(a, b),
        explain_phone(a, b),
        explain_postcode(a, b),
        explain_last_name(a, b),
    ]
