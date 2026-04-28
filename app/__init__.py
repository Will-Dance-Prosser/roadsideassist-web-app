from flask import Flask

from app.extensions import csrf, db, migrate
from config import Config

# create and config for Flask app
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    register_extensions(app)
    register_blueprints(app)

    return app

#connects Flask extensions to app
def register_extensions(app):

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)





def register_blueprints(app):

    from app.dashboard.routes import dashboard_bp
    app.register_blueprint(dashboard_bp)