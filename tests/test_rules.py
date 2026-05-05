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


def test_unauthenticated_rules_redirects_to_login(client):
    response = client.get("/rules", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_data_analyst_receives_403_for_rules(client, app):
    _create_and_login(client, app, "analyst", "analyst@example.com", "data_analyst")
    response = client.get("/rules")
    assert response.status_code == 403


def test_data_steward_receives_403_for_rules(client, app):
    _create_and_login(client, app, "steward", "steward@example.com", "data_steward")
    response = client.get("/rules")
    assert response.status_code == 403


def test_administrator_can_access_rules(client, app):
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.get("/rules")
    assert response.status_code == 200
    assert b"Rule management will be added in a later development stage" in response.data


def test_403_page_renders_useful_text(client, app):
    _create_and_login(client, app, "steward", "steward@example.com", "data_steward")
    response = client.get("/rules")
    assert response.status_code == 403
    assert b"403" in response.data
    assert b"Access Denied" in response.data
    assert b"Back to Dashboard" in response.data
