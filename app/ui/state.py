"""
Server-side state management for bid forms.
For MVP, uses in-memory storage. Can be replaced with Redis/DB later.
"""

from typing import Dict, Optional
from datetime import datetime, timezone
from app.ui.viewmodels import BidFormState
from app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory storage for active bid forms
# In production, this would be replaced with Redis or a database
_bid_forms: Dict[str, BidFormState] = {}

# QA warnings storage
_bid_warnings: Dict[str, list] = {}

# Extraction debug payloads
_bid_debug: Dict[str, dict] = {}

# The current active bid form (for single-user MVP)
_current_bid_id: Optional[str] = None


def set_state(bid_id: str, state: BidFormState) -> None:
    """Store a bid form state."""
    global _current_bid_id
    _bid_forms[bid_id] = state
    _current_bid_id = bid_id
    state.modified_at = datetime.now(timezone.utc).isoformat()
    logger.info(f"Stored bid form {bid_id} with {len(state.items)} items")


def get_state(bid_id: Optional[str] = None) -> Optional[BidFormState]:
    """
    Retrieve a bid form state.
    If bid_id is None, returns the current active bid.
    """
    if bid_id is None:
        bid_id = _current_bid_id

    if bid_id and bid_id in _bid_forms:
        return _bid_forms[bid_id]

    return None


def get_current_state() -> Optional[BidFormState]:
    """Get the current active bid form state."""
    return get_state()


def clear_state(bid_id: Optional[str] = None) -> bool:
    """
    Clear a specific bid form or all if no ID provided.
    Returns True if something was cleared.
    """
    global _current_bid_id

    if bid_id:
        if bid_id in _bid_forms:
            del _bid_forms[bid_id]
            if _current_bid_id == bid_id:
                _current_bid_id = None
            logger.info(f"Cleared bid form {bid_id}")
            return True
    else:
        # Clear all
        had_data = len(_bid_forms) > 0
        _bid_forms.clear()
        _current_bid_id = None
        if had_data:
            logger.info("Cleared all bid forms")
        return had_data

    return False


def list_bid_ids() -> list[str]:
    """List all stored bid form IDs."""
    return list(_bid_forms.keys())


def has_current_bid() -> bool:
    """Check if there's a current active bid."""
    return _current_bid_id is not None and _current_bid_id in _bid_forms


def set_warnings(bid_id: str, warnings: list) -> None:
    """Store QA warnings for a bid form."""
    _bid_warnings[bid_id] = warnings
    logger.info(f"Stored {len(warnings)} warnings for bid {bid_id}")

def set_debug(bid_id: str, debug_payload: dict) -> None:
    """Store extraction/mapping debug payload for a bid form."""
    _bid_debug[bid_id] = debug_payload
    logger.info(f"Stored debug payload for bid {bid_id}")


def get_warnings(bid_id: Optional[str] = None) -> list:
    """Get QA warnings for a bid form."""
    if bid_id is None:
        bid_id = _current_bid_id
    return _bid_warnings.get(bid_id, []) if bid_id else []

def get_debug(bid_id: Optional[str] = None) -> dict:
    """Get debug payload for a bid form."""
    if bid_id is None:
        bid_id = _current_bid_id
    return _bid_debug.get(bid_id, {}) if bid_id else {}


def get_current_warnings() -> list:
    """Get warnings for the current bid."""
    return get_warnings()

def get_current_debug() -> dict:
    """Get debug payload for the current bid."""
    return get_debug()


def update_current_state(updater_func) -> bool:
    """
    Update the current bid state using a function.
    The updater function receives the current state and should modify it in place.
    Returns True if successful.
    """
    state = get_current_state()
    if state:
        updater_func(state)
        state.modified_at = datetime.now(timezone.utc).isoformat()
        return True
    return False


# Session management helpers for multi-user support (future enhancement)
class SessionManager:
    """
    Manages user sessions and their associated bid forms.
    For MVP, this is simplified to single-user mode.
    """

    def __init__(self):
        self.sessions: Dict[str, str] = {}  # session_id -> bid_id

    def create_session(self, session_id: str, bid_id: str) -> None:
        """Associate a session with a bid form."""
        self.sessions[session_id] = bid_id

    def get_bid_for_session(self, session_id: str) -> Optional[str]:
        """Get the bid ID associated with a session."""
        return self.sessions.get(session_id)

    def clear_session(self, session_id: str) -> None:
        """Clear a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]


# Global session manager instance
session_manager = SessionManager()
