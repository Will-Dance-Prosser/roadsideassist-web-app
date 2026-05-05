from flask import Flask

from app.extensions import csrf, db, login_manager, migrate
from config import Config

# create and config for Flask app - keeps things testable and avoids circular imports
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    register_extensions(app)
    register_blueprints(app)

    return app

#connects Flask extensions to app (after it exists)
def register_extensions(app):

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Import models here so Flask-Migrate can detect them
    from app import models  # noqa: F401





def register_blueprints(app):
     # Import inside the function to avoid circular imports
    from app.dashboard.routes import dashboard_bp
    from app.auth.routes import auth_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)