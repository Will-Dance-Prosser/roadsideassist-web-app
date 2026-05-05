import os
import click
from flask.cli import with_appcontext
from app.extensions import db
from app.models import User


DEMO_USERS = [
    {"username": "admin",   "email": "admin@demo.local",   "role": "administrator"},
    {"username": "steward", "email": "steward@demo.local", "role": "data_steward"},
    {"username": "analyst", "email": "analyst@demo.local", "role": "data_analyst"},
]


@click.command("seed-demo-users")
@with_appcontext
def seed_demo_users():
    """Create demo users for local development if they do not already exist."""

    password = os.environ.get("DEMO_USER_PASSWORD", "demo-password-123")

    db.create_all()

    for data in DEMO_USERS:
        existing = User.query.filter_by(username=data["username"]).first()
        if existing:
            click.echo(f"  already exists: {data['username']} ({data['role']})")
        else:
            user = User(
                username=data["username"],
                email=data["email"],
                role=data["role"],
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            click.echo(f"  created:        {data['username']} ({data['role']})")

    db.session.commit()
    click.echo(f"\nPassword for new accounts: {password}")
    click.echo("Run 'flask seed-demo-users' again at any time — existing users are not overwritten.")
