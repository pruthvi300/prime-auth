# Prime Auth — Design Notes

Deeper notes on how the service works and why it is built this way. For setup, see the [README](../README.md).

## Overview

**Prime Auth** is a high-performance, asynchronous authentication microservice designed to handle identity management for modern web and mobile applications. It implements industry-standard security protocols (OAuth2, JWT) with a non-blocking architecture built for horizontal scalability.

**Problem Statement:** Authentication is the most security-critical component of any application. How do you build a stateless auth system that scales horizontally while maintaining robust security against token theft and brute-force attacks?

**Solution:** Dual-token JWT architecture with Refresh Token Rotation for theft detection, Bcrypt adaptive hashing for password security, and fully async FastAPI + SQLAlchemy for high-concurrency handling.

---

## 🏗️ Architecture Deep Dive

### High-Level System Design

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    Prime Auth Architecture                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│    ┌──────────────┐                                                      │
│    │  Client App  │                                                      │
│    │ (Web/Mobile) │                                                      │
│    └───────┬──────┘                                                      │
│            │ HTTPS/JSON                                                   │
│            ▼                                                              │
│    ┌──────────────────────────────────────────────────────┐              │
│    │              Load Balancer / API Gateway             │              │
│    └────────────────────────┬─────────────────────────────┘              │
│                             │                                             │
│                             ▼                                             │
│    ┌──────────────────────────────────────────────────────┐              │
│    │                  FastAPI (ASGI)                      │              │
│    │                  Uvicorn Workers                     │              │
│    ├──────────────────────────────────────────────────────┤              │
│    │                                                      │              │
│    │  ┌────────────┐  ┌────────────┐  ┌──────────────┐    │              │
│    │  │  Pydantic   │  │  Service   │  │   Security   │  │              │
│    │  │  Validation │  │   Layer    │  │   Layer      │  │              │
│    │  │  (Schemas)  │  │  (CRUD)    │  │  (JWT+Bcrypt)│  │              │
│    │  └────────────┘  └─────┬──────┘  └──────────────┘  │              │
│    │                        │                             │              │
│    └────────────────────────┼─────────────────────────────┘              │
│                             │                                             │
│                             ▼                                             │
│                    ┌────────────────┐                                     │
│                    │  PostgreSQL    │                                     │
│                    │  (Async Driver)│                                     │
│                    │  Port: 5432    │                                     │
│                    └────────────────┘                                     │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Request Flow: Authentication

```
1. REGISTRATION: POST /api/v1/auth/register
   ├── Pydantic validates input (email format, 8–72 byte password)
   ├── Email is normalised to lower case
   ├── Bcrypt hashes password (cost 12)
   ├── Store user in PostgreSQL (409 if the email exists)
   └── Return user profile (201, no tokens)

2. LOGIN: POST /api/v1/auth/login   (form fields: username=email, password)
   ├── Rate limited per IP (default 5/minute)
   ├── Find user by email; unknown emails still run a bcrypt check (no timing leak)
   ├── Generate JWT access token (15 min TTL)
   ├── Generate JWT refresh token (7 day TTL) with a unique jti and a new family id
   ├── Store the refresh token's jti in the refresh_token table
   └── Return both tokens

3. ACCESS PROTECTED RESOURCE: GET /api/v1/users/me
   ├── Extract Bearer token from Authorization header
   ├── Verify signature, expiry, and type == "access"
   ├── Load the user by id and reject inactive users
   └── Return user profile

4. TOKEN REFRESH: POST /api/v1/auth/refresh   (JSON body: {"refresh_token": ...})
   ├── Verify signature, expiry, and type == "refresh"
   ├── Atomically mark the jti as used (UPDATE ... WHERE revoked_at IS NULL)
   ├── If it was already used → revoke the whole family → 401
   ├── Issue a new access token and a new refresh token in the same family
   └── Return the new pair

5. LOGOUT: POST /api/v1/auth/logout   (JSON body: {"refresh_token": ...})
   └── Revoke every refresh token in that login session's family → 204
```

---

## 📊 Database Schema

```
┌─────────────────────────────────────┐       ┌──────────────────────────────────────┐
│                user                  │       │            refresh_token             │
├─────────────────────────────────────┤       ├──────────────────────────────────────┤
│ id              INTEGER (PK)         │◀──┐   │ jti         VARCHAR(32) (PK)         │
│ email           VARCHAR(320) UNIQUE  │   └───│ user_id     INTEGER FK → user.id     │
│ hashed_password VARCHAR(128)         │       │ family_id   VARCHAR(32)  (indexed)   │
│ full_name       VARCHAR(200)         │       │ expires_at  TIMESTAMPTZ              │
│ is_active       BOOLEAN              │       │ revoked_at  TIMESTAMPTZ NULL         │
│ is_superuser    BOOLEAN              │       └──────────────────────────────────────┘
│ created_at      TIMESTAMPTZ          │
└─────────────────────────────────────┘
```

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Email as unique index** | Fast lookup for login, prevents duplicate accounts |
| **Bcrypt for passwords** | Adaptive hashing, intentionally slow, salt built-in |
| **Refresh tokens tracked by jti** | Needed for rotation, reuse detection, and logout. Access tokens stay stateless. |
| **Token families** | Reuse in one login session revokes only that session, not the user's other devices |
| **is_active flag** | Soft-disable accounts without deleting data |
| **Alembic migrations** | Schema changes are versioned; the container runs `alembic upgrade head` on start |

