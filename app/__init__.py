"""
Application factory.

`create_app()` builds and configures the Flask application. Using a factory
(instead of a module-level `app = Flask(__name__)`) keeps the app easy to test
and lets other developers register their own blueprints in one obvious place.

To add a new feature area (module):
    1. Create a package under `app/` (e.g. `app/customers/`) with a blueprint.
    2. Import and register it in `register_blueprints()` below.
"""
from flask import Flask

from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    register_blueprints(app)
    register_error_handlers(app)

    return app


def register_blueprints(app):
    """Register every feature blueprint. Add new modules here."""
    from app.main import main_bp
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.user import user_bp
    from app.cria.routes import cria_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(cria_bp)



def register_error_handlers(app):
    """Friendly HTML pages instead of raw stack traces / default errors."""
    from flask import render_template

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("errors/500.html"), 500
