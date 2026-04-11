"""M46 — Database Foundation.

Lightweight SQLAlchemy setup for Offerion. Uses SQLite locally,
compatible with Postgres on Render via DATABASE_URL.
"""

import os

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """Configure and initialise the database for the given Flask app."""
    database_url = os.environ.get("DATABASE_URL", "")

    # Render provides DATABASE_URL with postgres://, SQLAlchemy needs postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    if not database_url:
        # Local development: SQLite in instance folder
        db_path = os.path.join(app.instance_path, "offerion.db")
        os.makedirs(app.instance_path, exist_ok=True)
        database_url = f"sqlite:///{db_path}"

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    app.config["DB_AVAILABLE"] = False

    try:
        with app.app_context():
            # Import models so they are registered before create_all
            from app import models as _models  # noqa: F401

            db.create_all()
            _migrate_add_columns(app)
        app.config["DB_AVAILABLE"] = True
    except Exception as exc:
        app.logger.warning(
            "Database initialization unavailable, using session fallback: %s", exc
        )


def _migrate_add_columns(app):
    """Add columns introduced after initial schema (safe for SQLite + Postgres)."""
    migrations = [
        ("user_identity", "tier", "VARCHAR(20) DEFAULT 'free'"),
        ("user_identity", "trial_start", "DATETIME"),
        ("user_identity", "trial_end", "DATETIME"),
        ("user_identity", "daily_matches_used", "INTEGER DEFAULT 0"),
        ("user_identity", "last_usage_reset", "DATETIME"),
    ]
    for table, column, col_type in migrations:
        try:
            db.session.execute(
                db.text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            )
            db.session.commit()
            app.logger.info("Migrated: added %s.%s", table, column)
        except Exception:
            db.session.rollback()  # column already exists, ignore
