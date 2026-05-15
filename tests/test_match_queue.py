import pytest
from app import create_app
from app.extensions import db
from app.models import AuditLog, GoldenRecord, GoldenRecordLink, MatchCandidate, MergeDecision, SourceRecord, SourceSystem, User
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


def _login(client, app, role="data_steward"):
    with app.app_context():
        user = User(username="testuser", email="test@example.com", role=role)
        user.set_password("test-password")
        db.session.add(user)
        db.session.commit()
    client.post("/login", data={"username": "testuser", "password": "test-password"}, follow_redirects=True)


def _seed_candidates(app):
    with app.app_context():
        system = SourceSystem(name="CRM")
        db.session.add(system)
        db.session.commit()

        rec_a = SourceRecord(source_system_id=system.id, external_id="CRM-001", first_name="John",  last_name="Smith")
        rec_b = SourceRecord(source_system_id=system.id, external_id="CRM-002", first_name="J.",    last_name="Smith")
        rec_c = SourceRecord(source_system_id=system.id, external_id="CRM-003", first_name="Alice", last_name="Jones")
        db.session.add_all([rec_a, rec_b, rec_c])
        db.session.commit()

        db.session.add(MatchCandidate(record_a_id=rec_a.id, record_b_id=rec_b.id, match_score=0.95, status="pending"))
        db.session.add(MatchCandidate(record_a_id=rec_a.id, record_b_id=rec_c.id, match_score=0.72, status="pending"))
        db.session.commit()


