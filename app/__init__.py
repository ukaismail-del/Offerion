import logging
import os

from flask import Flask, redirect, session as flask_session
from flask_wtf.csrf import CSRFProtect

from app.utils.storage import UPLOAD_DIR

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

csrf = CSRFProtect()


def create_app(testing=False):
    app = Flask(__name__)
    app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
    app.secret_key = os.environ.get("SECRET_KEY", "offerion-local-dev-key")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        not testing and os.environ.get("OFFERION_SECURE_COOKIES", "1") != "0"
    )

    if testing:
        app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = not app.config.get("TESTING", False)

    # CSRF protection
    csrf.init_app(app)

    # M46: Database initialization
    from app.db import init_db

    init_db(app)

    from app.routes import main_bp

    app.register_blueprint(main_bp)

    # Bundle T: Exempt Stripe webhook from CSRF
    from app.routes import stripe_webhook

    csrf.exempt(stripe_webhook)

    @app.context_processor
    def inject_auth_context():
        return {
            "is_authenticated": flask_session.get("is_authenticated", False),
            "current_user_email": flask_session.get("current_user_email"),
            "is_admin": flask_session.get("is_admin", False),
        }

    @app.errorhandler(404)
    def not_found(e):
        return redirect("/")

    @app.errorhandler(500)
    def server_error(e):
        logger.error("Internal server error: %s", e)
        return "Internal Server Error", 500

    logger.info("Offerion app created successfully")

    return app
