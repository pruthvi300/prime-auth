"""
Password hashing (bcrypt) and JWT helpers (PyJWT).

Token design:
- Access token: short-lived, carries `sub` (user id) and `type="access"`.
- Refresh token: long-lived, carries `jti` (unique id) and `fam` (rotation family).
  Every refresh token's jti is stored in the database so it can be rotated,
  revoked, and checked for reuse. See app/crud/crud_token.py.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ACCESS = "access"
REFRESH = "refresh"


class InvalidTokenError(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash or a password longer than bcrypt's 72-byte limit.
        return False


# Used to spend the same bcrypt time when the email is unknown, so response
# timing does not reveal which emails are registered.
_DUMMY_HASH = get_password_hash("timing-equalisation-dummy-password")


def burn_password_check(plain_password: str) -> None:
    verify_password(plain_password, _DUMMY_HASH)


def _encode(claims: dict[str, Any], expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**claims, "iat": now, "exp": now + expires_delta}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: int | str, expires_delta: timedelta | None = None) -> str:
    return _encode(
        {"sub": str(user_id), "type": ACCESS},
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(
    user_id: int | str, family_id: str, expires_delta: timedelta | None = None
) -> tuple[str, str, datetime]:
    """Return (encoded token, jti, expires_at)."""
    jti = uuid.uuid4().hex
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token = _encode({"sub": str(user_id), "type": REFRESH, "jti": jti, "fam": family_id}, delta)
    return token, jti, datetime.now(timezone.utc) + delta


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    required = ["exp", "sub", "type"] + (["jti", "fam"] if expected_type == REFRESH else [])
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": required},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    if payload.get("type") != expected_type:
        raise InvalidTokenError("wrong token type")
    return payload
