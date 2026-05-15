import pytest
from app import create_app
from app.extensions import db
from app.models import AuditLog, GoldenRecord, MatchCandidate, SourceRecord, SourceSystem, User
from config import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        user = User(username="steward", email="steward@example.com", role="data_steward")
        user.set_password("correct-password")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"username": "steward", "password": "correct-password"}, follow_redirects=True)
    return c


@pytest.fixture
def anon_client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_reports_requires_login(anon_client):
    response = anon_client.get("/reports", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Basic load
# ---------------------------------------------------------------------------

def test_reports_page_loads(client):
    response = client.get("/reports")
    assert response.status_code == 200
    assert b"Reports" in response.data
    assert b"Match Outcomes" in response.data
    assert b"Data Quality" in response.data
    assert b"Stewardship Activity" in response.data


# ---------------------------------------------------------------------------
# Match Outcomes
# ---------------------------------------------------------------------------

def test_reports_shows_match_outcome_counts(app, client):
    with app.app_context():
        system = SourceSystem(name="RPT-SYS")
        db.session.add(system)
        db.session.flush()
        r1 = SourceRecord(source_system_id=system.id, external_id="R1", first_name="A", last_name="A")
        r2 = SourceRecord(source_system_id=system.id, external_id="R2", first_name="B", last_name="B")
        r3 = SourceRecord(source_system_id=system.id, external_id="R3", first_name="C", last_name="C")
        r4 = SourceRecord(source_system_id=system.id, external_id="R4", first_name="D", last_name="D")
        db.session.add_all([r1, r2, r3, r4])
        db.session.flush()
        db.session.add(MatchCandidate(record_a_id=r1.id, record_b_id=r2.id, match_score=0.9, status="pending"))
        db.session.add(MatchCandidate(record_a_id=r2.id, record_b_id=r3.id, match_score=0.8, status="approved"))
        db.session.add(MatchCandidate(record_a_id=r3.id, record_b_id=r4.id, match_score=0.7, status="rejected"))
        db.session.commit()
    response = client.get("/reports")
    assert response.status_code == 200
    assert b"Pending review" in response.data
    assert b"Approved" in response.data
    assert b"Rejected" in response.data


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------

def test_reports_shows_data_quality_counts(app, client):
    with app.app_context():
        system = SourceSystem(name="RPT-DQ")
        db.session.add(system)
        db.session.flush()
        db.session.add(SourceRecord(source_system_id=system.id, external_id="DQ1", first_name="X", last_name="X"))
        db.session.add(SourceRecord(source_system_id=system.id, external_id="DQ2", first_name="Y", last_name="Y", is_archived=True))
        db.session.add(GoldenRecord(first_name="Gold", last_name="One"))
        db.session.commit()
    response = client.get("/reports")
    assert b"Active source records" in response.data
    assert b"Archived source records" in response.data
    assert b"Golden records" in response.data
    assert b"Connected source systems" in response.data


# ---------------------------------------------------------------------------
# Stewardship Activity
# ---------------------------------------------------------------------------

def test_reports_shows_stewardship_activity(app, client):
    with app.app_context():
        db.session.add(AuditLog(action="match_approved", detail="Candidate 1 approved"))
        db.session.add(AuditLog(action="match_rejected", detail="Candidate 2 rejected"))
        db.session.commit()
    response = client.get("/reports")
    assert b"Approved" in response.data
    assert b"Rejected" in response.data
    assert b"Candidate 1 approved" in response.data


def test_reports_shows_empty_stewardship_state(client):
    response = client.get("/reports")
    assert b"No approve or reject decisions" in response.data
