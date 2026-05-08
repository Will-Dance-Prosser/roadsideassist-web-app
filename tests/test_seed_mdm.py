import pytest
from app import create_app
from app.extensions import db
from app.models import AuditLog, MatchCandidate, MatchRule, SourceRecord, SourceSystem
from app.commands import seed_demo_mdm_data
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
