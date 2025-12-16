"""SQLite database module for managing subscribers.

This module uses Python's built-in :mod:`sqlite3` library and stores data in a
local SQLite file named ``subscribers.db``.

The table schema is created automatically on first import.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

# Requirement reference: "create file sqlite:///subscribers.db if not exists".
# sqlite3 connects to a filesystem path; we accept the SQLAlchemy-style URI and
# normalize it to a local file path.
DB_URI = "sqlite:///subscribers.db"

_ALLOWED_STATUSES = {"active", "pending", "expired"}
_ALLOWED_SUBSCRIPTION_TYPES = {"monthly", "lifetime"}


def _normalize_sqlite_uri(uri: str) -> str:
    """Normalize a SQLite URI or path to a filesystem path.

    Args:
        uri: A SQLite URI (e.g. ``sqlite:///subscribers.db``) or a plain path.

    Returns:
        A filesystem path suitable for :func:`sqlite3.connect`.
    """

    if uri.startswith("sqlite:///"):
        return uri[len("sqlite:///") :]
    return uri


def _db_path() -> str:
    """Return the resolved database path.

    By default, the database file is created alongside this module.
    """

    path = _normalize_sqlite_uri(DB_URI)
    if os.path.isabs(path):
        return path

    return os.path.abspath(os.path.join(os.path.dirname(__file__), path))


@contextmanager
def _get_connection() -> Iterator[sqlite3.Connection]:
    """Context manager that yields a SQLite connection.

    Commits on success and rolls back on exceptions.

    Yields:
        A configured :class:`sqlite3.Connection`.

    Raises:
        sqlite3.Error: If the connection cannot be created.
    """

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(
            _db_path(),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except sqlite3.Error:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()


def _initialize_db() -> None:
    """Create required tables if they do not already exist."""

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS subscribers (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        start_date DATE,
        end_date DATE,
        status TEXT NOT NULL CHECK (status IN ('active', 'pending', 'expired')),
        subscription_type TEXT CHECK (subscription_type IN ('monthly', 'lifetime'))
    )
    """.strip()

    try:
        with _get_connection() as conn:
            conn.execute(create_table_sql)
    except sqlite3.Error:
        logger.exception("Failed to initialize database")
        # Swallow to avoid import-time crashes. Callers will see failures on
        # actual CRUD operations.
        return


def _date_to_str(value: Optional[date]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(row)

    for key in ("start_date", "end_date"):
        raw = result.get(key)
        if isinstance(raw, str):
            try:
                result[key] = date.fromisoformat(raw)
            except ValueError:
                # Keep original value if it doesn't parse cleanly.
                pass

    return result


def create_subscriber(user_id: int, username: str) -> bool:
    """Create a new subscriber row.

    The new subscriber is created with a default status of ``pending`` and
    without subscription dates.

    Args:
        user_id: Unique user identifier. Used as the primary key.
        username: Username to associate with the subscriber.

    Returns:
        True if the subscriber was created successfully, False otherwise.
    """

    sql = """
    INSERT INTO subscribers (user_id, username, start_date, end_date, status, subscription_type)
    VALUES (?, ?, NULL, NULL, 'pending', NULL)
    """.strip()

    try:
        with _get_connection() as conn:
            conn.execute(sql, (user_id, username))
        return True
    except sqlite3.IntegrityError:
        logger.exception("Failed to create subscriber: user_id=%s already exists", user_id)
        return False
    except sqlite3.Error:
        logger.exception("Failed to create subscriber: user_id=%s", user_id)
        return False


def get_subscriber(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a subscriber by user ID.

    Args:
        user_id: The primary key of the subscriber.

    Returns:
        A dict representing the subscriber row, or None if no row exists.
    """

    sql = "SELECT user_id, username, start_date, end_date, status, subscription_type FROM subscribers WHERE user_id = ?"

    try:
        with _get_connection() as conn:
            row = conn.execute(sql, (user_id,)).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)
    except sqlite3.Error:
        logger.exception("Failed to get subscriber: user_id=%s", user_id)
        return None


def update_subscriber_status(user_id: int, status: str) -> bool:
    """Update the status for a subscriber.

    Args:
        user_id: The primary key of the subscriber.
        status: New status. Must be one of: ``active``, ``pending``, ``expired``.

    Returns:
        True if a row was updated, False otherwise.
    """

    if status not in _ALLOWED_STATUSES:
        logger.error("Invalid status '%s' for user_id=%s", status, user_id)
        return False

    sql = "UPDATE subscribers SET status = ? WHERE user_id = ?"

    try:
        with _get_connection() as conn:
            cur = conn.execute(sql, (status, user_id))
            return cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to update subscriber status: user_id=%s", user_id)
        return False


def update_subscription_dates(
    user_id: int,
    start_date: Optional[date],
    end_date: Optional[date],
    subscription_type: str,
) -> bool:
    """Update subscription dates and type for a subscriber.

    Args:
        user_id: The primary key of the subscriber.
        start_date: Subscription start date.
        end_date: Subscription end date.
        subscription_type: Subscription type (``monthly`` or ``lifetime``).

    Returns:
        True if a row was updated, False otherwise.
    """

    if subscription_type not in _ALLOWED_SUBSCRIPTION_TYPES:
        logger.error(
            "Invalid subscription_type '%s' for user_id=%s", subscription_type, user_id
        )
        return False

    sql = """
    UPDATE subscribers
    SET start_date = ?, end_date = ?, subscription_type = ?
    WHERE user_id = ?
    """.strip()

    try:
        with _get_connection() as conn:
            cur = conn.execute(
                sql,
                (
                    _date_to_str(start_date),
                    _date_to_str(end_date),
                    subscription_type,
                    user_id,
                ),
            )
            return cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to update subscription dates: user_id=%s", user_id)
        return False


def list_expired_subscriptions() -> List[Dict[str, Any]]:
    """List subscribers that have an active status but an expired end_date.

    Returns:
        A list of subscriber dicts for all rows where ``status='active'`` and
        ``end_date`` is before today.
    """

    sql = """
    SELECT user_id, username, start_date, end_date, status, subscription_type
    FROM subscribers
    WHERE status = 'active'
      AND end_date IS NOT NULL
      AND date(end_date) < date('now')
    ORDER BY end_date ASC
    """.strip()

    try:
        with _get_connection() as conn:
            rows = conn.execute(sql).fetchall()
        return [_row_to_dict(r) for r in rows]
    except sqlite3.Error:
        logger.exception("Failed to list expired subscriptions")
        return []


def delete_subscriber(user_id: int) -> bool:
    """Delete a subscriber by user ID.

    Args:
        user_id: The primary key of the subscriber.

    Returns:
        True if a row was deleted, False otherwise.
    """

    sql = "DELETE FROM subscribers WHERE user_id = ?"

    try:
        with _get_connection() as conn:
            cur = conn.execute(sql, (user_id,))
            return cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete subscriber: user_id=%s", user_id)
        return False


_initialize_db()
