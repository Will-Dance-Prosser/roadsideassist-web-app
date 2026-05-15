import pytest
from datetime import date
from app import create_app
from app.extensions import db
from app.models import MatchCandidate, SourceRecord, SourceSystem, User
from app.match_queue.explain import (
    build_explanation,
    explain_date_of_birth,
    explain_email,
    explain_last_name,
    explain_phone,
    explain_postcode,
)
from config import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Minimal stub records — no database needed for unit tests
# ---------------------------------------------------------------------------

class _Rec:
    """Lightweight stand-in for SourceRecord with only the fields explain uses."""
    def __init__(self, **kwargs):
        self.first_name = kwargs.get("first_name")
        self.last_name = kwargs.get("last_name")
        self.email = kwargs.get("email")
        self.date_of_birth = kwargs.get("date_of_birth")
        self.postcode = kwargs.get("postcode")
        self.phone = kwargs.get("phone")


# ---------------------------------------------------------------------------
# Unit tests — explain helpers
# ---------------------------------------------------------------------------

def test_explain_dob_exact_match():
    a = _Rec(date_of_birth=date(1980, 4, 12))
    b = _Rec(date_of_birth=date(1980, 4, 12))
    result = explain_date_of_birth(a, b)
    assert result["match"] is True
    assert result["result"] == "Match"
    assert "match" in result["note"].lower()


def test_explain_dob_mismatch():
    a = _Rec(date_of_birth=date(1980, 4, 12))
    b = _Rec(date_of_birth=date(1990, 1, 1))
    result = explain_date_of_birth(a, b)
    assert result["match"] is False
    assert result["result"] == "Mismatch"


def test_explain_dob_missing():
    a = _Rec(date_of_birth=None)
    b = _Rec(date_of_birth=date(1980, 4, 12))
    result = explain_date_of_birth(a, b)
    assert result["match"] is None


def test_explain_postcode_match_after_normalisation():
    a = _Rec(postcode="SW1A 1AA")
    b = _Rec(postcode="sw1a1aa")  # different case/spacing
    result = explain_postcode(a, b)
    assert result["match"] is True
    assert result["result"] == "Match"
    assert "normalisation" in result["note"].lower()


def test_explain_postcode_mismatch():
    a = _Rec(postcode="SW1A 1AA")
    b = _Rec(postcode="M1 1AE")
    result = explain_postcode(a, b)
    assert result["match"] is False


def test_explain_postcode_missing():
    a = _Rec(postcode=None)
    b = _Rec(postcode="SW1A 1AA")
    result = explain_postcode(a, b)
    assert result["match"] is None


def test_explain_phone_match_digits_only():
    a = _Rec(phone="07700 900001")
    b = _Rec(phone="+44-7700-900001")  # different formatting, same digits
    # Both normalise to digits: 07700900001 vs 447700900001 — these differ,
    # so test with actually matching numbers:
    a2 = _Rec(phone="07700 900001")
    b2 = _Rec(phone="07700900001")
    result = explain_phone(a2, b2)
    assert result["match"] is True
    assert result["result"] == "Match"


def test_explain_phone_mismatch():
    a = _Rec(phone="07700900001")
    b = _Rec(phone="07700900002")
    result = explain_phone(a, b)
    assert result["match"] is False


def test_explain_phone_missing():
    a = _Rec(phone=None)
    b = _Rec(phone="07700900001")
    result = explain_phone(a, b)
    assert result["match"] is None


def test_explain_email_match():
    a = _Rec(email="j.smith@email.com")
    b = _Rec(email="J.SMITH@EMAIL.COM")
    result = explain_email(a, b)
    assert result["match"] is True


def test_explain_email_mismatch():
    a = _Rec(email="j.smith@email.com")
    b = _Rec(email="other@email.com")
    result = explain_email(a, b)
    assert result["match"] is False
    assert result["result"] == "Mismatch"
    assert "differ" in result["note"].lower()


def test_explain_email_missing():
    a = _Rec(email=None)
    b = _Rec(email="j.smith@email.com")
    result = explain_email(a, b)
    assert result["match"] is None


def test_explain_last_name_exact():
    a = _Rec(last_name="Smith")
    b = _Rec(last_name="smith")
    result = explain_last_name(a, b)
    assert result["match"] is True
    assert result["result"] == "Match"


def test_explain_last_name_abbreviation():
    # "J." vs "Johnson" is no longer treated as a match under fuzzy SequenceMatcher
    # (similarity ~0.29, below the 0.80 threshold). This is intentional — the old
    # prefix-check was replaced with difflib fuzzy matching to align with scoring.
    a = _Rec(last_name="J.")
    b = _Rec(last_name="Johnson")
    result = explain_last_name(a, b)
    assert result["match"] is False


def test_explain_last_name_close_fuzzy_match():
    # Near-duplicate surnames that differ by a character should return 'Similar'
    a = _Rec(last_name="Ahmed")
    b = _Rec(last_name="Ahmad")
    result = explain_last_name(a, b)
    assert result["match"] is True
    assert result["result"] == "Similar"
    assert "fuzzy rule passed" in result["note"].lower()


def test_explain_last_name_mismatch():
    a = _Rec(last_name="Smith")
    b = _Rec(last_name="Jones")
    result = explain_last_name(a, b)
    assert result["match"] is False
    assert result["result"] == "Mismatch"
    assert "fuzzy rule failed" in result["note"].lower()


# ---------------------------------------------------------------------------
# Integration test — detail page renders Match Explanation section
# ---------------------------------------------------------------------------

def _seed_candidate(app):
    with app.app_context():
        system = SourceSystem(name="CRM")
        db.session.add(system)
        db.session.flush()

        rec_a = SourceRecord(
            source_system_id=system.id, external_id="CRM-001",
            first_name="Sara", last_name="Ahmed", email="s.ahmed@email.com",
            phone="07700900001", postcode="E1 6AN", date_of_birth=date(1988, 7, 15),
        )
        rec_b = SourceRecord(
            source_system_id=system.id, external_id="LEG-001",
            first_name="Sara", last_name="Ahmad", email="s.ahmed@email.com",
            phone="07700900001", postcode="E1 6AN", date_of_birth=date(1988, 7, 15),
        )
        db.session.add_all([rec_a, rec_b])
        db.session.flush()

        candidate = MatchCandidate(
            record_a_id=rec_a.id, record_b_id=rec_b.id,
            match_score=0.88, status="pending",
        )
        db.session.add(candidate)
        db.session.commit()
        return candidate.id


def test_detail_page_renders_match_explanation_section(client, app):
    candidate_id = _seed_candidate(app)
    with app.app_context():
        user = User(username="steward", email="s@example.com", role="data_steward")
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
    client.post("/login", data={"username": "steward", "password": "pw"}, follow_redirects=True)
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"Match Explanation" in response.data
    assert b"Email" in response.data
    assert b"Date of Birth" in response.data
    assert b"Postcode" in response.data
    assert b"Phone" in response.data
    assert b"Last Name" in response.data
    # Ahmed vs Ahmad passes fuzzy threshold — badge should read Similar, not Match
    assert b"Similar" in response.data