def test_unauthenticated_match_queue_redirects_to_login(client):
    response = client.get("/match-queue", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logged_in_user_can_access_match_queue(client, app):
    _login(client, app)
    response = client.get("/match-queue")
    assert response.status_code == 200
    assert b"Match Queue" in response.data


def test_match_queue_renders_candidates_from_database(client, app):
    _seed_candidates(app)
    _login(client, app)
    response = client.get("/match-queue")
    assert response.status_code == 200
    assert b"John" in response.data or b"CRM-001" in response.data


def test_match_queue_ordered_by_score_descending(client, app):
    _seed_candidates(app)
    _login(client, app)
    response = client.get("/match-queue")
    data = response.data.decode()
    # 95% should appear before 72% in the page
    assert data.index("95") < data.index("72")


# ---------------------------------------------------------------------------
# Candidate detail page tests
# ---------------------------------------------------------------------------

def _seed_candidate(app):
    """Create two source records and one match candidate, return the candidate id."""
    with app.app_context():
        system = SourceSystem.query.filter_by(name="CRM").first()
        if not system:
            system = SourceSystem(name="CRM")
            db.session.add(system)
            db.session.commit()

        rec_a = SourceRecord(
            source_system_id=system.id,
            external_id="DET-001",
            first_name="John",
            last_name="Smith",
            email="john.smith@example.com",
            postcode="SW1A 1AA",
            phone="07700900001",
        )
        rec_b = SourceRecord(
            source_system_id=system.id,
            external_id="DET-002",
            first_name="J.",
            last_name="Smith",
            email="john.smith@example.com",
            postcode="SW1A 1AA",
            phone="07700900001",
        )
        db.session.add_all([rec_a, rec_b])
        db.session.commit()

        candidate = MatchCandidate(
            record_a_id=rec_a.id,
            record_b_id=rec_b.id,
            match_score=0.97,
            status="pending",
        )
        db.session.add(candidate)
        db.session.commit()
        return candidate.id


def test_unauthenticated_candidate_detail_redirects_to_login(client, app):
    candidate_id = _seed_candidate(app)
    response = client.get(f"/match-candidates/{candidate_id}", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logged_in_user_can_view_candidate_detail(client, app):
    candidate_id = _seed_candidate(app)
    _login(client, app)
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"Match Candidate" in response.data


def test_candidate_detail_renders_both_source_records(client, app):
    candidate_id = _seed_candidate(app)
    _login(client, app)
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"DET-001" in response.data
    assert b"DET-002" in response.data
    assert b"John" in response.data
    assert b"97%" in response.data


def test_missing_candidate_returns_404(client, app):
    _login(client, app)
    response = client.get("/match-candidates/99999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Approve / reject workflow tests
# ---------------------------------------------------------------------------

def _login_as(client, app, role):
    """Create a user with the given role and log them in."""
    username = f"user_{role}"
    with app.app_context():
        if not User.query.filter_by(username=username).first():
            user = User(username=username, email=f"{role}@example.com", role=role)
            user.set_password("test-password")
            db.session.add(user)
            db.session.commit()
    client.post("/login", data={"username": username, "password": "test-password"}, follow_redirects=True)


def _seed_pending_candidate(app):
    """Seed a fresh pending candidate and return its id."""
    with app.app_context():
        system = SourceSystem.query.filter_by(name="CRM").first()
        if not system:
            system = SourceSystem(name="CRM")
            db.session.add(system)
            db.session.commit()
        rec_a = SourceRecord(source_system_id=system.id, external_id="WF-001", first_name="Alice", last_name="Brown", email="alice@example.com")
        rec_b = SourceRecord(source_system_id=system.id, external_id="WF-002", first_name="A.", last_name="Brown", email="alice@example.com")
        db.session.add_all([rec_a, rec_b])
        db.session.commit()
        candidate = MatchCandidate(record_a_id=rec_a.id, record_b_id=rec_b.id, match_score=0.93, status="pending")
        db.session.add(candidate)
        db.session.commit()
        return candidate.id


def _post(client, url):
    """Send a POST with CSRF bypassed (test client uses WTF_CSRF_ENABLED=False)."""
    return client.post(url, follow_redirects=True)


def test_data_steward_can_approve_pending_candidate(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/approve")
    with app.app_context():
        c = db.session.get(MatchCandidate, candidate_id)
        assert c.status == "approved"
        assert c.reviewed_at is not None
        assert c.reviewed_by_id is not None


def test_approve_creates_merge_decision(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/approve")
    with app.app_context():
        decision = MergeDecision.query.filter_by(candidate_id=candidate_id).first()
        assert decision is not None
        assert decision.decision == "approved"


def test_approve_creates_golden_record_and_links(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/approve")
    with app.app_context():
        assert GoldenRecord.query.count() == 1
        assert GoldenRecordLink.query.count() == 2


def test_approve_creates_audit_log_entry(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/approve")
    with app.app_context():
        log = AuditLog.query.filter_by(action="match_approved").first()
        assert log is not None
        assert log.target_id == candidate_id


def test_data_steward_can_reject_pending_candidate(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    with app.app_context():
        c = db.session.get(MatchCandidate, candidate_id)
        assert c.status == "rejected"


def test_reject_creates_merge_decision_and_audit_log(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    with app.app_context():
        decision = MergeDecision.query.filter_by(candidate_id=candidate_id).first()
        assert decision is not None
        assert decision.decision == "rejected"
        log = AuditLog.query.filter_by(action="match_rejected").first()
        assert log is not None


def test_reject_does_not_create_golden_record(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    with app.app_context():
        assert GoldenRecord.query.count() == 0


def test_data_analyst_cannot_approve_receives_403(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_analyst")
    response = client.post(f"/match-candidates/{candidate_id}/approve")
    assert response.status_code == 403


def test_data_analyst_cannot_reject_receives_403(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_analyst")
    response = client.post(f"/match-candidates/{candidate_id}/reject")
    assert response.status_code == 403


def test_administrator_cannot_approve_receives_403(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "administrator")
    response = client.post(f"/match-candidates/{candidate_id}/approve")
    assert response.status_code == 403


def test_administrator_cannot_reject_receives_403(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "administrator")
    response = client.post(f"/match-candidates/{candidate_id}/reject")
    assert response.status_code == 403


def test_already_reviewed_candidate_cannot_be_reviewed_again(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/approve")
    # Try to approve again — should flash warning, not duplicate
    _post(client, f"/match-candidates/{candidate_id}/approve")
    with app.app_context():
        assert MergeDecision.query.filter_by(candidate_id=candidate_id).count() == 1
        assert GoldenRecord.query.count() == 1
        assert GoldenRecordLink.query.count() == 2
        assert AuditLog.query.filter_by(action="match_approved").count() == 1


def test_already_rejected_candidate_cannot_be_rejected_again(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    with app.app_context():
        assert MergeDecision.query.filter_by(candidate_id=candidate_id).count() == 1
        assert AuditLog.query.filter_by(action="match_rejected").count() == 1


def test_approve_buttons_hidden_for_data_analyst(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_analyst")
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"Approve Match" not in response.data
    assert b"Reject Match" not in response.data


def test_approve_buttons_hidden_for_administrator(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "administrator")
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"Approve Match" not in response.data
    assert b"Reject Match" not in response.data


def test_approve_buttons_hidden_for_already_reviewed_candidate(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/approve")
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"Approve Match" not in response.data
    assert b"Reject Match" not in response.data


# ---------------------------------------------------------------------------
# Source record navigation links on candidate detail page
# ---------------------------------------------------------------------------

def test_candidate_detail_shows_view_source_record_links(client, app):
    # All roles should see a View source record link for each record card
    candidate_id = _seed_candidate(app)
    _login(client, app, role="data_analyst")
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"View source record" in response.data


def test_candidate_detail_source_record_link_points_to_detail_route(client, app):
    candidate_id = _seed_candidate(app)
    _login(client, app)
    response = client.get(f"/match-candidates/{candidate_id}")
    assert b"/source-records/" in response.data


def test_data_analyst_not_shown_edit_link_on_candidate_detail(client, app):
    candidate_id = _seed_candidate(app)
    _login(client, app, role="data_analyst")
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"View source record" in response.data
    assert b"Edit" not in response.data


def test_data_steward_sees_edit_link_on_candidate_detail(client, app):
    candidate_id = _seed_candidate(app)
    _login(client, app, role="data_steward")
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"View source record" in response.data
    assert b"Edit" in response.data
