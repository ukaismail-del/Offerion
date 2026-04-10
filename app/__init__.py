import os

from flask import Flask

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}


def create_app():
    app = Flask(__name__)
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
    app.secret_key = os.environ.get("SECRET_KEY", "offerion-local-dev-key")

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    from app.routes import main_bp

    app.register_blueprint(main_bp)

    return app
