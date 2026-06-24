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


def _post(client, url, data=None):
    """Send a POST with CSRF bypassed (test client uses WTF_CSRF_ENABLED=False)."""
    return client.post(url, data=data or {}, follow_redirects=True)


def _approve(client, candidate_id, primary="a"):
    """Approve a candidate with a primary record selection."""
    return _post(client, f"/match-candidates/{candidate_id}/approve", data={"primary_record": primary})


def test_data_steward_can_approve_pending_candidate(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id)
    with app.app_context():
        c = db.session.get(MatchCandidate, candidate_id)
        assert c.status == "approved"
        assert c.reviewed_at is not None
        assert c.reviewed_by_id is not None


def test_approve_creates_merge_decision(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id)
    with app.app_context():
        decision = MergeDecision.query.filter_by(candidate_id=candidate_id).first()
        assert decision is not None
        assert decision.decision == "approved"


def test_approve_creates_golden_record_and_links(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id)
    with app.app_context():
        assert GoldenRecord.query.count() == 1
        assert GoldenRecordLink.query.count() == 2


def test_approve_creates_audit_log_entry(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id)
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
    _approve(client, candidate_id)
        # Try to approve again — should flash warning, not duplicate
    _approve(client, candidate_id)
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


# ---------------------------------------------------------------------------
# Related candidates tests
# ---------------------------------------------------------------------------

def _seed_related_candidates(app):
    """Seed two candidates that share Record A, plus one unrelated candidate."""
    with app.app_context():
        system = SourceSystem(name="Related-CRM")
        db.session.add(system)
        db.session.commit()

        rec_a = SourceRecord(source_system_id=system.id, external_id="R-001", first_name="Alice", last_name="Smith")
        rec_b = SourceRecord(source_system_id=system.id, external_id="R-002", first_name="Alice", last_name="Smyth")
        rec_c = SourceRecord(source_system_id=system.id, external_id="R-003", first_name="Alice", last_name="Smithe")
        rec_d = SourceRecord(source_system_id=system.id, external_id="R-004", first_name="Bob",   last_name="Jones")
        rec_e = SourceRecord(source_system_id=system.id, external_id="R-005", first_name="Bob",   last_name="Jonez")
        db.session.add_all([rec_a, rec_b, rec_c, rec_d, rec_e])
        db.session.commit()

        # main candidate (A+B) and a related one (A+C), plus unrelated (D+E)
        main = MatchCandidate(record_a_id=rec_a.id, record_b_id=rec_b.id, match_score=0.90, status="pending")
        related = MatchCandidate(record_a_id=rec_a.id, record_b_id=rec_c.id, match_score=0.75, status="pending")
        unrelated = MatchCandidate(record_a_id=rec_d.id, record_b_id=rec_e.id, match_score=0.80, status="pending")
        db.session.add_all([main, related, unrelated])
        db.session.commit()
        return main.id, related.id


def test_related_candidates_shown_on_detail_page(client, app):
    main_id, related_id = _seed_related_candidates(app)
    _login(client, app)
    response = client.get(f"/match-candidates/{main_id}")
    assert response.status_code == 200
    assert b"Related Candidates" in response.data
    # The related candidate's ID should appear
    assert f"MC-{related_id:04d}".encode() in response.data


def test_related_candidates_does_not_show_current_candidate(client, app):
    main_id, related_id = _seed_related_candidates(app)
    _login(client, app)
    response = client.get(f"/match-candidates/{main_id}")
    assert response.status_code == 200
    # The related candidate should have a View link
    assert f"/match-candidates/{related_id}".encode() in response.data
    # The related table should not contain a View link back to the current candidate
    assert f"match-candidates/{main_id}\" class=\"btn".encode() not in response.data


def test_no_related_candidates_shows_empty_state(client, app):
    candidate_id = _seed_candidate(app)  # isolated candidate with no shared records
    _login(client, app)
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"No related candidates found" in response.data


