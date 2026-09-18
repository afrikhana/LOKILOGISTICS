# -*- coding: utf-8 -*-
"""The app module, containing the app factory function."""
import logging
import os
import sys
from datetime import timedelta

from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from lokiLogistics import commands
from lokiLogistics.extensions import (
    bcrypt,
    cache,
    csrf_protect,
    db,
    debug_toolbar,
    flask_static_digest,
    login_manager,
    migrate,
    redis_client,
)


# Global Extensions initialized outside factory context to avoid leaks
jwt = JWTManager()
cors = CORS()
limiter = Limiter(
    key_func=lambda: user_jwt_or_ip(),
    storage_uri=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    strategy="moving-window",
    default_limits=["100 per hour"]
)


def user_jwt_or_ip():
    """Identifies users based on JWT token content or falls back to remote IP address."""
    from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity:
            return f"user:{identity}"
    except Exception:
        pass
    return get_remote_address()


# --- Core JWT Callback Hooks ---
@jwt.user_identity_loader
def user_identity_lookup(user_obj):
    if hasattr(user_obj, 'business_name'):
        return user_obj.business_name
    return str(user_obj)


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    return merchants.models.User.query.filter_by(business_name=jwt_data["sub"]).first()


def create_app(config_object="lokiLogistics.settings"):
    """Create application factory."""
    app = Flask(__name__.split(".")[0])
    app.config.from_object(config_object)

    register_extensions(app)

    # 1. Import raw model modules directly (do NOT trigger __init__.py files)
    import lokiLogistics.customers.models  # noqa: F401
    import lokiLogistics.merchants.models  # noqa: F401
    import lokiLogistics.riders.models     # noqa: F401
    import lokiLogistics.shipments.models  # noqa: F401

    # 2. Register blueprints and extensions after models are loaded
    register_blueprints(app)
    register_errorhandlers(app)
    register_shellcontext(app)
    register_commands(app)
    configure_logger(app)

    # 3. Create database tables automatically if they don't exist
    with app.app_context():
        db.create_all()

    return app


def register_extensions(app):
    """Register Flask extensions."""
    # Configure Cache to use Redis
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    app.config["CACHE_DEFAULT_TIMEOUT"] = 300

    bcrypt.init_app(app)
    cache.init_app(app)
    db.init_app(app)
    csrf_protect.init_app(app)
    login_manager.init_app(app)
    debug_toolbar.init_app(app)
    redis_client.init_app(app)
    migrate.init_app(app, db)
    flask_static_digest.init_app(app)

    jwt.init_app(app)
    limiter.init_app(app)

    cors.init_app(
        app,
        resources={r"/*": {"origins": "*"}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )
    return None


def register_blueprints(app):
    """Register Flask blueprints."""
    # Core/Legacy App Blueprints

    # Logistics & API Blueprints
    from lokiLogistics.shipments.views import shipments_bp
    from lokiLogistics.merchants.views import merchants_bp
    from lokiLogistics.riders.views import riders_bp  # Assuming riders/views.py exists
    from lokiLogistics.customers.views import customers_bp  # Assuming customers/views.py exists
    from lokiLogistics.jwt.auth import auth_bp  # Assuming jwt/auth.py exists

    app.register_blueprint(shipments_bp)
    app.register_blueprint(merchants_bp)
    app.register_blueprint(riders_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(auth_bp)

    # API CSRF Exemptions for external/mobile clients
    csrf_protect.exempt(shipments_bp)
    csrf_protect.exempt(merchants_bp)
    csrf_protect.exempt(riders_bp)
    csrf_protect.exempt(customers_bp)
    csrf_protect.exempt(auth_bp)


def register_errorhandlers(app):
    """Register API-friendly JSON error handlers."""
    def render_error(error):
        error_code = getattr(error, "code", 500)
        
        response_data = {
            "status": "error",
            "code": error_code,
            "message": getattr(error, "description", "Internal Server Error")
        }

        if hasattr(error, "original_exception") and error.original_exception:
            response_data["details"] = str(error.original_exception)

        return response_data, error_code

    for errcode in [401, 403, 404, 405, 500]:
        app.errorhandler(errcode)(render_error)

    return None


def register_shellcontext(app):
    """Register shell context objects."""
    def shell_context():
        return {"db": db, "User": merchants.models.User}

    app.shell_context_processor(shell_context)


def register_commands(app):
    """Register Click commands."""
    app.cli.add_command(commands.test)
    app.cli.add_command(commands.lint)


def configure_logger(app):
    """Configure loggers."""
    handler = logging.StreamHandler(sys.stdout)
    if not app.logger.handlers:
        app.logger.addHandler(handler)