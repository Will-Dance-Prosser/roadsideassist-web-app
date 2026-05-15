# Field-level match explanation helpers.
# Each function compares a single field from two SourceRecord objects and returns
# a dict with:
#   field  - human-readable field label
#   a_val  - display value from Record A
#   b_val  - display value from Record B
#   match  - True / False / None (None = not enough data to compare)
#   note   - short explanation shown in the UI


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
            "note": "Cannot compare — one or both dates are missing.",
        }
    matched = a == b
    return {
        "field": "Date of Birth",
        "a_val": a.strftime("%d %b %Y"),
        "b_val": b.strftime("%d %b %Y"),
        "match": matched,
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
            "note": "Cannot compare — one or both postcodes are missing.",
        }
    matched = a == b
    return {
        "field": "Postcode",
        "a_val": rec_a.postcode,
        "b_val": rec_b.postcode,
        "match": matched,
        "note": "Postcodes match (after normalisation)." if matched else "Postcodes differ.",
    }


def explain_phone(rec_a, rec_b):
    # Strip everything except digits before comparing
    # TODO: could +44 prefix stripping be handled here???
    def digits(v):
        if v is None:
            return None
        return "".join(ch for ch in v if ch.isdigit())

    a, b = digits(rec_a.phone), digits(rec_b.phone)
    if a is None or b is None:
        return {
            "field": "Phone",
            "a_val": rec_a.phone or "—",
            "b_val": rec_b.phone or "—",
            "match": None,
            "note": "Cannot compare — one or both phone numbers are missing.",
        }
    matched = a == b
    return {
        "field": "Phone",
        "a_val": rec_a.phone,
        "b_val": rec_b.phone,
        "match": matched,
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
            "note": "Cannot compare — one or both emails are missing.",
        }
    matched = a == b
    return {
        "field": "Email",
        "a_val": rec_a.email,
        "b_val": rec_b.email,
        "match": matched,
        "note": "Email addresses match." if matched else "Email addresses differ.",
    }


def explain_last_name(rec_a, rec_b):
    # Exact match first, then a basic prefix check for abbreviations
    # e.g. 'J.' should loosely match 'JOHNSON' - not perfect but good enough for now
    a_raw, b_raw = rec_a.last_name, rec_b.last_name
    a, b = _normalise(a_raw), _normalise(b_raw)
    if a is None or b is None:
        return {
            "field": "Last Name",
            "a_val": a_raw or "—",
            "b_val": b_raw or "—",
            "match": None,
            "note": "Cannot compare — one or both last names are missing.",
        }
    if a == b:
        return {
            "field": "Last Name",
            "a_val": a_raw,
            "b_val": b_raw,
            "match": True,
            "note": "Last names match exactly.",
        }
    # Partial: strip punctuation for prefix check so "J." matches "JOHNSON"
    a_alpha = "".join(ch for ch in a if ch.isalpha())
    b_alpha = "".join(ch for ch in b if ch.isalpha())
    if a_alpha and b_alpha and (b_alpha.startswith(a_alpha) or a_alpha.startswith(b_alpha)):
        return {
            "field": "Last Name",
            "a_val": a_raw,
            "b_val": b_raw,
            "match": True,
            "note": "Last names appear similar (one may be an abbreviation).",
        }
    return {
        "field": "Last Name",
        "a_val": a_raw,
        "b_val": b_raw,
        "match": False,
        "note": "Last names differ.",
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