# ---------------------------------------------------------------------------
# Merge selection tests
# ---------------------------------------------------------------------------

def _seed_merge_candidate(app):
    """Seed a candidate where record_a has email but no phone, record_b has phone but no email."""
    with app.app_context():
        system = SourceSystem(name="MergeTest")
        db.session.add(system)
        db.session.commit()
        rec_a = SourceRecord(
            source_system_id=system.id, external_id="M-001",
            first_name="Jane", last_name="Doe",
            email="jane@example.com", phone=None,
        )
        rec_b = SourceRecord(
            source_system_id=system.id, external_id="M-002",
            first_name="J.", last_name="Doe",
            email=None, phone="+447400123456",
        )
        db.session.add_all([rec_a, rec_b])
        db.session.commit()
        candidate = MatchCandidate(record_a_id=rec_a.id, record_b_id=rec_b.id, match_score=0.85, status="pending")
        db.session.add(candidate)
        db.session.commit()
        return candidate.id, rec_a.id, rec_b.id


def test_approve_with_primary_a_uses_record_a_as_base(client, app):
    candidate_id, rec_a_id, rec_b_id = _seed_merge_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id, primary="a")
    with app.app_context():
        from app.models import GoldenRecord
        golden = GoldenRecord.query.first()
        assert golden is not None
        assert golden.first_name == "Jane"   # from record_a
        assert golden.phone == "+447400123456"  # filled from record_b


def test_approve_with_primary_b_uses_record_b_as_base(client, app):
    candidate_id, rec_a_id, rec_b_id = _seed_merge_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id, primary="b")
    with app.app_context():
        from app.models import GoldenRecord
        golden = GoldenRecord.query.first()
        assert golden is not None
        assert golden.first_name == "J."     # from record_b (the primary)
        assert golden.email == "jane@example.com"  # filled from record_a


def test_approve_audit_log_includes_primary_record_id(client, app):
    candidate_id, rec_a_id, rec_b_id = _seed_merge_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id, primary="a")
    with app.app_context():
        log = AuditLog.query.filter_by(action="match_approved").first()
        assert log is not None
        assert "M-001" in log.detail  # record_a external_id


def test_merge_selection_ui_shown_for_pending_candidate(client, app):
    candidate_id, _, _ = _seed_merge_candidate(app)
    _login_as(client, app, "data_steward")
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"Approve &amp; Merge" in response.data
    assert b"primary_record" in response.data


def test_merge_selection_ui_not_shown_for_approved_candidate(client, app):
    candidate_id, _, _ = _seed_merge_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id, primary="a")
    response = client.get(f"/match-candidates/{candidate_id}")
    assert b"primary_record" not in response.data


# ---------------------------------------------------------------------------
# Merge into existing golden record tests
# ---------------------------------------------------------------------------

def _seed_two_candidates_sharing_record(app):
    """
    Three source records: A, B, C.
    Candidate 1: A + B  (approve this first to create a golden record)
    Candidate 2: A + C  (approving this should add C to the existing golden record)
    """
    with app.app_context():
        system = SourceSystem(name="ClusterTest")
        db.session.add(system)
        db.session.commit()
        rec_a = SourceRecord(source_system_id=system.id, external_id="CL-001", first_name="Tom", last_name="Jones", email="tom@example.com")
        rec_b = SourceRecord(source_system_id=system.id, external_id="CL-002", first_name="T.",  last_name="Jones", email="tom@example.com")
        rec_c = SourceRecord(source_system_id=system.id, external_id="CL-003", first_name="Tom", last_name="Jones", email="tom@example.com", phone="+447400123456")
        db.session.add_all([rec_a, rec_b, rec_c])
        db.session.commit()
        c1 = MatchCandidate(record_a_id=rec_a.id, record_b_id=rec_b.id, match_score=0.90, status="pending")
        c2 = MatchCandidate(record_a_id=rec_a.id, record_b_id=rec_c.id, match_score=0.85, status="pending")
        db.session.add_all([c1, c2])
        db.session.commit()
        return c1.id, c2.id, rec_c.id


