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


def _create_and_login(client, app, username, email, role):
    """Helper: create a user with the given role and log them in."""
    with app.app_context():
        user = User(username=username, email=email, role=role)
        user.set_password("test-password")
        db.session.add(user)
        db.session.commit()
    client.post(
        "/login",
        data={"username": username, "password": "test-password"},
        follow_redirects=True,
    )


def _admin_login(client, app):
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")


def _post_create(client, **overrides):
    """POST to create_user with sensible defaults; override any field as needed."""
    data = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "secure-pass-1",
        "confirm_password": "secure-pass-1",
        "role": "data_steward",
        "is_active": "y",
    }
    data.update(overrides)
    return client.post("/admin/users/create", data=data, follow_redirects=True)


# ── Access control ───────────────────────────────────────────────────────────

def test_unauthenticated_users_cannot_view_user_management(client):
    response = client.get("/admin/users", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_analyst_cannot_view_user_management(client, app):
    _create_and_login(client, app, "analyst", "analyst@example.com", "data_analyst")
    response = client.get("/admin/users")
    assert response.status_code == 403


def test_steward_cannot_view_user_management(client, app):
    _create_and_login(client, app, "steward", "steward@example.com", "data_steward")
    response = client.get("/admin/users")
    assert response.status_code == 403


def test_admin_can_view_user_management(client, app):
    _admin_login(client, app)
    response = client.get("/admin/users")
    assert response.status_code == 200
    assert b"User Management" in response.data


def test_unauthenticated_users_cannot_access_create_user(client):
    response = client.get("/admin/users/create", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_steward_cannot_access_create_user(client, app):
    _create_and_login(client, app, "steward", "steward@example.com", "data_steward")
    response = client.get("/admin/users/create")
    assert response.status_code == 403


# ── User creation ────────────────────────────────────────────────────────────

def test_admin_can_create_user(client, app):
    _admin_login(client, app)
    response = _post_create(client)
    assert response.status_code == 200
    assert b"created successfully" in response.data
    with app.app_context():
        user = User.query.filter_by(username="newuser").first()
        assert user is not None
        assert user.role == "data_steward"
        assert user.is_active is True


def test_duplicate_username_rejected(client, app):
    _admin_login(client, app)
    _post_create(client)
    response = _post_create(client, email="other@example.com")
    assert b"already taken" in response.data
    with app.app_context():
        assert User.query.filter_by(username="newuser").count() == 1


def test_password_mismatch_rejected(client, app):
    _admin_login(client, app)
    response = _post_create(client, confirm_password="different-pass")
    assert b"Passwords do not match" in response.data
    with app.app_context():
        assert User.query.filter_by(username="newuser").first() is None


def test_invalid_role_rejected(client, app):
    _admin_login(client, app)
    response = _post_create(client, role="superuser")
    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(username="newuser").first() is None


def test_short_password_rejected(client, app):
    _admin_login(client, app)
    response = _post_create(client, password="short", confirm_password="short")
    assert b"at least 8 characters" in response.data
    with app.app_context():
        assert User.query.filter_by(username="newuser").first() is None


def test_created_user_can_log_in(client, app):
    _admin_login(client, app)
    _post_create(client)
    client.get("/logout")
    response = client.post(
        "/login",
        data={"username": "newuser", "password": "secure-pass-1"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Match Review Dashboard" in response.data


def test_created_user_has_selected_role(client, app):
    _admin_login(client, app)
    _post_create(client, role="data_analyst")
    with app.app_context():
        user = User.query.filter_by(username="newuser").first()
        assert user.role == "data_analyst"


def test_user_creation_creates_audit_log(client, app):
    _admin_login(client, app)
    _post_create(client)
    with app.app_context():
        log = AuditLog.query.filter_by(action="user_created").first()
        assert log is not None
        assert log.target_type == "user"
        assert "newuser" in log.detail
