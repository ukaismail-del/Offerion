import logging
import os
import tempfile
import uuid

from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# Use /tmp/uploads on Linux (Render) or a temp dir on Windows
if os.name == "nt":
    UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "offerion_uploads")
else:
    UPLOAD_DIR = "/tmp/uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)


def _unique_filename(filename):
    """Generate a unique filename using UUID to prevent overwrites."""
    name, ext = os.path.splitext(secure_filename(filename))
    return f"{name}_{uuid.uuid4().hex[:12]}{ext}"


def save_file(file):
    """Save an uploaded file to the upload directory.

    Returns (filepath, safe_filename) on success, or (None, None) on failure.
    """
    try:
        filename = _unique_filename(file.filename)
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)
        logger.info("File saved: %s", filepath)
        return filepath, filename
    except Exception as exc:
        logger.error("Failed to save file: %s", exc)
        return None, None


def get_file_path(filename):
    """Return the full path for a given filename, or None if it doesn't exist."""
    filepath = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(filepath):
        return filepath
    return None


def delete_file(filepath):
    """Safely delete a file. Does not raise if the file is already missing."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.info("File deleted: %s", filepath)
    except Exception as exc:
        logger.warning("Could not delete file %s: %s", filepath, exc)
