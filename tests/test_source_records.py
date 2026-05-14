import pytest
from datetime import date
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


# ---------------------------------------------------------------------------
# Helpers for CRUD tests
# ---------------------------------------------------------------------------

def _seed_system(app):
    """Seed a SourceSystem and return its id."""
    with app.app_context():
        system = SourceSystem(name="CRM", description="Test CRM")
        db.session.add(system)
        db.session.commit()
        return system.id


def _login_as(client, app, role):
    username = f"user_{role}"
    with app.app_context():
        if not User.query.filter_by(username=username).first():
            u = User(username=username, email=f"{username}@example.com", role=role)
            u.set_password("pw")
            db.session.add(u)
            db.session.commit()
    client.post("/login", data={"username": username, "password": "pw"}, follow_redirects=True)


def _form_data(system_id, external_id="NEW-001"):
    return {
        "source_system_id": system_id,
        "external_id": external_id,
        "first_name": "Test",
        "last_name": "User",
        "email": "",
        "postcode": "",
        "phone": "",
        "raw_data": "",
    }


# ---------------------------------------------------------------------------
# Create tests
# ---------------------------------------------------------------------------

def test_data_analyst_cannot_access_create_form(client, app):
    _login_as(client, app, "data_analyst")
    response = client.get("/source-records/new")
    assert response.status_code == 403


def test_data_analyst_cannot_post_create(client, app):
    system_id = _seed_system(app)
    _login_as(client, app, "data_analyst")
    response = client.post("/source-records/new", data=_form_data(system_id))
    assert response.status_code == 403


def test_data_steward_can_create_source_record(client, app):
    system_id = _seed_system(app)
    _login_as(client, app, "data_steward")
    response = client.post(
        "/source-records/new",
        data=_form_data(system_id, "NEW-001"),
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert SourceRecord.query.filter_by(external_id="NEW-001").first() is not None


def test_administrator_can_create_source_record(client, app):
    system_id = _seed_system(app)
    _login_as(client, app, "administrator")
    response = client.post(
        "/source-records/new",
        data=_form_data(system_id, "NEW-002"),
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert SourceRecord.query.filter_by(external_id="NEW-002").first() is not None


def test_create_requires_external_id(client, app):
    system_id = _seed_system(app)
    _login_as(client, app, "data_steward")
    data = _form_data(system_id)
    data["external_id"] = ""
    response = client.post("/source-records/new", data=data)
    assert response.status_code == 200
    with app.app_context():
        assert SourceRecord.query.count() == 0


def test_create_requires_at_least_one_name(client, app):
    system_id = _seed_system(app)
    _login_as(client, app, "data_steward")
    data = _form_data(system_id)
    data["first_name"] = ""
    data["last_name"] = ""
    response = client.post("/source-records/new", data=data)
    assert response.status_code == 200
    assert b"First Name or Last Name" in response.data
    with app.app_context():
        assert SourceRecord.query.count() == 0


def test_create_rejects_duplicate_external_id(client, app):
    system_id = _seed_system(app)
    _login_as(client, app, "data_steward")
    client.post("/source-records/new", data=_form_data(system_id, "DUP-001"), follow_redirects=True)
    response = client.post("/source-records/new", data=_form_data(system_id, "DUP-001"), follow_redirects=True)
    assert response.status_code == 200
    assert b"already exists" in response.data
    with app.app_context():
        assert SourceRecord.query.filter_by(external_id="DUP-001").count() == 1


def test_create_rejects_invalid_email(client, app):
    system_id = _seed_system(app)
    _login_as(client, app, "data_steward")
    data = _form_data(system_id, "EML-001")
    data["email"] = "not-an-email"
    response = client.post("/source-records/new", data=data)
    assert response.status_code == 200
    with app.app_context():
        assert SourceRecord.query.count() == 0


# ---------------------------------------------------------------------------
# Edit tests
# ---------------------------------------------------------------------------

def _seed_record_with_system(app):
    with app.app_context():
        system = SourceSystem(name="CRM", description="Test CRM")
        db.session.add(system)
        db.session.flush()
        record = SourceRecord(
            source_system_id=system.id,
            external_id="EDIT-001",
            first_name="Jane",
            last_name="Doe",
        )
        db.session.add(record)
        db.session.commit()
        return record.id, system.id


def test_steward_can_edit_source_record(client, app):
    record_id, system_id = _seed_record_with_system(app)
    _login_as(client, app, "data_steward")
    data = _form_data(system_id, "EDIT-001")
    data["first_name"] = "Updated"
    response = client.post(f"/source-records/{record_id}/edit", data=data, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        updated = db.session.get(SourceRecord, record_id)
        assert updated.first_name == "Updated"


def test_edit_rejects_duplicate_external_id_on_another_record(client, app):
    with app.app_context():
        system = SourceSystem(name="CRM2")
        db.session.add(system)
        db.session.flush()
        r1 = SourceRecord(source_system_id=system.id, external_id="R-001", first_name="A", last_name="A")
        r2 = SourceRecord(source_system_id=system.id, external_id="R-002", first_name="B", last_name="B")
        db.session.add_all([r1, r2])
        db.session.commit()
        r2_id = r2.id
        system_id = system.id

    _login_as(client, app, "data_steward")
    data = _form_data(system_id, "R-001")  # try to use R-001 which belongs to r1
    data["first_name"] = "B"
    data["last_name"] = "B"
    response = client.post(f"/source-records/{r2_id}/edit", data=data, follow_redirects=True)
    assert b"already exists" in response.data


def test_edit_missing_record_returns_404(client, app):
    _login_as(client, app, "data_steward")
    response = client.get("/source-records/99999/edit")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Archive tests
# ---------------------------------------------------------------------------

def test_steward_can_archive_source_record(client, app):
    record_id, _ = _seed_record_with_system(app)
    _login_as(client, app, "data_steward")
    response = client.post(f"/source-records/{record_id}/archive", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        record = db.session.get(SourceRecord, record_id)
        assert record.is_archived is True
        assert record.archived_at is not None


def test_archive_is_post_only(client, app):
    record_id, _ = _seed_record_with_system(app)
    _login_as(client, app, "data_steward")
    response = client.get(f"/source-records/{record_id}/archive")
    assert response.status_code == 405


def test_data_analyst_cannot_archive(client, app):
    record_id, _ = _seed_record_with_system(app)
    _login_as(client, app, "data_analyst")
    response = client.post(f"/source-records/{record_id}/archive")
    assert response.status_code == 403

