"""Symmetric encryption for at-rest secrets (per-clinic Twilio + email credentials).

Uses Fernet (AES-128-CBC + HMAC-SHA256) from cryptography. The master key is stored in the
`VETAURA_ENCRYPTION_KEY` env var. If missing, we generate and persist one to the .env file
so local dev works out of the box — but production deployments MUST set this explicitly.
"""
from __future__ import annotations
import os
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_ENV_VAR = "VETAURA_ENCRYPTION_KEY"


def _load_or_create_key() -> bytes:
    key = os.environ.get(_ENV_VAR)
    if key:
        return key.encode()
    # Generate and persist to backend/.env so restarts don't rotate the key.
    new = Fernet.generate_key()
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        with open(env_path, "a") as f:
            f.write(f'\n{_ENV_VAR}="{new.decode()}"\n')
        os.environ[_ENV_VAR] = new.decode()
        logger.warning(f"Generated new {_ENV_VAR} and persisted to backend/.env — set this explicitly in production!")
    except Exception as e:
        logger.error(f"Could not persist {_ENV_VAR}: {e}. Using ephemeral key (secrets will not survive restarts).")
        os.environ[_ENV_VAR] = new.decode()
    return new


_KEY = _load_or_create_key()
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