---

## 🏗️ System Architecture Deep Dive

### The Asynchronous Event Loop

Unlike traditional WSGI frameworks (Flask, Django) that use a **thread-per-request** model, this service runs on **ASGI (Asynchronous Server Gateway Interface)** via `uvicorn`.

- **How it works**: A single event loop manages thousands of concurrent connections. When an API request hits an `await` point (like a DB query), the loop pauses that task and handles another request.
- **Why it matters**: This results in **massive throughput** for I/O-bound operations (like authentication checks), making it ideal for a high-traffic identity provider.

### Dependency Injection (DI) System

We rely heavily on FastAPI's DI system (`Depends`).

- **Pattern**: `app/api/deps.py` defines reusable logic (like `get_db` or `get_current_user`).
- **Benefits**:
  1. **Testability**: We can easily override `get_db` in tests to use an in-memory SQLite database.
  2. **Clean Code**: Route handlers focus purely on business logic, not database connection management.
  3. **Security Chain**: `get_current_user` depends on `get_db` + JWT decode — FastAPI resolves the entire chain automatically.

---

## 🔑 Key Technical Decisions

### 1. JWT Dual-Token Architecture

Tokens are signed with PyJWT (HS256). See `app/core/security.py`.

```python
def create_access_token(user_id) -> str:
    return _encode({"sub": str(user_id), "type": "access"}, timedelta(minutes=15))

def create_refresh_token(user_id, family_id) -> tuple[str, str, datetime]:
    jti = uuid.uuid4().hex
    token = _encode({"sub": str(user_id), "type": "refresh", "jti": jti, "fam": family_id}, timedelta(days=7))
    return token, jti, expires_at
```

`decode_token(token, expected_type)` requires `exp`, `sub` and `type`, so an access token can never be used as a refresh token or the other way round.

**Why Dual Tokens?**
- Access token: short-lived (15 min), sent on every request
- Refresh token: long-lived (7 days), used only to get a new pair
- If an access token is stolen, the damage window is 15 minutes

### 2. Refresh Token Rotation (Theft Detection)

See `app/crud/crud_token.py`.

```python
async def consume(db, jti):
    # Only matches a token that has not been used yet, so two concurrent
    # refreshes with the same token cannot both succeed.
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.jti == jti, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    row = await db.get(RefreshToken, jti)
    if row is None:
        raise InvalidTokenError("unknown refresh token")
    if result.rowcount == 0:          # already used → reuse → theft
        await revoke_family(db, row.family_id)
        raise RefreshTokenReuse
    return row
```

**The Security Logic:**
1. A refresh token can only be used **once**
2. Each login starts a new token *family*; rotation keeps the family id
3. If an old token is presented again, the whole family is revoked, so both the attacker and the real user must log in again
4. Other login sessions (other devices) are not affected

### 3. Bcrypt Password Hashing

The `bcrypt` library is used directly (passlib is unmaintained and breaks with bcrypt 4.1+).

```python
def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

Bcrypt only uses the first 72 bytes of a password, so the API rejects longer passwords instead of silently truncating them. Login runs a dummy bcrypt check for unknown emails so response time does not reveal which emails exist.

### 4. Async SQLAlchemy with Connection Pooling

```python
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_size=settings.DB_POOL_SIZE,        # default 10
    max_overflow=settings.DB_MAX_OVERFLOW,  # default 20
    pool_pre_ping=True,
)
```

### 5. Rate Limiting

`slowapi` limits `/auth/login` (5/minute) and `/auth/register` (10/hour) per client IP. Counters live in memory, which is correct for one instance. For several replicas, point the limiter at Redis so all instances share counters.

---

## 🚀 Performance Notes

These are expectations from the design, not measured benchmarks.

| Operation | Dominant cost |
|-----------|---------------|
| Access-token check | JWT signature check plus one primary-key lookup |
| Login / register | One bcrypt operation (cost 12, roughly 200–300 ms) |
| Token refresh | Two small UPDATE/SELECT statements plus JWT signing |

---


## 🔌 API Reference

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/auth/register` | Create new user account | ❌ |
| `POST` | `/api/v1/auth/login` | Login, get tokens (form data) | ❌ |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token, get new pair | 🔄 Refresh Token |
| `POST` | `/api/v1/auth/logout` | Revoke the login session | 🔄 Refresh Token |
| `GET` | `/api/v1/users/me` | Get current user profile | ✅ Access Token |
| `GET` | `/health` | Health check | ❌ |

### Request/Response Examples

```json
// POST /api/v1/auth/register
// Request:
{
    "email": "pruthvi@example.com",
    "password": "SecurePass123!",
    "full_name": "Pruthviraj Kakade"
}

// Response (201):
{
    "id": 1,
    "email": "pruthvi@example.com",
    "full_name": "Pruthviraj Kakade",
    "is_active": true,
    "created_at": "2026-11-07T10:00:00Z"
}
```

```bash
# POST /api/v1/auth/login  (OAuth2 password flow uses form data)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=pruthvi@example.com" -d "password=SecurePass123!"

# Response (200):
# {"access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer"}
```

