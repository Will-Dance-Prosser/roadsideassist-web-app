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


def _seed_golden_record(app):
    """Create a golden record with two source record links."""
    with app.app_context():
        system = SourceSystem(name="CRM")
        db.session.add(system)
        db.session.commit()

        rec_a = SourceRecord(source_system_id=system.id, external_id="CRM-001", first_name="John", last_name="Smith", email="john@example.com")
        rec_b = SourceRecord(source_system_id=system.id, external_id="CRM-002", first_name="J.", last_name="Smith", email="john@example.com")
        db.session.add_all([rec_a, rec_b])
        db.session.commit()

        golden = GoldenRecord(first_name="John", last_name="Smith", email="john@example.com")
        db.session.add(golden)
        db.session.flush()

        db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=rec_a.id))
        db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=rec_b.id))
        db.session.commit()
        return golden.id


def test_unauthenticated_golden_records_redirects_to_login(client):
    response = client.get("/golden-records", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logged_in_user_can_access_golden_records(client, app):
    _login(client, app)
    response = client.get("/golden-records")
    assert response.status_code == 200
    assert b"Golden Records" in response.data


def test_golden_records_page_renders_record_from_database(client, app):
    _seed_golden_record(app)
    _login(client, app)
    response = client.get("/golden-records")
    assert response.status_code == 200
    assert b"John" in response.data
    assert b"Smith" in response.data
    assert b"GR-" in response.data


def test_golden_records_shows_linked_source_record_count(client, app):
    _seed_golden_record(app)
    _login(client, app)
    response = client.get("/golden-records")
    assert b"2" in response.data


# --- Detail page ---

def test_unauthenticated_golden_record_detail_redirects_to_login(client, app):
    golden_id = _seed_golden_record(app)
    response = client.get(f"/golden-records/{golden_id}", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logged_in_user_can_view_golden_record_detail(client, app):
    golden_id = _seed_golden_record(app)
    _login(client, app)
    response = client.get(f"/golden-records/{golden_id}")
    assert response.status_code == 200


def test_golden_record_detail_renders_golden_record_fields(client, app):
    golden_id = _seed_golden_record(app)
    _login(client, app)
    response = client.get(f"/golden-records/{golden_id}")
    assert response.status_code == 200
    assert b"John" in response.data
    assert b"Smith" in response.data
    assert b"john@example.com" in response.data
    assert b"GR-" in response.data


def test_golden_record_detail_renders_linked_source_records(client, app):
    golden_id = _seed_golden_record(app)
    _login(client, app)
    response = client.get(f"/golden-records/{golden_id}")
    assert response.status_code == 200
    assert b"CRM-001" in response.data
    assert b"CRM-002" in response.data
    assert b"CRM" in response.data


def test_missing_golden_record_returns_404(client, app):
    _login(client, app)
    response = client.get("/golden-records/99999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------

def _login_as(client, app, role):
    username = f"user_{role}"
    with app.app_context():
        if not User.query.filter_by(username=username).first():
            u = User(username=username, email=f"{username}@example.com", role=role)
            u.set_password("pw")
            db.session.add(u)
            db.session.commit()
    client.post("/login", data={"username": username, "password": "pw"}, follow_redirects=True)


def test_administrator_can_delete_golden_record(client, app):
    golden_id = _seed_golden_record(app)
    _login_as(client, app, "administrator")
    response = client.post(f"/golden-records/{golden_id}/delete",
                           data={"confirmation": "DELETE"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(GoldenRecord, golden_id) is None


def test_golden_record_links_are_removed_on_delete(client, app):
    golden_id = _seed_golden_record(app)
    _login_as(client, app, "administrator")
    client.post(f"/golden-records/{golden_id}/delete", data={"confirmation": "DELETE"})
    with app.app_context():
        assert GoldenRecordLink.query.filter_by(golden_record_id=golden_id).count() == 0


def test_source_records_are_not_deleted(client, app):
    _seed_golden_record(app)
    with app.app_context():
        golden_id = GoldenRecord.query.first().id
    _login_as(client, app, "administrator")
    client.post(f"/golden-records/{golden_id}/delete", data={"confirmation": "DELETE"})
    with app.app_context():
        assert SourceRecord.query.count() == 2


def test_match_candidates_are_not_deleted(client, app):
    with app.app_context():
        system = SourceSystem(name="MCCRM")
        db.session.add(system)
        db.session.flush()
        r1 = SourceRecord(source_system_id=system.id, external_id="MC-1", first_name="A", last_name="A")
        r2 = SourceRecord(source_system_id=system.id, external_id="MC-2", first_name="B", last_name="B")
        db.session.add_all([r1, r2])
        db.session.flush()
        candidate = MatchCandidate(record_a_id=r1.id, record_b_id=r2.id, match_score=0.9)
        db.session.add(candidate)
        db.session.flush()
        golden = GoldenRecord(first_name="A", last_name="A")
        db.session.add(golden)
        db.session.flush()
        db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=r1.id))
        db.session.commit()
        golden_id = golden.id

    _login_as(client, app, "administrator")
    client.post(f"/golden-records/{golden_id}/delete", data={"confirmation": "DELETE"})
    with app.app_context():
        assert MatchCandidate.query.count() == 1


def test_audit_log_entry_created_on_delete(client, app):
    golden_id = _seed_golden_record(app)
    _login_as(client, app, "administrator")
    client.post(f"/golden-records/{golden_id}/delete", data={"confirmation": "DELETE"})
    with app.app_context():
        entry = AuditLog.query.filter_by(action="golden_record_deleted").first()
        assert entry is not None
        assert str(golden_id) in entry.detail


def test_wrong_confirmation_does_not_delete_golden_record(client, app):
    golden_id = _seed_golden_record(app)
    _login_as(client, app, "administrator")
    client.post(f"/golden-records/{golden_id}/delete", data={"confirmation": "delete"})
    with app.app_context():
        assert db.session.get(GoldenRecord, golden_id) is not None


def test_data_steward_cannot_delete_golden_record(client, app):
    golden_id = _seed_golden_record(app)
    _login_as(client, app, "data_steward")
    response = client.post(f"/golden-records/{golden_id}/delete", data={"confirmation": "DELETE"})
    assert response.status_code == 403


def test_data_analyst_cannot_delete_golden_record(client, app):
    golden_id = _seed_golden_record(app)
    _login_as(client, app, "data_analyst")
    response = client.post(f"/golden-records/{golden_id}/delete", data={"confirmation": "DELETE"})
    assert response.status_code == 403


def test_delete_is_post_only(client, app):
    golden_id = _seed_golden_record(app)
    _login_as(client, app, "administrator")
    response = client.get(f"/golden-records/{golden_id}/delete")
    assert response.status_code == 405


def test_delete_controls_hidden_from_non_admin(client, app):
    golden_id = _seed_golden_record(app)
    _login_as(client, app, "data_steward")
    response = client.get(f"/golden-records/{golden_id}")
    assert b"Permanent Deletion" not in response.data
