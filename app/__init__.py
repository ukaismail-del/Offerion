import logging
import os

from flask import Flask, redirect

from app.utils.storage import UPLOAD_DIR

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
    app.secret_key = os.environ.get("SECRET_KEY", "offerion-local-dev-key")

    from app.routes import main_bp

    app.register_blueprint(main_bp)

    @app.errorhandler(404)
    def not_found(e):
        return redirect("/")

    @app.errorhandler(500)
    def server_error(e):
        logger.error("Internal server error: %s", e)
        return "Internal Server Error", 500

    logger.info("Offerion app created successfully")

    return app