def test_second_approval_adds_to_existing_golden_record(client, app):
    c1_id, c2_id, rec_c_id = _seed_two_candidates_sharing_record(app)
    _login_as(client, app, "data_steward")
    _approve(client, c1_id, primary="a")   # creates golden record
    _approve(client, c2_id, primary="a")   # should add rec_c to same golden record
    with app.app_context():
        from app.models import GoldenRecord, GoldenRecordLink
        assert GoldenRecord.query.count() == 1  # only one golden record
        assert GoldenRecordLink.query.count() == 3  # all three source records linked


def test_second_approval_fills_missing_fields_from_new_record(client, app):
    c1_id, c2_id, rec_c_id = _seed_two_candidates_sharing_record(app)
    _login_as(client, app, "data_steward")
    _approve(client, c1_id, primary="a")
    _approve(client, c2_id, primary="a")
    with app.app_context():
        from app.models import GoldenRecord
        golden = GoldenRecord.query.first()
        # rec_c had a phone number; the golden record should now have it
        assert golden.phone == "+447400123456"


def test_two_separate_golden_records_merged_on_approval(client, app):
    """Approve A+B and A+C independently so A and C both get their own golden records,
    then approve B+C — this should merge the two golden records into one."""
    with app.app_context():
        system = SourceSystem(name="MergeTwo")
        db.session.add(system)
        db.session.commit()
        rec_a = SourceRecord(source_system_id=system.id, external_id="MT-001", first_name="Sue", last_name="Lee", email="sue@example.com")
        rec_b = SourceRecord(source_system_id=system.id, external_id="MT-002", first_name="S.",  last_name="Lee", email="sue@example.com")
        rec_c = SourceRecord(source_system_id=system.id, external_id="MT-003", first_name="Sue", last_name="Lee", email="sue@example.com")
        db.session.add_all([rec_a, rec_b, rec_c])
        db.session.commit()
        c1 = MatchCandidate(record_a_id=rec_a.id, record_b_id=rec_b.id, match_score=0.90, status="pending")
        c2 = MatchCandidate(record_a_id=rec_a.id, record_b_id=rec_c.id, match_score=0.88, status="pending")
        c3 = MatchCandidate(record_a_id=rec_b.id, record_b_id=rec_c.id, match_score=0.85, status="pending")
        db.session.add_all([c1, c2, c3])
        db.session.commit()
        c1_id, c2_id, c3_id = c1.id, c2.id, c3.id

    _login_as(client, app, "data_steward")
    _approve(client, c1_id, primary="a")
    _approve(client, c2_id, primary="a")
    # All three should now be on one golden record
    with app.app_context():
        from app.models import GoldenRecord, GoldenRecordLink
        assert GoldenRecord.query.count() == 1
        assert GoldenRecordLink.query.count() == 3


# ---------------------------------------------------------------------------
# Approval flow UX tests
# ---------------------------------------------------------------------------

