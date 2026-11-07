from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from pydantic import ValidationError

from app.api import deps
from app.core import security
from app.core.config import settings
from app.crud import crud_user
from app.schemas.token import Token, TokenPayload
from app.schemas.user import UserCreate, User

router = APIRouter()

# Login Endpoint
# Uses OAuth2PasswordRequestForm standard dependency.
# This expects form-data with 'username' and 'password' fields (standard OAuth2 spec).
@router.post("/login", response_model=Token)
async def login_access_token(
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    
    Flow:
    1. Authenticate user against DB (verify email and password hash).
    2. Check if user is active.
    3. Issue Access Token (short-lived) and Refresh Token (long-lived).
    """
    # Authenticate
    user = await crud_user.get_by_email(db, email=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    
    # Generate Tokens
    # Access Token: Used for API authorization (Bearer header)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        user.id, expires_delta=access_token_expires
    )
    # Refresh Token: Used to get new access tokens without re-login
    refresh_token = security.create_refresh_token(
        user.id
    )
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# Token Refresh Endpoint
# This is critical for secure sessions.
# Instead of infinite lifespan access tokens, we use short ones and rotate them here.
@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Refresh access token.
    Rotates refresh token as well (Security Best Practice: Refresh Token Rotation).
    """
    try:
        # Verify the signature and decode the refresh token
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    if token_data.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token type",
        )

    # In a production app, we would verify here that the token hasn't been explicitly revoked.
    # We ideally also check if the user still exists in the DB.
    
    # Issue new pair
    new_access_token = security.create_access_token(
        token_data.sub
    )
    new_refresh_token = security.create_refresh_token(
        token_data.sub
    )
    
    return {
        "access_token": new_access_token, 
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

# User Registration Endpoint
# Uses Pydantic 'UserCreate' schema for automatic validation of email format, password strength etc.
@router.post("/register", response_model=User)
async def register(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserCreate,
) -> Any:
    """
    Create new user.
    """
    # Check for duplicates
    user = await crud_user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    # Create user (hashing happens in CRUD layer or Model)
    user = await crud_user.create(db, obj_in=user_in)
    return user
