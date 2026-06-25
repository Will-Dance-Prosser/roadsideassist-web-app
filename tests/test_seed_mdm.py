import pytest
from click.testing import CliRunner

from app import create_app
from app.commands import reset_demo_mdm_data, seed_demo_mdm_data, seed_demo_users
from app.extensions import db
from app.models import (
    AuditLog,
    GoldenRecord,
    GoldenRecordLink,
    MatchCandidate,
    MatchRule,
    MergeDecision,
    SourceRecord,
    SourceSystem,
    User,
)
from config import TestingConfig


EXPECTED_SOURCE_SYSTEMS = 4
EXPECTED_SOURCE_RECORDS = 18
EXPECTED_MATCH_RULES = 5
EXPECTED_PENDING_CANDIDATES = 9
EXPECTED_APPROVED_CANDIDATES = 0
EXPECTED_REJECTED_CANDIDATES = 0


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def assert_seeded_counts():
    """Assert the expected clean seeded demo state."""
    assert SourceSystem.query.count() == EXPECTED_SOURCE_SYSTEMS
    assert SourceRecord.query.count() == EXPECTED_SOURCE_RECORDS
    assert MatchRule.query.count() == EXPECTED_MATCH_RULES

    assert MatchCandidate.query.count() == EXPECTED_PENDING_CANDIDATES
    assert MatchCandidate.query.filter_by(status="pending").count() == EXPECTED_PENDING_CANDIDATES
    assert MatchCandidate.query.filter_by(status="approved").count() == EXPECTED_APPROVED_CANDIDATES
    assert MatchCandidate.query.filter_by(status="rejected").count() == EXPECTED_REJECTED_CANDIDATES

    assert AuditLog.query.filter_by(action="demo_seed").count() == 1


def test_seed_demo_mdm_data_creates_expected_data(app):
    runner = CliRunner()

    with app.app_context():
        result = runner.invoke(seed_demo_mdm_data, catch_exceptions=False)

        assert result.exit_code == 0

        assert SourceSystem.query.filter_by(name="CRM").first() is not None
        assert SourceSystem.query.filter_by(name="Web Portal").first() is not None
        assert SourceSystem.query.filter_by(name="Legacy Membership").first() is not None
        assert SourceSystem.query.filter_by(name="Vehicle Records").first() is not None

        assert MatchRule.query.filter_by(field_name="email").first() is not None
        assert MatchRule.query.filter_by(field_name="date_of_birth").first() is not None

        assert_seeded_counts()


def test_seed_demo_mdm_data_is_idempotent(app):
    """Running the seed command twice must not create duplicate records."""
    runner = CliRunner()

    with app.app_context():
        runner.invoke(seed_demo_mdm_data, catch_exceptions=False)
        runner.invoke(seed_demo_mdm_data, catch_exceptions=False)

        assert_seeded_counts()


def _run_seed(app):
    runner = CliRunner()
    with app.app_context():
        return runner.invoke(seed_demo_mdm_data, catch_exceptions=False)


def _run_reset(app):
    runner = CliRunner()
    with app.app_context():
        return runner.invoke(reset_demo_mdm_data, catch_exceptions=False)


def test_reset_demo_mdm_data_restores_original_counts(app):
    """After dirtying candidate statuses, reset should restore the original seeded state."""
    _run_seed(app)

    with app.app_context():
        pending = MatchCandidate.query.filter_by(status="pending").all()
        assert len(pending) == EXPECTED_PENDING_CANDIDATES

        for candidate in pending:
            candidate.status = "approved"

        db.session.commit()

        assert MatchCandidate.query.filter_by(status="pending").count() == 0
        assert MatchCandidate.query.filter_by(status="approved").count() == EXPECTED_PENDING_CANDIDATES

    result = _run_reset(app)
    assert result.exit_code == 0

    with app.app_context():
        assert_seeded_counts()

        # Reset should leave the decision/golden-record workflow clean.
        assert MergeDecision.query.count() == 0
        assert GoldenRecord.query.count() == 0
        assert GoldenRecordLink.query.count() == 0


def test_reset_demo_mdm_data_does_not_delete_users(app):
    """Reset must leave user accounts untouched."""
    runner = CliRunner()

    with app.app_context():
        runner.invoke(seed_demo_users, catch_exceptions=False)
        user_count_before = User.query.count()
        assert user_count_before > 0

    _run_seed(app)
    _run_reset(app)

    with app.app_context():
        assert User.query.count() == user_count_before


def test_reset_is_idempotent(app):
    """Running reset twice should produce the same clean seeded state."""
    _run_seed(app)
    _run_reset(app)
    _run_reset(app)

    with app.app_context():
        assert_seeded_counts()


def test_reset_prints_completion_message(app):
    """Reset command should print a clear completion message."""
    _run_seed(app)
    result = _run_reset(app)

    assert result.exit_code == 0
    assert "reset to its original seeded state" in result.output