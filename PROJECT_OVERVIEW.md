# Prime Identity Service - Technical Project Overview

## Executive Summary

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
   ├── Pydantic validates input (email format, password strength)
   ├── Bcrypt hashes password (12 rounds, ~300ms intentionally)
   ├── Store user in PostgreSQL
   └── Return user profile (no tokens yet)

2. LOGIN: POST /api/v1/auth/login
   ├── Find user by email
   ├── Bcrypt.verify(submitted_password, stored_hash)
   ├── Generate JWT Access Token (15 min TTL)
   ├── Generate JWT Refresh Token (7 day TTL)
   └── Return both tokens to client

3. ACCESS PROTECTED RESOURCE: GET /api/v1/users/me
   ├── Extract Bearer token from Authorization header
   ├── Decode JWT → Verify signature with SECRET_KEY
   ├── Check expiration → Reject if expired
   ├── Extract user_id from payload (sub claim)
   └── Return user data (ZERO database queries for validation!)

4. TOKEN REFRESH: POST /api/v1/auth/refresh
   ├── Client sends expired access_token + valid refresh_token
   ├── Verify refresh token is valid and not yet used
   ├── Generate NEW access_token + NEW refresh_token (Rotation!)
   ├── Invalidate old refresh_token
   └── Return new token pair
```

---

## 📊 Database Schema

### Entity Relationship Diagram

```
┌─────────────────────────────────────┐
│              USERS                   │
├─────────────────────────────────────┤
│ id              UUID (PK)            │
│ email           VARCHAR(255) UNIQUE  │  ◀── B-Tree Index
│ hashed_password VARCHAR(128)         │  ◀── Bcrypt hash (never plain text)
│ full_name       VARCHAR(100)         │
│ is_active       BOOLEAN              │  ◀── Account deactivation
│ is_superuser    BOOLEAN              │
│ created_at      TIMESTAMP            │
│ updated_at      TIMESTAMP            │
└─────────────────────────────────────┘
```

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **UUID primary keys** | Prevents sequential ID enumeration attacks |
| **Email as unique index** | Fast lookup for login, prevents duplicate accounts |
| **Bcrypt for passwords** | Adaptive hashing, intentionally slow (~300ms), salt built-in |
| **No session table** | JWTs are stateless — validation doesn't need DB queries |
| **is_active flag** | Soft-disable accounts without deleting data |

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

```python
# Token generation
def create_access_token(user_id: str) -> str:
    payload = {
        "sub": str(user_id),          # Subject (user identifier)
        "exp": datetime.utcnow() + timedelta(minutes=15),  # Short-lived!
        "type": "access"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=7),  # Long-lived
        "type": "refresh"
    }
    return jwt.encode(payload, REFRESH_SECRET_KEY, algorithm="HS256")
```

**Why Dual Tokens?**
- Access Token: Short-lived (15 min), used on every request, no DB lookup needed
- Refresh Token: Long-lived (7 days), used once to get new access token
- If access token is stolen, damage is limited to 15 minutes

### 2. Refresh Token Rotation (Theft Detection)

```python
async def refresh_tokens(refresh_token: str):
    # 1. Decode and validate
    payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=["HS256"])
    
    # 2. Check if token was already used (CRITICAL for security)
    if await is_token_used(payload["jti"]):
        # ALERT: Token reuse detected = possible theft!
        # Revoke ALL tokens for this user (force re-login)
        await revoke_all_user_tokens(payload["sub"])
        raise HTTPException(status_code=401, detail="Token reuse detected")
    
    # 3. Mark current token as used
    await mark_token_used(payload["jti"])
    
    # 4. Issue new pair
    new_access = create_access_token(payload["sub"])
    new_refresh = create_refresh_token(payload["sub"])
    
    return {"access_token": new_access, "refresh_token": new_refresh}
```

**The Security Logic:**
1. A Refresh Token can only be used **ONCE**
2. When a legitimate user refreshes, the old token is marked as "used"
3. If an attacker tries to use the old token → **Token reuse detected** → All tokens revoked → Forces re-login
4. The stolen token becomes a **tripwire** that alerts us to an attack

### 3. Bcrypt Password Hashing

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain_password: str) -> str:
    """Hash with bcrypt (12 rounds, ~300ms per hash)"""
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed: str) -> bool:
    """Verify password against stored hash"""
    return pwd_context.verify(plain_password, hashed)
```

**Why Bcrypt over SHA-256?**
| Algorithm | Speed | Security |
|-----------|-------|----------|
| MD5 | ~1 billion hashes/sec | ❌ Crackable in seconds |
| SHA-256 | ~100 million hashes/sec | ❌ Too fast for passwords |
| **Bcrypt** | **~3 hashes/sec** | ✅ Brute-force resistant |

Bcrypt is intentionally slow. With 12 rounds, each hash takes ~300ms. That's fast enough for login (one hash), but makes brute-force attacks computationally infeasible.

