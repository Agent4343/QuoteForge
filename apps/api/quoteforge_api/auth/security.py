"""Password hashing and token handling (§16).

- Argon2id for passwords (t=3, m=64 MiB, p=4).
- JWT access tokens, 15-minute expiry.
- Opaque refresh tokens, 30-day expiry, stored only as SHA-256 hashes and
  rotated on use.
- Signed password-reset tokens, 1-hour expiry.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2 import Type as ArgonType
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from quoteforge_api.config import get_settings

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)
RESET_TOKEN_TTL = timedelta(hours=1)
_ALG = "HS256"

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, type=ArgonType.ID)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "access", "exp": _now() + ACCESS_TOKEN_TTL}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=_ALG)


def create_reset_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "reset", "exp": _now() + RESET_TOKEN_TTL}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=_ALG)


def decode_token(token: str, expected_type: str) -> str | None:
    """Return the subject (user id) if the token is valid and of the expected
    type, else None."""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALG])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


def generate_refresh_token() -> tuple[str, str, datetime]:
    """Return (raw_token, sha256_hash, expires_at). Only the hash is stored."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw), _now() + REFRESH_TOKEN_TTL


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
