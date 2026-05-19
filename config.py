import os

class Config:
    """Base application configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    # Railway injects DATABASE_URL as postgres:// but SQLAlchemy requires postgresql://
    _db_url = os.environ.get("DATABASE_URL", "sqlite:///membermatch-dev.db")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestingConfig(Config):
    """Configuration used by pytest — in-memory database, CSRF disabled."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False