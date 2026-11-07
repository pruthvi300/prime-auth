# Prime Identity Service

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

A high-performance, asynchronous **Identity & Access Management (IAM) Microservice** designed for scalability and security. Built with modern Python tooling to handle authentication, token management, and user security policies.

## 🏗 System Architecture

The service follows a clean architecture pattern, separating concerns between API, Core Logic, and Data Access layers.

```mermaid
graph TD
    Client[Client App (Web/Mobile)] -->|HTTPS/JSON| LB[Load Balancer]
    LB -->|Requests| API[FastAPI Layer]
    
    subgraph "Prime Auth Service"
        API -->|Validate| Schema[Pydantic v2 Schemas]
        API -->|Business Logic| CRUD[CRUD Layer]
        CRUD -->|Queries| DB_Layer[SQLAlchemy Async]
        API -->|Hash/Verify| Security[Bcrypt & JWT]
    end
    
    DB_Layer -->|Async Driver| DB[(PostgreSQL)]
```

## 🚀 Key Technical Features

### Security First
- **JWT access + refresh tokens**: 15-minute access tokens and 7-day refresh tokens, each with a `type` claim so they can't be swapped.
- **Refresh token rotation with reuse detection**: every refresh token is single-use. Replaying an old one revokes that whole login session.
- **Bcrypt hashing** (cost 12) with timing-safe login, so response time doesn't reveal which emails are registered.
- **Rate limiting** on login and registration (slowapi).
- **Input validation** with Pydantic v2: email format, 8–72 byte passwords, and no client-controlled flags like `is_active`.

### Production Basics
- **Fully asynchronous**: FastAPI + SQLAlchemy 2.0 async + asyncpg with a configurable connection pool.
- **Alembic migrations**, applied automatically when the container starts.
- **CI**: ruff, pytest with coverage, and a migration drift check against real PostgreSQL.

## 🛠 Tech Stack

| Component | Technology | Reasoning |
|-----------|------------|-----------|
| **Framework** | **FastAPI** | High performance, auto-generated OpenAPI docs, native async support. |
| **Database** | **PostgreSQL** | Reliable OLTP database suitable for structured user data. |
| **ORM** | **SQLAlchemy (Async)** | Powerful ORM with modern async support (v2.0 style). |
| **Validation** | **Pydantic v2** | The fastest data validation library for Python, core to FastAPI. |
| **Auth** | **PyJWT + bcrypt** | Maintained, widely used libraries for tokens and password hashing. |

## 📦 Project Structure

```bash
prime_auth/
├── app/
│   ├── api/            # Route handlers (v1, ...)
│   ├── core/           # Security, Config, Middleware
│   ├── db/             # Database connection & Session management
│   ├── models/         # SQLAlchemy ORM Models
│   ├── schemas/        # Pydantic Request/Response Models
│   └── crud/           # Database Access Objects (DAOs)
├── tests/              # Pytest Integration & Unit tests
└── docker-compose.yml  # Container orchestration
```

## ⚡️ Quick Start

### Prerequisites
- Python 3.10+
- Docker & Docker Compose

### Running with Docker (Recommended)

```bash
# Start the database and application
docker-compose up -d --build

# View Logs
docker-compose logs -f
```

### Local Development Setup

1. **Environment Setup**
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements-dev.txt
    ```

2. **Configuration**
    Copy `.env.example` to `.env` and configure your local Postgres credentials.

3. **Run Migrations and the Application**
    ```bash
    alembic upgrade head
    uvicorn app.main:app --reload
    ```
    Access documentation at: `http://localhost:8000/docs`

## 🧪 Testing

We use **Pytest** for ensuring reliability.

```bash
pytest          # 13 tests, in-memory SQLite, no Postgres needed
ruff check app tests alembic
```

## 🔌 Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/auth/register` | Create an account |
| POST | `/api/v1/auth/login` | OAuth2 password login (form data), returns token pair |
| POST | `/api/v1/auth/refresh` | Rotate a refresh token |
| POST | `/api/v1/auth/logout` | Revoke the login session |
| GET | `/api/v1/users/me` | Current user (Bearer access token) |
| GET | `/health` | Liveness check |