def test_approve_redirects_to_match_queue(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    response = client.post(
        f"/match-candidates/{candidate_id}/approve",
        data={"primary_record": "a"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/match-queue" in response.headers["Location"]


def test_reject_redirects_to_match_queue(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    response = client.post(
        f"/match-candidates/{candidate_id}/reject",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/match-queue" in response.headers["Location"]


def test_approve_shows_single_success_message(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    response = _approve(client, candidate_id)
    # Only one success alert should appear
    assert response.data.count(b"alert-success") == 1


def test_detail_back_button_links_to_match_queue(client, app):
    candidate_id = _seed_candidate(app)
    _login(client, app)
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"/match-queue" in response.data


# ---------------------------------------------------------------------------
# Reopen / decision lifecycle tests
# ---------------------------------------------------------------------------

def test_data_steward_can_reopen_rejected_candidate(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    _post(client, f"/match-candidates/{candidate_id}/reopen")
    with app.app_context():
        c = db.session.get(MatchCandidate, candidate_id)
        assert c.status == "pending"
        assert c.reviewed_at is None
        assert c.reviewed_by_id is None


def test_reopen_rejected_candidate_creates_audit_log(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    _post(client, f"/match-candidates/{candidate_id}/reopen")
    with app.app_context():
        log = AuditLog.query.filter_by(action="match_reopened", target_id=candidate_id).first()
        assert log is not None
        assert "MC-" in log.detail


def test_reopened_candidate_returns_to_match_queue(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    response = client.get("/match-queue")
    assert f"MC-{candidate_id:04d}".encode() not in response.data
    _post(client, f"/match-candidates/{candidate_id}/reopen")
    response = client.get("/match-queue")
    assert f"MC-{candidate_id:04d}".encode() in response.data


def test_reopen_rejected_shows_single_success_message(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    response = _post(client, f"/match-candidates/{candidate_id}/reopen")
    assert response.data.count(b"alert-success") == 1


def test_data_analyst_cannot_reopen_receives_403(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    _login_as(client, app, "data_analyst")
    response = client.post(f"/match-candidates/{candidate_id}/reopen")
    assert response.status_code == 403


def test_administrator_cannot_reopen_receives_403(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    _login_as(client, app, "administrator")
    response = client.post(f"/match-candidates/{candidate_id}/reopen")
    assert response.status_code == 403


def test_reopen_pending_candidate_is_noop(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reopen")
    with app.app_context():
        c = db.session.get(MatchCandidate, candidate_id)
        assert c.status == "pending"
        assert AuditLog.query.filter_by(action="match_reopened").count() == 0


def test_reopen_approved_candidate_is_blocked(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id)
    response = _post(client, f"/match-candidates/{candidate_id}/reopen")
    assert b"cannot be reopened" in response.data
    with app.app_context():
        c = db.session.get(MatchCandidate, candidate_id)
        assert c.status == "approved"
        assert GoldenRecord.query.count() == 1
        assert AuditLog.query.filter_by(action="match_reopened").count() == 0


def test_rejected_candidate_detail_shows_reopen_button(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _post(client, f"/match-candidates/{candidate_id}/reject")
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"Reopen" in response.data
    assert f"/match-candidates/{candidate_id}/reopen".encode() in response.data


def test_approved_candidate_detail_shows_locked_message_not_reopen_button(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id)
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"Approved" in response.data
    assert b"Locked after approval" in response.data
    # No reopen form should be on the approved page
    assert f"/match-candidates/{candidate_id}/reopen".encode() not in response.data


def test_approved_candidate_hides_source_record_edit_buttons(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    _approve(client, candidate_id)
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    # Approved cards should show "Locked after approval" and not show Edit links
    assert b"Locked after approval" in response.data
    # The /edit URL for the source records should not appear in the candidate detail
    with app.app_context():
        c = db.session.get(MatchCandidate, candidate_id)
        rec_a_id = c.record_a_id
        rec_b_id = c.record_b_id
    assert f"/source-records/{rec_a_id}/edit".encode() not in response.data
    assert f"/source-records/{rec_b_id}/edit".encode() not in response.data


def test_pending_candidate_detail_shows_approve_and_reject(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    response = client.get(f"/match-candidates/{candidate_id}")
    assert response.status_code == 200
    assert b"Approve &amp; Create Golden Record" in response.data
    assert b"Reject Match" in response.data


def test_reject_shows_single_success_message(client, app):
    candidate_id = _seed_pending_candidate(app)
    _login_as(client, app, "data_steward")
    response = _post(client, f"/match-candidates/{candidate_id}/reject")
    assert response.data.count(b"alert-success") == 1
