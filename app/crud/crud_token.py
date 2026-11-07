"""
Refresh token persistence: issue, rotate (with reuse detection), and revoke.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.models.refresh_token import RefreshToken


class RefreshTokenReuse(Exception):
    """A refresh token that was already used or revoked was presented again."""


async def issue(db: AsyncSession, user_id: int, family_id: str | None = None) -> str:
    """Create and persist a refresh token. Caller commits."""
    family_id = family_id or uuid.uuid4().hex
    token, jti, expires_at = security.create_refresh_token(user_id, family_id)
    db.add(RefreshToken(jti=jti, user_id=user_id, family_id=family_id, expires_at=expires_at))
    return token


async def consume(db: AsyncSession, jti: str) -> RefreshToken:
    """
    Atomically mark a refresh token as used.

    The UPDATE only matches a row that is not yet revoked, so two concurrent
    requests with the same token cannot both succeed. If nothing matched and the
    row exists, the token is being reused: revoke its whole family.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.jti == jti, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    row = await db.get(RefreshToken, jti)
    if row is None:
        raise security.InvalidTokenError("unknown refresh token")
    if result.rowcount == 0:
        await revoke_family(db, row.family_id)
        await db.commit()
        raise RefreshTokenReuse
    return row


async def revoke_family(db: AsyncSession, family_id: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
