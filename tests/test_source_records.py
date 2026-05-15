import pytest
from datetime import date, datetime
from app import create_app
from app.extensions import db
from app.models import GoldenRecord, GoldenRecordLink, MatchCandidate, SourceRecord, SourceSystem, User
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


# ---------------------------------------------------------------------------
# Status filter tests
# ---------------------------------------------------------------------------

def _seed_active_and_archived(app):
    """Seed one active and one archived source record."""
    with app.app_context():
        system = SourceSystem(name="FilterCRM")
        db.session.add(system)
        db.session.flush()
        active = SourceRecord(source_system_id=system.id, external_id="ACTIVE-001", first_name="Alice", last_name="A")
        archived = SourceRecord(source_system_id=system.id, external_id="ARCHIVED-001", first_name="Bob", last_name="B",
                                is_archived=True, archived_at=datetime.utcnow())
        db.session.add_all([active, archived])
        db.session.commit()


def test_default_view_shows_active_records_only(client, app):
    _seed_active_and_archived(app)
    _login_as(client, app, "data_steward")
    response = client.get("/source-records")
    assert response.status_code == 200
    assert b"ACTIVE-001" in response.data
    assert b"ARCHIVED-001" not in response.data


def test_status_archived_shows_archived_records(client, app):
    _seed_active_and_archived(app)
    _login_as(client, app, "data_steward")
    response = client.get("/source-records?status=archived")
    assert response.status_code == 200
    assert b"ARCHIVED-001" in response.data
    assert b"ACTIVE-001" not in response.data


def test_status_all_shows_all_records(client, app):
    _seed_active_and_archived(app)
    _login_as(client, app, "data_steward")
    response = client.get("/source-records?status=all")
    assert response.status_code == 200
    assert b"ACTIVE-001" in response.data
    assert b"ARCHIVED-001" in response.data


# ---------------------------------------------------------------------------
# Unarchive tests
# ---------------------------------------------------------------------------

def _seed_archived_record(app):
    with app.app_context():
        system = SourceSystem(name="RestoreCRM")
        db.session.add(system)
        db.session.flush()
        record = SourceRecord(source_system_id=system.id, external_id="RESTORE-001", first_name="Carol", last_name="C",
                              is_archived=True, archived_at=datetime.utcnow())
        db.session.add(record)
        db.session.commit()
        return record.id


