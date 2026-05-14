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
def admin_client(app):
    with app.app_context():
        admin = User(username="admin", email="admin@example.com", role="administrator")
        admin.set_password("admin-password")
        db.session.add(admin)
        db.session.commit()
    c = app.test_client()
    c.post("/login", data={"username": "admin", "password": "admin-password"}, follow_redirects=True)
    return c


@pytest.fixture
def analyst_client(app):
    with app.app_context():
        analyst = User(username="analyst", email="analyst@example.com", role="data_analyst")
        analyst.set_password("analyst-password")
        db.session.add(analyst)
        db.session.commit()
    c = app.test_client()
    c.post("/login", data={"username": "analyst", "password": "analyst-password"}, follow_redirects=True)
    return c


def _seed_two_candidates(app):
    """Seed two pending MatchCandidates with different scores; return (high_id, low_id)."""
    with app.app_context():
        system = SourceSystem(name="CRM-pq")
        db.session.add(system)
        db.session.flush()
        r1 = SourceRecord(source_system_id=system.id, external_id="PQ1", first_name="Alice", last_name="Smith")
        r2 = SourceRecord(source_system_id=system.id, external_id="PQ2", first_name="Bob",   last_name="Jones")
        r3 = SourceRecord(source_system_id=system.id, external_id="PQ3", first_name="Carol",  last_name="White")
        db.session.add_all([r1, r2, r3])
        db.session.flush()
        high = MatchCandidate(record_a_id=r1.id, record_b_id=r2.id, match_score=0.95, status="pending")
        low  = MatchCandidate(record_a_id=r2.id, record_b_id=r3.id, match_score=0.60, status="pending")
        db.session.add_all([high, low])
        db.session.commit()
        return high.id, low.id


# ---------------------------------------------------------------------------
# Basic load
# ---------------------------------------------------------------------------

