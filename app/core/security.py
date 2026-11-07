"""
Prime Auth - Security Utilities

This module contains cryptographic utilities for:
- Password hashing (bcrypt)
- JWT token creation (access & refresh)

Security Design Decisions (Interview talking points):

1. Bcrypt for Password Hashing:
   - Adaptive hash function (configurable work factor)
   - Built-in salting (prevents rainbow table attacks)
   - Intentionally slow (resistant to brute-force)
   
2. JWT (JSON Web Tokens):
   - Stateless authentication (no session storage needed)
   - Access Token: Short-lived (15 mins) for API access
   - Refresh Token: Long-lived (7 days) to get new access tokens
   
3. Token Rotation (not yet implemented here):
   - Each refresh generates a new refresh token
   - Old token is invalidated
   - Detects token theft via reuse detection
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any

from passlib.context import CryptContext
from jose import jwt

from app.core.config import settings

# Configure bcrypt password context
# - bcrypt is chosen for its adaptive nature and built-in salting
# - deprecated="auto" means old schemes will still verify but new hashes use bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain_password: The password provided by the user
        hashed_password: The bcrypt hash stored in the database
    
    Returns:
        bool: True if password matches, False otherwise
    
    Security Note:
        bcrypt verification is intentionally slow to prevent brute-force attacks.
        Time: ~100ms per verification is normal and expected.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password to hash
    
    Returns:
        str: Bcrypt hash string (includes algorithm, cost factor, salt, and hash)
    
    Example output:
        $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.wK5FeX5HxgK7Py
        └─┘└─┘└────────────────────────────────────────────────────────┘
        alg cost          salt + hash
    """
    return pwd_context.hash(password)


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a short-lived JWT access token.
    
    Args:
        subject: User identifier (typically user ID or email)
        expires_delta: Optional custom expiration time
    
    Returns:
        str: Encoded JWT access token
    
    Token Payload:
        {
            "sub": "user_id",      # Subject (who the token is for)
            "exp": 1234567890,     # Expiration timestamp
            "type": "access"       # Token type for validation
        }
    
    Security Note:
        Access tokens are short-lived (default 15 mins) because:
        - If stolen, the damage window is small
        - Forces frequent refresh, allowing us to check user status
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a long-lived JWT refresh token.
    
    Args:
        subject: User identifier (typically user ID or email)
        expires_delta: Optional custom expiration time
    
    Returns:
        str: Encoded JWT refresh token
    
    Token Rotation (Interview talking point):
        In production, we would also:
        1. Add a JTI (unique token ID) to track issued tokens
        2. Store JTI in Redis/DB
        3. On refresh, invalidate old JTI and issue new one
        4. If old JTI is reused → token theft detected → revoke family
    
    Security Note:
        Refresh tokens are stored securely (HttpOnly cookies or secure storage).
        They should NEVER be stored in localStorage.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    # In a real scenario regarding rotation, you might want to add a JTI (unique ID) here to track used tokens
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

