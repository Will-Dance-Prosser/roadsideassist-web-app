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
        user = User(username="steward", email="steward@example.com", role="data_steward")
        user.set_password("correct-password")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


def test_dashboard_page_loads(app):
    client = app.test_client()

    client.post(
        "/login",
        data={"username": "steward", "password": "correct-password"},
        follow_redirects=True,
    )

    response = client.get("/")
    assert response.status_code == 200
    assert b"MemberMatch" in response.data
    assert b"Match Review Dashboard" in response.data
