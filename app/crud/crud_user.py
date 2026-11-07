from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.models.user import User
from app.schemas.user import UserCreate


class EmailAlreadyRegistered(Exception):
    pass


async def get(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.strip().lower()))
    return result.scalar_one_or_none()


async def create(db: AsyncSession, *, obj_in: UserCreate) -> User:
    user = User(
        email=obj_in.email,
        hashed_password=security.get_password_hash(obj_in.password),
        full_name=obj_in.full_name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:  # two concurrent registrations with the same email
        await db.rollback()
        raise EmailAlreadyRegistered from exc
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_by_email(db, email)
    if user is None:
        security.burn_password_check(password)
        return None
    if not security.verify_password(password, user.hashed_password):
        return None
    return user
