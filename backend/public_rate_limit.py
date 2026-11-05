"""Rate limits for public (no-login) endpoints that spend AI credits.

The public receptionist chat and the Try-it wizard call Claude without a login, so
without a cap anyone could run up the Emergent LLM bill. Counters live in MongoDB
(fixed windows, auto-expired by a TTL index) so they survive restarts.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, Request
from pymongo import ReturnDocument

from login_security import client_ip

_indexes_ready = False


async def _ensure_indexes(db) -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    await db.public_rate_limits.create_index("expires_at", expireAfterSeconds=0)
    _indexes_ready = True


async def enforce(db, request: Request, bucket: str, *, limit: int, window_minutes: int,
                  key_suffix: str = "") -> None:
    """Raise 429 once `limit` calls from this IP (+ optional key) hit `bucket` in the window."""
    await _ensure_indexes(db)
    now = datetime.now(timezone.utc)
    window = int(now.timestamp() // (window_minutes * 60))
    key = f"{bucket}:{client_ip(request)}:{key_suffix}:{window}"
    doc = await db.public_rate_limits.find_one_and_update(
        {"_id": key},
        {"$inc": {"n": 1}, "$setOnInsert": {"expires_at": now + timedelta(minutes=window_minutes * 2)}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if doc and doc.get("n", 0) > limit:
        raise HTTPException(429, "Too many requests. Please wait a few minutes and try again.")