### 4. Async SQLAlchemy with Connection Pooling

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,           # Maintain 10 open connections
    max_overflow=20,        # Allow up to 20 extra under load
    pool_pre_ping=True,     # Verify connections before use
)
```

**Why Connection Pooling Matters for Auth:**
- Auth endpoints are hit on **every request** (token validation)
- Without pooling: Each request opens a TCP connection to PostgreSQL (~50ms overhead)
- With pooling: Reuse existing connections (~1ms overhead)
- 10 pooled connections can handle 100s of concurrent auth requests

---

## 🚀 Performance Characteristics

| Metric | Value | How |
|--------|-------|-----|
| **Token validation** | ~1ms | JWT decode is pure CPU, no DB query |
| **Login** | ~300ms | Bcrypt hash verification dominates |
| **Registration** | ~350ms | Bcrypt hash generation + DB insert |
| **Token refresh** | ~5ms | DB lookup (is token used?) + JWT generation |
| **Concurrent capacity** | 1000+ req/sec | Async I/O + connection pooling |

---

## 📁 Folder Structure

```bash
prime_auth/
├── app/
│   ├── api/
│   │   ├── deps.py            # Dependency injection (get_db, get_current_user)
│   │   └── v1/
│   │       └── endpoints/
│   │           └── auth.py    # Login, Register, Refresh, Me endpoints
│   ├── core/
│   │   ├── config.py          # Pydantic Settings (env vars)
│   │   └── security.py        # JWT + Bcrypt utilities
│   ├── crud/
│   │   └── user.py            # Database CRUD operations
│   ├── db/
│   │   ├── base.py            # Import all models for Alembic
│   │   └── session.py         # Async engine + session factory
│   ├── models/
│   │   └── user.py            # SQLAlchemy User model
│   ├── schemas/
│   │   ├── auth.py            # Login/Register request schemas
│   │   └── user.py            # User response schemas
│   └── main.py                # FastAPI app entry point
├── tests/
│   ├── conftest.py            # Test fixtures (in-memory SQLite DB)
│   └── test_auth.py           # Auth endpoint tests
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## 🔌 API Reference

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/auth/register` | Create new user account | ❌ |
| `POST` | `/api/v1/auth/login` | Login, get tokens | ❌ |
| `POST` | `/api/v1/auth/refresh` | Refresh expired access token | 🔄 Refresh Token |
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
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "pruthvi@example.com",
    "full_name": "Pruthviraj Kakade",
    "is_active": true
}
```

```json
// POST /api/v1/auth/login
// Request:
{
    "email": "pruthvi@example.com",
    "password": "SecurePass123!"
}

// Response (200):
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
}
```

---

## 🧪 Running the Project

### Quick Start (Docker)

```bash
cd prime_auth
docker-compose up --build

# Access:
# - API: http://localhost:8000
# - Swagger Docs: http://localhost:8000/docs
# - Health: http://localhost:8000/health
```

### Local Development

```bash
cd prime_auth
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### Running Migrations

```bash
# Create a migration after changing models
alembic revision --autogenerate -m "Added phone number to user"

# Apply changes to DB
alembic upgrade head
```

### Running Tests

```bash
pytest tests/ -v
# Note: conftest.py spins up an in-memory SQLite DB, so tests never touch your local Postgres
```

---

## 📈 Interview Q&A

### Q1: "Explain the JWT structure and how validation works without a database."

> "A JWT has three parts: Header.Payload.Signature. The Header specifies the algorithm (HS256). The Payload contains claims like user_id and expiration. The Signature is `HMAC-SHA256(header + payload, SECRET_KEY)`.
>
> **Validation requires ZERO database queries:**
> 1. Take the header and payload from the incoming token
> 2. Recalculate the signature using the server's SECRET_KEY
> 3. Compare with the attached signature — if they match, the token is authentic
> 4. Check the `exp` claim — if expired, reject
>
> This is why JWTs enable stateless scaling — any server instance with the SECRET_KEY can validate tokens independently."

### Q2: "Why Refresh Token Rotation over simple long-lived tokens?"

> "A simple long-lived access token (e.g., 7 days) means an attacker who steals it has a 7-day window of access with no way to detect or revoke it.
>
> Refresh Token Rotation solves this:
> 1. Access tokens are short-lived (15 min) — limits damage window
> 2. Refresh tokens are single-use — each refresh issues a completely new pair
> 3. **Token reuse detection** — if an old refresh token is used again, it means theft. We revoke ALL tokens for that user, forcing re-login
>
> The stolen token becomes a tripwire that triggers automatic account protection."

### Q3: "How would you scale this for 10,000 logins per second?"

> "The architecture scales very well:
> 1. **Stateless JWTs** — No session storage needed. Any server can validate tokens, enabling horizontal scaling behind a load balancer
> 2. **Connection pooling** — asyncpg with pool_size=10 handles hundreds of concurrent DB operations per instance
> 3. **Read replicas** — Login reads (find user by email) can go to PostgreSQL replicas
> 4. **Redis for token blacklist** — Instead of DB checks for revoked tokens, use Redis SET with TTL matching token expiration
> 5. **Rate limiting** — Prevent brute-force with Redis-backed rate limiting per email/IP
>
> The main bottleneck is Bcrypt (300ms per hash), but that's by design — it's the security trade-off that prevents brute-force attacks."

### Q4: "What's the difference between Authentication and Authorization?"

> "**Authentication** = 'Who are you?' — Verifying identity via credentials (what Prime Auth handles)
> **Authorization** = 'What can you do?' — Checking permissions/roles (RBAC)
>
> In Prime Auth, I implement authentication. The `is_superuser` flag is a simple authorization check, but for full RBAC (roles, permissions, scopes), I'd add a roles table and middleware that checks permissions per endpoint."

---

## 🎯 Skills Demonstrated

| Category | Technologies |
|----------|-------------|
| **Backend** | Python, FastAPI, Async/Await, Pydantic v2 |
| **Security** | JWT (HS256), OAuth2, Bcrypt, Token Rotation, Brute-force Protection |
| **Database** | PostgreSQL, Async SQLAlchemy 2.0, Connection Pooling, Alembic Migrations |
| **Architecture** | Dependency Injection, Clean Architecture, Stateless Design |
| **Testing** | Pytest, pytest-asyncio, In-memory SQLite Test DB |
| **DevOps** | Docker, Docker Compose, Environment Configuration |
