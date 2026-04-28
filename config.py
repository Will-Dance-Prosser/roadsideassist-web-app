import os

class Config:
    """Base application configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///roadsideassist-dev.db",
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

#temp SQLlite for local dev, will move to postgres when hosted on Railway