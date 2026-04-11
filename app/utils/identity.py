"""M48 — Auth-Ready User Identity Layer.

Provides an anonymous persistent user identifier stored in the session.
All DB records are linked to this identity. When full auth is added later,
this identity can be upgraded to a real user account.
"""

import logging
import uuid

from app.db import db
from app.models import UserIdentity

logger = logging.getLogger(__name__)


def get_or_create_user(session_obj):
    """Return the user_id for the current session.

    If the session already has a user_id that exists in the DB, return it.
    Otherwise create a new anonymous identity, persist it, and store the
    id in the session.

    Returns the user_id string, or None if the DB is unavailable.
    """
    user_id = session_obj.get("user_id")

    if user_id:
        try:
            exists = UserIdentity.query.filter_by(id=user_id).first()
            if exists:
                # Sync tier from DB to session
                if exists.tier:
                    session_obj.setdefault("user_tier", exists.tier)
                else:
                    session_obj.setdefault("user_tier", "free")
                return user_id
        except Exception as exc:
            logger.warning("get_or_create_user lookup failed: %s", exc)
            session_obj.setdefault("user_tier", "free")
            return user_id  # still return the session value as fallback

    # Create new identity
    try:
        identity = UserIdentity()
        db.session.add(identity)
        db.session.commit()
        session_obj["user_id"] = identity.id
        session_obj["user_tier"] = "free"
        return identity.id
    except Exception as exc:
        db.session.rollback()
        logger.warning("get_or_create_user create failed: %s", exc)
        fallback_id = session_obj.get("user_id") or uuid.uuid4().hex
        session_obj["user_id"] = fallback_id
        session_obj.setdefault("user_tier", "free")
        return fallback_id
