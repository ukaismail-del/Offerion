"""M48 — Auth-Ready User Identity Layer.

Provides an anonymous persistent user identifier stored in the session.
All DB records are linked to this identity. When full auth is added later,
this identity can be upgraded to a real user account.
"""

import logging
import uuid

from app.db import db
from app.models import UserIdentity
from app.utils.tier_config import start_trial, check_trial_expiry, trial_days_remaining

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
                # Check trial expiry and sync tier
                current_tier = check_trial_expiry(exists)
                if exists.tier != current_tier:
                    exists.tier = current_tier
                    db.session.commit()
                session_obj["user_tier"] = exists.tier or "free"
                # Inject trial info
                days_left = trial_days_remaining(exists)
                if days_left is not None:
                    session_obj["trial_days_left"] = days_left
                else:
                    session_obj.pop("trial_days_left", None)
                return user_id
        except Exception as exc:
            logger.warning("get_or_create_user lookup failed: %s", exc)
            session_obj.setdefault("user_tier", "free")
            return user_id  # still return the session value as fallback

    # Create new identity with trial
    try:
        identity = UserIdentity()
        start_trial(identity)
        db.session.add(identity)
        db.session.commit()
        session_obj["user_id"] = identity.id
        session_obj["user_tier"] = "trial"
        session_obj["trial_days_left"] = 7
        return identity.id
    except Exception as exc:
        db.session.rollback()
        logger.warning("get_or_create_user create failed: %s", exc)
        fallback_id = session_obj.get("user_id") or uuid.uuid4().hex
        session_obj["user_id"] = fallback_id
        session_obj.setdefault("user_tier", "free")
        return fallback_id
