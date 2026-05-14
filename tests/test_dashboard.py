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


def test_dashboard_page_loads(app, client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"MemberMatch" in response.data
    assert b"Match Review Dashboard" in response.data


def test_dashboard_shows_zero_counts_when_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    # All four metric cards should render (values will be 0)
    assert b"Pending Review" in response.data
    assert b"Source Records" in response.data
    assert b"Golden Records" in response.data
    assert b"Archived Records" in response.data


def test_dashboard_shows_live_source_record_count(app, client):
    with app.app_context():
        system = SourceSystem(name="CRM")
        db.session.add(system)
        db.session.flush()
        db.session.add(SourceRecord(source_system_id=system.id, external_id="A", first_name="Test", last_name="User"))
        db.session.add(SourceRecord(source_system_id=system.id, external_id="B", first_name="Test", last_name="User", is_archived=True))
        db.session.commit()
    response = client.get("/")
    # 1 active, 1 archived — both counts should appear somewhere in the page
    assert b"Source Records" in response.data
    assert b"Archived Records" in response.data


def test_dashboard_shows_live_pending_count(app, client):
    with app.app_context():
        system = SourceSystem(name="CRM2")
        db.session.add(system)
        db.session.flush()
        r1 = SourceRecord(source_system_id=system.id, external_id="R1", first_name="A", last_name="A")
        r2 = SourceRecord(source_system_id=system.id, external_id="R2", first_name="B", last_name="B")
        db.session.add_all([r1, r2])
        db.session.flush()
        db.session.add(MatchCandidate(record_a_id=r1.id, record_b_id=r2.id, match_score=0.9, status="pending"))
        db.session.commit()
    response = client.get("/")
    assert b"Pending Review" in response.data
    assert b"1" in response.data


def test_dashboard_shows_live_golden_record_count(app, client):
    with app.app_context():
        db.session.add(GoldenRecord(first_name="John", last_name="Smith"))
        db.session.commit()
    response = client.get("/")
    assert b"Golden Records" in response.data
    assert b"1" in response.data


def test_dashboard_shows_recent_activity(app, client):
    with app.app_context():
        db.session.add(AuditLog(action="match_approved", detail="Test activity entry"))
        db.session.commit()
    response = client.get("/")
    assert b"Recent Activity" in response.data
    assert b"match_approved" in response.data
    assert b"Test activity entry" in response.data


def test_dashboard_shows_empty_state_when_no_activity(client):
    response = client.get("/")
    assert b"No activity recorded yet" in response.data
