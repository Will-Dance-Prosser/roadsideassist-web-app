import pytest
from app import create_app
from app.extensions import db
from app.models import User
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


@pytest.fixture
def active_user(app):
    with app.app_context():
        user = User(username="steward", email="steward@example.com", role="data_steward")
        user.set_password("correct-password")
        db.session.add(user)
        db.session.commit()
    return user


@pytest.fixture
def inactive_user(app):
    with app.app_context():
        user = User(
            username="inactive",
            email="inactive@example.com",
            role="data_steward",
            is_active=False,
        )
        user.set_password("some-password")
        db.session.add(user)
        db.session.commit()
    return user


def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"MemberMatch" in response.data
    assert b"Sign in" in response.data


def test_unauthenticated_dashboard_redirects_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_valid_login_redirects_to_dashboard(client, active_user):
    response = client.post(
        "/login",
        data={"username": "steward", "password": "correct-password"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Match Review Dashboard" in response.data


def test_invalid_password_does_not_log_in(client, active_user):
    response = client.post(
        "/login",
        data={"username": "steward", "password": "wrong-password"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data
    assert b"Match Review Dashboard" not in response.data


def test_unknown_user_does_not_log_in(client):
    response = client.post(
        "/login",
        data={"username": "nobody", "password": "anything"},
        follow_redirects=True,
    )
    assert b"Invalid username or password" in response.data


def test_inactive_user_cannot_log_in(client, inactive_user):
    response = client.post(
        "/login",
        data={"username": "inactive", "password": "some-password"},
        follow_redirects=True,
    )
    assert b"Invalid username or password" in response.data
    assert b"Match Review Dashboard" not in response.data


def test_logout_redirects_to_login(client, active_user):
    client.post(
        "/login",
        data={"username": "steward", "password": "correct-password"},
        follow_redirects=True,
    )
    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"Sign in" in response.data


def test_user_model_password_hashing(app):
    with app.app_context():
        user = User(username="testuser", email="test@example.com", role="data_steward")
        user.set_password("correct-password")

        assert user.password_hash != "correct-password"
        assert user.check_password("correct-password") is True
        assert user.check_password("wrong-password") is False

