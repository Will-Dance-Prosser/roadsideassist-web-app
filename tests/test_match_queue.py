import pytest
from app import create_app
from app.extensions import db
from app.models import MatchCandidate, SourceRecord, SourceSystem, User
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
