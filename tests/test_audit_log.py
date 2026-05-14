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


def _seed_audit_entry(app):
    with app.app_context():
        entry = AuditLog(
            action="match_approved",
            target_type="match_candidate",
            target_id=42,
            detail="Demo audit entry for testing",
        )
        db.session.add(entry)
        db.session.commit()


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
