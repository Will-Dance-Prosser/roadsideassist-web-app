import pytest
from app import create_app
from app.extensions import db
from app.models import AuditLog, MatchCandidate, SourceRecord, SourceSystem, User
from config import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_create_source_system(app):
    with app.app_context():
        system = SourceSystem(name="CRM", description="Customer CRM system")
        db.session.add(system)
        db.session.commit()

        saved = db.session.get(SourceSystem, system.id)
        assert saved is not None
        assert saved.name == "CRM"
        assert saved.description == "Customer CRM system"
        assert saved.is_active is True
        assert saved.created_at is not None


def test_create_source_records_linked_to_source_system(app):
    with app.app_context():
        system = SourceSystem(name="ERP")
        db.session.add(system)
        db.session.commit()

        record_a = SourceRecord(
            source_system_id=system.id,
            external_id="ERP-001",
            first_name="John",
            last_name="Smith",
            email="john.smith@example.com",
        )
        record_b = SourceRecord(
            source_system_id=system.id,
            external_id="ERP-002",
            first_name="Jane",
            last_name="Doe",
            email="jane.doe@example.com",
        )
        db.session.add_all([record_a, record_b])
        db.session.commit()

        assert record_a.id is not None
        assert record_b.id is not None
        assert record_a.source_system.name == "ERP"
        assert record_b.source_system.name == "ERP"
        assert len(system.records) == 2
        assert record_a.is_archived is False
        assert record_a.archived_at is None


def test_create_match_candidate_between_two_source_records(app):
    with app.app_context():
        system = SourceSystem(name="LEGACY")
        db.session.add(system)
        db.session.commit()

        record_a = SourceRecord(source_system_id=system.id, external_id="L-001", first_name="Alice", last_name="Jones")
        record_b = SourceRecord(source_system_id=system.id, external_id="L-002", first_name="A.", last_name="Jones")
        db.session.add_all([record_a, record_b])
        db.session.commit()

        candidate = MatchCandidate(
            record_a_id=record_a.id,
            record_b_id=record_b.id,
            match_score=0.91,
        )
        db.session.add(candidate)
        db.session.commit()

        saved = db.session.get(MatchCandidate, candidate.id)
        assert saved is not None
        assert saved.match_score == 0.91
        assert saved.status == "pending"
        assert saved.record_a.external_id == "L-001"
        assert saved.record_b.external_id == "L-002"
        assert saved.reviewed_at is None


def test_create_audit_log_entry(app):
    with app.app_context():
        user = User(username="admin", email="admin@example.com", role="administrator")
        user.set_password("test-password")
        db.session.add(user)
        db.session.commit()

        log = AuditLog(
            user_id=user.id,
            action="match_approved",
            target_type="match_candidate",
            target_id=1,
            detail="Approved by administrator",
        )
        db.session.add(log)
        db.session.commit()

        saved = db.session.get(AuditLog, log.id)
        assert saved is not None
        assert saved.action == "match_approved"
        assert saved.target_type == "match_candidate"
        assert saved.target_id == 1
        assert saved.user.username == "admin"
        assert saved.created_at is not None


def test_create_audit_log_without_user(app):
    """System-generated audit log entries have no user (nullable user_id)."""
    with app.app_context():
        log = AuditLog(
            action="system_startup",
            target_type=None,
            target_id=None,
            detail="System initialised",
        )
        db.session.add(log)
        db.session.commit()

        saved = db.session.get(AuditLog, log.id)
        assert saved is not None
        assert saved.user_id is None
        assert saved.action == "system_startup"
