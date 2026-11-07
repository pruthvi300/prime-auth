from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession
from app.core import security
from app.core.config import settings
from app.core.rate_limit import limiter
from app.crud import crud_token, crud_user
from app.schemas.token import RefreshRequest, Token
from app.schemas.user import User, UserCreate

router = APIRouter()

def _invalid_refresh() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def register(request: Request, db: DbSession, user_in: UserCreate):
    if await crud_user.get_by_email(db, user_in.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    try:
        return await crud_user.create(db, obj_in=user_in)
    except crud_user.EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from None


@router.post("/login", response_model=Token)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(
    request: Request, db: DbSession, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """OAuth2 password flow. `username` is the email address."""
    user = await crud_user.authenticate(db, form_data.username, form_data.password)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    refresh_token = await crud_token.issue(db, user.id)
    await db.commit()
    return Token(access_token=security.create_access_token(user.id), refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh(body: RefreshRequest, db: DbSession):
    """
    Exchange a refresh token for a new access + refresh token pair.

    The old refresh token stops working. Presenting it again is treated as
    theft: every token in that login session is revoked.
    """
    try:
        payload = security.decode_token(body.refresh_token, security.REFRESH)
        row = await crud_token.consume(db, payload["jti"])
    except (security.InvalidTokenError, crud_token.RefreshTokenReuse):
        raise _invalid_refresh() from None

    user = await crud_user.get(db, row.user_id)
    if user is None or not user.is_active:
        await crud_token.revoke_family(db, row.family_id)
        await db.commit()
        raise _invalid_refresh()

    new_refresh = await crud_token.issue(db, user.id, family_id=row.family_id)
    await db.commit()
    return Token(access_token=security.create_access_token(user.id), refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: DbSession):
    """Revoke the login session that the given refresh token belongs to."""
    try:
        payload = security.decode_token(body.refresh_token, security.REFRESH)
    except security.InvalidTokenError:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    await crud_token.revoke_family(db, payload["fam"])
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
