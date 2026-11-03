"""Symmetric encryption for at-rest secrets (per-clinic Twilio + email credentials).

Uses Fernet (AES-128-CBC + HMAC-SHA256) from cryptography. The master key is stored in the
`VETAURA_ENCRYPTION_KEY` env var and is required at import time.
"""
from __future__ import annotations
import os
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_ENV_VAR = "VETAURA_ENCRYPTION_KEY"


def _load_key() -> bytes:
    """Fail fast if the master key is missing — never auto-generate (that silently bricks stored secrets)."""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    key = os.environ.get(_ENV_VAR)
    if not key:
        raise RuntimeError(f"{_ENV_VAR} is not set. Set it in backend/.env (never rotate it without re-encrypting secrets).")
    return key.encode()


_KEY = _load_key()
_F = Fernet(_KEY)


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        return ""
    return _F.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _F.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt secret — encryption key may have rotated.")
        raise


def mask(secret: str, keep: int = 4) -> str:
    """Return an obfuscated version of a secret for display (e.g. 'AC••••••••••1234')."""
    if not secret:
        return ""
    if len(secret) <= keep:
        return "•" * len(secret)
    return secret[:2] + "•" * max(4, len(secret) - keep - 2) + secret[-keep:]