def test_administrator_can_unarchive(client, app):
    record_id = _seed_archived_record(app)
    _login_as(client, app, "administrator")
    response = client.post(f"/source-records/{record_id}/unarchive", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        record = db.session.get(SourceRecord, record_id)
        assert record.is_archived is False
        assert record.archived_at is None


def test_data_steward_cannot_unarchive(client, app):
    record_id = _seed_archived_record(app)
    _login_as(client, app, "data_steward")
    response = client.post(f"/source-records/{record_id}/unarchive")
    assert response.status_code == 403


def test_data_analyst_cannot_unarchive(client, app):
    record_id = _seed_archived_record(app)
    _login_as(client, app, "data_analyst")
    response = client.post(f"/source-records/{record_id}/unarchive")
    assert response.status_code == 403


def test_unarchive_is_post_only(client, app):
    record_id = _seed_archived_record(app)
    _login_as(client, app, "administrator")
    response = client.get(f"/source-records/{record_id}/unarchive")
    assert response.status_code == 405


# ---------------------------------------------------------------------------
# Permanent delete tests
# ---------------------------------------------------------------------------

def _seed_clean_archived_record(app):
    """Archived record with no match or golden record links."""
    with app.app_context():
        system = SourceSystem(name="DelCRM")
        db.session.add(system)
        db.session.flush()
        record = SourceRecord(
            source_system_id=system.id, external_id="DEL-001",
            first_name="Dave", last_name="D",
            is_archived=True, archived_at=datetime.utcnow(),
        )
        db.session.add(record)
        db.session.commit()
        return record.id


def test_archived_record_cannot_be_edited(client, app):
    record_id = _seed_archived_record(app)
    _login_as(client, app, "data_steward")
    response = client.get(f"/source-records/{record_id}/edit", follow_redirects=True)
    assert b"cannot be edited" in response.data


def test_administrator_cannot_delete_active_record(client, app):
    record_id, _ = _seed_record_with_system(app)
    _login_as(client, app, "administrator")
    response = client.post(f"/source-records/{record_id}/delete",
                           data={"confirmation": "DELETE"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(SourceRecord, record_id) is not None


def test_administrator_cannot_delete_record_with_match_candidate_link(client, app):
    with app.app_context():
        system = SourceSystem(name="MatchCRM")
        db.session.add(system)
        db.session.flush()
        r1 = SourceRecord(source_system_id=system.id, external_id="MC-A", first_name="A", last_name="A",
                          is_archived=True, archived_at=datetime.utcnow())
        r2 = SourceRecord(source_system_id=system.id, external_id="MC-B", first_name="B", last_name="B")
        db.session.add_all([r1, r2])
        db.session.flush()
        candidate = MatchCandidate(record_a_id=r1.id, record_b_id=r2.id, match_score=0.9)
        db.session.add(candidate)
        db.session.commit()
        r1_id = r1.id

    _login_as(client, app, "administrator")
    response = client.post(f"/source-records/{r1_id}/delete",
                           data={"confirmation": "DELETE"}, follow_redirects=True)
    assert b"match or golden record history" in response.data
    with app.app_context():
        assert db.session.get(SourceRecord, r1_id) is not None


def test_administrator_cannot_delete_record_with_golden_record_link(client, app):
    with app.app_context():
        system = SourceSystem(name="GoldenCRM")
        db.session.add(system)
        db.session.flush()
        record = SourceRecord(source_system_id=system.id, external_id="GR-A", first_name="G", last_name="G",
                              is_archived=True, archived_at=datetime.utcnow())
        db.session.add(record)
        db.session.flush()
        golden = GoldenRecord(first_name="G", last_name="G")
        db.session.add(golden)
        db.session.flush()
        db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=record.id))
        db.session.commit()
        record_id = record.id

    _login_as(client, app, "administrator")
    response = client.post(f"/source-records/{record_id}/delete",
                           data={"confirmation": "DELETE"}, follow_redirects=True)
    assert b"match or golden record history" in response.data
    with app.app_context():
        assert db.session.get(SourceRecord, record_id) is not None


def test_administrator_can_permanently_delete_clean_archived_record(client, app):
    record_id = _seed_clean_archived_record(app)
    _login_as(client, app, "administrator")
    response = client.post(f"/source-records/{record_id}/delete",
                           data={"confirmation": "DELETE"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(SourceRecord, record_id) is None


def test_wrong_confirmation_does_not_delete(client, app):
    record_id = _seed_clean_archived_record(app)
    _login_as(client, app, "administrator")
    response = client.post(f"/source-records/{record_id}/delete",
                           data={"confirmation": "delete"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(SourceRecord, record_id) is not None


def test_delete_is_post_only(client, app):
    record_id = _seed_clean_archived_record(app)
    _login_as(client, app, "administrator")
    response = client.get(f"/source-records/{record_id}/delete")
    assert response.status_code == 405


def test_data_steward_cannot_delete(client, app):
    record_id = _seed_clean_archived_record(app)
    _login_as(client, app, "data_steward")
    response = client.post(f"/source-records/{record_id}/delete",
                           data={"confirmation": "DELETE"})
    assert response.status_code == 403


def test_data_analyst_cannot_delete(client, app):
    record_id = _seed_clean_archived_record(app)
    _login_as(client, app, "data_analyst")
    response = client.post(f"/source-records/{record_id}/delete",
                           data={"confirmation": "DELETE"})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Delete eligibility display tests
# ---------------------------------------------------------------------------

def test_detail_shows_delete_form_for_clean_archived_record(client, app):
    record_id = _seed_clean_archived_record(app)
    _login_as(client, app, "administrator")
    response = client.get(f"/source-records/{record_id}")
    assert response.status_code == 200
    # delete form should be present
    assert b"Permanently Delete" in response.data
    assert b'name="confirmation"' in response.data


def test_detail_shows_blocked_state_for_linked_archived_record(client, app):
    with app.app_context():
        system = SourceSystem(name="BlockCRM")
        db.session.add(system)
        db.session.flush()
        r1 = SourceRecord(source_system_id=system.id, external_id="BLK-A", first_name="X", last_name="X",
                          is_archived=True, archived_at=datetime.utcnow())
        r2 = SourceRecord(source_system_id=system.id, external_id="BLK-B", first_name="Y", last_name="Y")
        db.session.add_all([r1, r2])
        db.session.flush()
        mc = MatchCandidate(record_a_id=r1.id, record_b_id=r2.id, match_score=0.8)
        db.session.add(mc)
        db.session.commit()
        r1_id = r1.id
        mc_id = mc.id

    _login_as(client, app, "administrator")
    response = client.get(f"/source-records/{r1_id}")
    assert response.status_code == 200
    assert b"Lineage Protected" in response.data
    assert b"cannot be permanently deleted" in response.data
    # MC ID shown in MC-0001 format
    assert f"MC-{mc_id:04d}".encode() in response.data
    # links to match candidate detail page
    assert f"/match-candidates/{mc_id}".encode() in response.data


def test_detail_blocked_state_shows_golden_record_id(client, app):
    with app.app_context():
        system = SourceSystem(name="GoldBlockCRM")
        db.session.add(system)
        db.session.flush()
        record = SourceRecord(source_system_id=system.id, external_id="GB-A", first_name="G", last_name="G",
                              is_archived=True, archived_at=datetime.utcnow())
        db.session.add(record)
        db.session.flush()
        golden = GoldenRecord(first_name="G", last_name="G")
        db.session.add(golden)
        db.session.flush()
        db.session.add(GoldenRecordLink(golden_record_id=golden.id, source_record_id=record.id))
        db.session.commit()
        record_id = record.id
        golden_id = golden.id

    _login_as(client, app, "administrator")
    response = client.get(f"/source-records/{record_id}")
    assert f"GR-{golden_id:04d}".encode() in response.data
    assert f"/golden-records/{golden_id}".encode() in response.data


# ---------------------------------------------------------------------------
# Source system filter tests
# ---------------------------------------------------------------------------

def _seed_two_systems(app):
    """Seed two source systems with one record each, return (system_a_id, system_b_id)."""
    with app.app_context():
        sys_a = SourceSystem(name="FilterCRM")
        sys_b = SourceSystem(name="FilterWeb")
        db.session.add_all([sys_a, sys_b])
        db.session.flush()
        db.session.add(SourceRecord(source_system_id=sys_a.id, external_id="F-CRM-001", first_name="Alice", last_name="A"))
        db.session.add(SourceRecord(source_system_id=sys_b.id, external_id="F-WEB-001", first_name="Bob",   last_name="B"))
        db.session.commit()
        return sys_a.id, sys_b.id


def test_source_records_default_view_no_filter(client, app):
    _seed_two_systems(app)
    _login(client, app)
    response = client.get("/source-records")
    assert response.status_code == 200
    assert b"F-CRM-001" in response.data
    assert b"F-WEB-001" in response.data


def test_source_records_filter_by_source_system(client, app):
    sys_a_id, sys_b_id = _seed_two_systems(app)
    _login(client, app)
    response = client.get(f"/source-records?source_system_id={sys_a_id}")
    assert response.status_code == 200
    assert b"F-CRM-001" in response.data
    assert b"F-WEB-001" not in response.data


def test_source_system_filter_combined_with_status_archived(client, app):
    sys_a_id, _ = _seed_two_systems(app)
    # Archive the CRM record
    with app.app_context():
        record = SourceRecord.query.filter_by(external_id="F-CRM-001").first()
        record.is_archived = True
        db.session.commit()
    _login(client, app)
    response = client.get(f"/source-records?status=archived&source_system_id={sys_a_id}")
    assert response.status_code == 200
    assert b"F-CRM-001" in response.data
    assert b"F-WEB-001" not in response.data


def test_invalid_source_system_id_shows_all_records(client, app):
    _seed_two_systems(app)
    _login(client, app)
    # 99999 is not a real system id — should silently fall back to all systems
    response = client.get("/source-records?source_system_id=99999")
    assert response.status_code == 200
    assert b"F-CRM-001" in response.data
    assert b"F-WEB-001" in response.data
