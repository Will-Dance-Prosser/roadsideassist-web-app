import pytest
from app import create_app
from app.extensions import db
from app.models import AuditLog, GoldenRecord, GoldenRecordLink, MatchCandidate, MatchRule, MergeDecision, SourceRecord, SourceSystem, User
from app.commands import reset_demo_mdm_data, seed_demo_mdm_data, seed_demo_users
from config import TestingConfig
from click.testing import CliRunner


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_seed_demo_mdm_data_creates_expected_data(app):
    runner = CliRunner()

    with app.app_context():
        result = runner.invoke(seed_demo_mdm_data, catch_exceptions=False)

        assert result.exit_code == 0

        # Source systems created
        assert SourceSystem.query.count() == 4
        assert SourceSystem.query.filter_by(name="CRM").first() is not None
        assert SourceSystem.query.filter_by(name="Web Portal").first() is not None
        assert SourceSystem.query.filter_by(name="Legacy Membership").first() is not None
        assert SourceSystem.query.filter_by(name="Vehicle Records").first() is not None

        # Source records created
        assert SourceRecord.query.count() == 12

        # Match candidates created with correct statuses
        assert MatchCandidate.query.count() == 6
        assert MatchCandidate.query.filter_by(status="pending").count() == 2
        assert MatchCandidate.query.filter_by(status="approved").count() == 3
        assert MatchCandidate.query.filter_by(status="rejected").count() == 1

        # Match rules created
        assert MatchRule.query.count() == 5
        assert MatchRule.query.filter_by(field_name="email").first() is not None
        assert MatchRule.query.filter_by(field_name="date_of_birth").first() is not None

        # Audit log entry created
        assert AuditLog.query.filter_by(action="demo_seed").first() is not None


def test_seed_demo_mdm_data_is_idempotent(app):
    """Running the seed command twice must not create duplicate records."""
    runner = CliRunner()

    with app.app_context():
        runner.invoke(seed_demo_mdm_data, catch_exceptions=False)
        runner.invoke(seed_demo_mdm_data, catch_exceptions=False)

        assert SourceSystem.query.count() == 4
        assert SourceRecord.query.count() == 12
        assert MatchCandidate.query.count() == 6
        assert MatchRule.query.count() == 5
        assert AuditLog.query.filter_by(action="demo_seed").count() == 1


def _run_seed(app):
    runner = CliRunner()
    with app.app_context():
        runner.invoke(seed_demo_mdm_data, catch_exceptions=False)


def _run_reset(app):
    runner = CliRunner()
    with app.app_context():
        result = runner.invoke(reset_demo_mdm_data, catch_exceptions=False)
    return result


def test_reset_demo_mdm_data_restores_original_counts(app):
    """After dirtying candidate statuses, reset should restore the original seeded state."""
    _run_seed(app)

    # Simulate state change: flip both pending candidates to approved
    with app.app_context():
        pending = MatchCandidate.query.filter_by(status="pending").all()
        assert len(pending) == 2
        for c in pending:
            c.status = "approved"
        db.session.commit()
        assert MatchCandidate.query.filter_by(status="pending").count() == 0

    result = _run_reset(app)
    assert result.exit_code == 0

    with app.app_context():
        # Original seeded counts restored
        assert SourceSystem.query.count() == 4
        assert SourceRecord.query.count() == 12
        assert MatchCandidate.query.count() == 6
        assert MatchCandidate.query.filter_by(status="pending").count() == 2
        assert MatchCandidate.query.filter_by(status="approved").count() == 3
        assert MatchCandidate.query.filter_by(status="rejected").count() == 1
        assert MatchRule.query.count() == 5
        assert AuditLog.query.filter_by(action="demo_seed").count() == 1

        # MDM decision data should be clean (none was created in this test)
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
        assert SourceSystem.query.count() == 4
        assert SourceRecord.query.count() == 12
        assert MatchCandidate.query.count() == 6
        assert MatchRule.query.count() == 5
        assert AuditLog.query.filter_by(action="demo_seed").count() == 1


def test_reset_prints_completion_message(app):
    """Reset command should print a clear completion message."""
    _run_seed(app)
    result = _run_reset(app)
    assert "reset to its original seeded state" in result.output
