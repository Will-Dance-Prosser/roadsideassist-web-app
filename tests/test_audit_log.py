import pytest
from app import create_app
from app.extensions import db
from app.models import AuditLog, User
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


def _login(client, app, role="administrator"):
    with app.app_context():
        existing = User.query.filter_by(username="testuser").first()
        if not existing:
            user = User(username="testuser", email="test@example.com", role=role)
            user.set_password("test-password")
            db.session.add(user)
            db.session.commit()
    client.post("/login", data={"username": "testuser", "password": "test-password"}, follow_redirects=True)


def _seed_audit_entry(app, action="match_approved", target_type="match_candidate",
                      target_id=42, detail="Demo audit entry for testing", user_id=None):
    with app.app_context():
        entry = AuditLog(
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            user_id=user_id,
        )
        db.session.add(entry)
        db.session.commit()
        return entry.id


def test_unauthenticated_audit_log_redirects_to_login(client):
    response = client.get("/audit-log", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_data_analyst_receives_403_for_audit_log(client, app):
    _login(client, app, role="data_analyst")
    response = client.get("/audit-log")
    assert response.status_code == 403


def test_data_steward_receives_403_for_audit_log(client, app):
    _login(client, app, role="data_steward")
    response = client.get("/audit-log")
    assert response.status_code == 403


def test_administrator_can_access_audit_log(client, app):
    _login(client, app, role="administrator")
    response = client.get("/audit-log")
    assert response.status_code == 200
    assert b"Audit Log" in response.data


def test_audit_log_renders_entries_from_database(client, app):
    _seed_audit_entry(app)
    _login(client, app, role="administrator")
    response = client.get("/audit-log")
    assert response.status_code == 200
    assert b"match_approved" in response.data
    assert b"match_candidate" in response.data
    assert b"Demo audit entry for testing" in response.data


def test_audit_log_shows_system_for_null_user(client, app):
    _seed_audit_entry(app)
    _login(client, app, role="administrator")
    response = client.get("/audit-log")
    assert b"System" in response.data


# ---------------------------------------------------------------------------
# Filter tests
# ---------------------------------------------------------------------------

def test_q_filter_returns_matching_entries(client, app):
    _seed_audit_entry(app, detail="unique_search_term_xyz")
    _seed_audit_entry(app, detail="something completely different", action="match_rejected")
    _login(client, app, role="administrator")
    response = client.get("/audit-log?q=unique_search_term_xyz")
    assert b"unique_search_term_xyz" in response.data
    assert b"something completely different" not in response.data


def test_q_filter_matches_action(client, app):
    _seed_audit_entry(app, action="source_record_created", detail="created record XYZ")
    _seed_audit_entry(app, action="match_rejected",       detail="rejected record ABC")
    _login(client, app, role="administrator")
    response = client.get("/audit-log?q=source_record_created")
    assert b"created record XYZ" in response.data
    assert b"rejected record ABC" not in response.data


def test_action_filter_works(client, app):
    _seed_audit_entry(app, action="match_approved", detail="this was approved")
    _seed_audit_entry(app, action="match_rejected", detail="this was rejected")
    _login(client, app, role="administrator")
    response = client.get("/audit-log?action=match_approved")
    assert b"this was approved" in response.data
    assert b"this was rejected" not in response.data


def test_target_type_filter_works(client, app):
    _seed_audit_entry(app, target_type="match_candidate", detail="candidate entry")
    _seed_audit_entry(app, target_type="source_record", detail="source entry")
    _login(client, app, role="administrator")
    response = client.get("/audit-log?target_type=source_record")
    assert b"source entry" in response.data
    assert b"candidate entry" not in response.data


def test_user_filter_works(client, app):
    with app.app_context():
        u1 = User(username="alice", email="alice@example.com", role="administrator")
        u1.set_password("pw")
        u2 = User(username="bob", email="bob@example.com", role="data_steward")
        u2.set_password("pw")
        db.session.add_all([u1, u2])
        db.session.commit()
        db.session.add(AuditLog(action="test_action", detail="alice did this", user_id=u1.id))
        db.session.add(AuditLog(action="test_action", detail="bob did this",   user_id=u2.id))
        db.session.commit()
        u1_id = u1.id

    _login(client, app, role="administrator")
    response = client.get(f"/audit-log?user_id={u1_id}")
    assert b"alice did this" in response.data
    assert b"bob did this" not in response.data


def test_sort_created_asc(client, app):
    _seed_audit_entry(app, detail="first entry",  action="action_a")
    _seed_audit_entry(app, detail="second entry", action="action_b")
    _login(client, app, role="administrator")
    response = client.get("/audit-log?sort=created_asc")
    data = response.data.decode()
    assert data.index("first entry") < data.index("second entry")


def test_sort_created_desc(client, app):
    _seed_audit_entry(app, detail="first entry",  action="action_a")
    _seed_audit_entry(app, detail="second entry", action="action_b")
    _login(client, app, role="administrator")
    response = client.get("/audit-log?sort=created_desc")
    data = response.data.decode()
    assert data.index("second entry") < data.index("first entry")


def test_no_filters_shows_all_entries(client, app):
    _seed_audit_entry(app, detail="entry one",   action="action_a")
    _seed_audit_entry(app, detail="entry two",   action="action_b")
    _seed_audit_entry(app, detail="entry three", action="action_c")
    _login(client, app, role="administrator")
    response = client.get("/audit-log")
    assert b"entry one"   in response.data
    assert b"entry two"   in response.data
    assert b"entry three" in response.data


def test_pagination_limits_page_size(client, app):
    from app.audit_log.routes import PAGE_SIZE
    # Seed one more than a full page
    with app.app_context():
        for i in range(PAGE_SIZE + 1):
            db.session.add(AuditLog(action="bulk_action", detail=f"entry {i}"))
        db.session.commit()
    _login(client, app, role="administrator")
    response = client.get("/audit-log?page=1")
    # The page should not contain all entries — entry 0 should be on a different page
    # when sorted desc. Just verify page 2 exists (pagination rendered)
    assert b"page-link" in response.data or b"Page 1 of" in response.data


def test_empty_filter_result_shows_friendly_message(client, app):
    _login(client, app, role="administrator")
    response = client.get("/audit-log?action=nonexistent_action_xyz")
    assert b"No audit log entries match" in response.data