def test_dashboard_page_loads(app, client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"MemberMatch" in response.data
    assert b"Match Review Dashboard" in response.data


# ---------------------------------------------------------------------------
# Workflow status cards
# ---------------------------------------------------------------------------

def test_dashboard_shows_section_headings(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Review Workload"        in response.data
    assert b"Data Quality Snapshot"  in response.data
    assert b"Priority Match Queue"   in response.data


def test_admin_dashboard_shows_recent_activity_heading(admin_client):
    response = admin_client.get("/")
    assert response.status_code == 200
    assert b"Recent Activity" in response.data


def test_dashboard_shows_workflow_labels(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Pending Review"   in response.data or b"pending" in response.data
    assert b"Approved"         in response.data
    assert b"Rejected"         in response.data
    assert b"Golden Records"   in response.data


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
    assert b"Review Workload" in response.data
    assert b"1" in response.data


def test_dashboard_shows_highest_pending_score(app, client):
    with app.app_context():
        system = SourceSystem(name="CRM-score")
        db.session.add(system)
        db.session.flush()
        r1 = SourceRecord(source_system_id=system.id, external_id="S1", first_name="A", last_name="A")
        r2 = SourceRecord(source_system_id=system.id, external_id="S2", first_name="B", last_name="B")
        db.session.add_all([r1, r2])
        db.session.flush()
        db.session.add(MatchCandidate(record_a_id=r1.id, record_b_id=r2.id, match_score=0.87, status="pending"))
        db.session.commit()
    response = client.get("/")
    assert b"87%" in response.data


def test_dashboard_shows_data_quality_counts(app, client):
    with app.app_context():
        system = SourceSystem(name="CRM-dq")
        db.session.add(system)
        db.session.flush()
        db.session.add(SourceRecord(source_system_id=system.id, external_id="DQ1", first_name="X", last_name="X"))
        db.session.add(SourceRecord(source_system_id=system.id, external_id="DQ2", first_name="Y", last_name="Y", is_archived=True))
        db.session.commit()
    response = client.get("/")
    assert b"Active source records"   in response.data
    assert b"Archived source records" in response.data


def test_dashboard_shows_live_approved_count(app, client):
    with app.app_context():
        system = SourceSystem(name="CRM3")
        db.session.add(system)
        db.session.flush()
        r1 = SourceRecord(source_system_id=system.id, external_id="C1", first_name="X", last_name="X")
        r2 = SourceRecord(source_system_id=system.id, external_id="C2", first_name="Y", last_name="Y")
        db.session.add_all([r1, r2])
        db.session.flush()
        db.session.add(MatchCandidate(record_a_id=r1.id, record_b_id=r2.id, match_score=0.8, status="approved"))
        db.session.commit()
    response = client.get("/")
    assert b"Approved" in response.data
    assert b"1" in response.data


def test_dashboard_shows_live_golden_record_count(app, client):
    with app.app_context():
        db.session.add(GoldenRecord(first_name="John", last_name="Smith"))
        db.session.commit()
    response = client.get("/")
    assert b"Golden Records" in response.data
    assert b"1" in response.data


# ---------------------------------------------------------------------------
# Priority Match Queue
# ---------------------------------------------------------------------------

def test_dashboard_shows_priority_queue_section(client):
    response = client.get("/")
    assert b"Priority Match Queue" in response.data


def test_dashboard_shows_pending_candidates_in_priority_queue(app, client):
    _seed_two_candidates(app)
    response = client.get("/")
    assert b"Alice" in response.data
    assert b"Bob"   in response.data
    assert b"Review" in response.data


def test_data_steward_sees_review_button_in_queue(app, client):
    _seed_two_candidates(app)
    response = client.get("/")
    assert b"Review" in response.data


def test_data_analyst_sees_view_button_in_queue(app, analyst_client):
    _seed_two_candidates(app)
    response = analyst_client.get("/")
    assert b"View</a>" in response.data       # button label is "View"
    assert b"Review</a>" not in response.data  # no "Review" button text


def test_dashboard_priority_queue_ordered_by_score_descending(app, client):
    _seed_two_candidates(app)
    response = client.get("/")
    html = response.data.decode()
    # 95% should appear before 60% in the rendered page
    assert html.index("95%") < html.index("60%")


def test_dashboard_shows_empty_queue_state_when_no_candidates(client):
    response = client.get("/")
    assert b"No pending candidates" in response.data


# ---------------------------------------------------------------------------
# Recent Activity — administrator only
# ---------------------------------------------------------------------------

def test_dashboard_shows_recent_activity_section(admin_client):
    response = admin_client.get("/")
    assert b"Recent Activity" in response.data


def test_dashboard_shows_recent_activity(app, admin_client):
    with app.app_context():
        db.session.add(AuditLog(action="match_approved", detail="Test activity entry"))
        db.session.commit()
    response = admin_client.get("/")
    assert b"Recent Activity" in response.data
    assert b"match_approved" in response.data
    assert b"Test activity entry" in response.data


def test_dashboard_shows_empty_state_when_no_activity(admin_client):
    response = admin_client.get("/")
    assert b"No activity recorded yet" in response.data


# ---------------------------------------------------------------------------
# Role-aware right panel
# ---------------------------------------------------------------------------

def test_data_steward_does_not_see_audit_log_entries(app, client):
    with app.app_context():
        db.session.add(AuditLog(action="match_approved", detail="Secret audit detail"))
        db.session.commit()
    response = client.get("/")
    assert b"match_approved" not in response.data
    assert b"Secret audit detail" not in response.data


def test_data_analyst_does_not_see_audit_log_entries(app, analyst_client):
    with app.app_context():
        db.session.add(AuditLog(action="match_rejected", detail="Analyst should not see this"))
        db.session.commit()
    response = analyst_client.get("/")
    assert b"match_rejected" not in response.data
    assert b"Analyst should not see this" not in response.data


# ---------------------------------------------------------------------------
# Quick links
# ---------------------------------------------------------------------------

def test_dashboard_has_view_queue_link(client):
    response = client.get("/")
    assert b"View queue" in response.data


def test_dashboard_has_view_records_link(client):
    response = client.get("/")
    assert b"View records" in response.data


def test_dashboard_has_view_golden_records_link(client):
    response = client.get("/")
    assert b"View golden records" in response.data


def test_admin_sees_view_audit_log_link(admin_client):
    response = admin_client.get("/")
    assert b"View audit log" in response.data


def test_data_steward_does_not_see_view_audit_log_link(client):
    response = client.get("/")
    assert b"View audit log" not in response.data


def test_data_analyst_does_not_see_view_audit_log_link(analyst_client):
    response = analyst_client.get("/")
    assert b"View audit log" not in response.data
