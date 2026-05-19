from flask_migrate import upgrade
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    upgrade()
    from app.commands import seed_demo_users, seed_demo_mdm
    from click.testing import CliRunner
    runner = CliRunner()
    runner.invoke(seed_demo_users)
    runner.invoke(seed_demo_mdm)
