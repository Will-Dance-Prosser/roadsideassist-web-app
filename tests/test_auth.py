from app import create_app
from app.extensions import db
from app.models import User
from config import TestingConfig


def test_login_page_loads():
    app = create_app(TestingConfig)

    client = app.test_client()
    response = client.get("/login")

    assert response.status_code == 200
    assert b"MemberMatch" in response.data
    assert b"Sign in" in response.data


def test_user_model_password_hashing():
    app = create_app(TestingConfig)

    with app.app_context():
        db.create_all()

        user = User(username="teststeward", email="steward@example.com", role="data_steward")
        user.set_password("correct-password")

        assert user.password_hash != "correct-password"
        assert user.check_password("correct-password") is True
        assert user.check_password("wrong-password") is False
