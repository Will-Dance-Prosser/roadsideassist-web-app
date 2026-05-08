import pytest
from app import create_app
from app.extensions import db
from app.models import SourceRecord, SourceSystem, User
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


def _seed_record(app):
    """Create a source system and one source record for testing."""
    with app.app_context():
        system = SourceSystem(name="CRM", description="Test CRM")
        db.session.add(system)
        db.session.commit()

        record = SourceRecord(
            source_system_id=system.id,
            external_id="CRM-001",
            first_name="John",
            last_name="Smith",
            email="john.smith@example.com",
            postcode="SW1A 1AA",
            phone="07700900001",
        )
        db.session.add(record)
        db.session.commit()


def _login(client, app, role="data_steward"):
    with app.app_context():
        user = User(username="testuser", email="test@example.com", role=role)
        user.set_password("test-password")
        db.session.add(user)
        db.session.commit()
    client.post(
        "/login",
        data={"username": "testuser", "password": "test-password"},
        follow_redirects=True,
    )


def test_unauthenticated_source_records_redirects_to_login(client):
    response = client.get("/source-records", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logged_in_user_can_access_source_records(client, app):
    _login(client, app)
    response = client.get("/source-records")
    assert response.status_code == 200
    assert b"Source Records" in response.data


def test_source_records_page_renders_record_from_database(client, app):
    _seed_record(app)
    _login(client, app)
    response = client.get("/source-records")
    assert response.status_code == 200
    assert b"CRM-001" in response.data
    assert b"John" in response.data
    assert b"Smith" in response.data
    assert b"CRM" in response.data


def test_all_roles_can_access_source_records(client, app):
    for role in ("administrator", "data_steward", "data_analyst"):
        inner_app = create_app(TestingConfig)
        with inner_app.app_context():
            db.create_all()
            user = User(username=role, email=f"{role}@example.com", role=role)
            user.set_password("test-password")
            db.session.add(user)
            db.session.commit()

        inner_client = inner_app.test_client()
        inner_client.post(
            "/login",
            data={"username": role, "password": "test-password"},
            follow_redirects=True,
        )
        response = inner_client.get("/source-records")
        assert response.status_code == 200, f"{role} should be able to access /source-records"

        with inner_app.app_context():
            db.session.remove()
            db.drop_all()
