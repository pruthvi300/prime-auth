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
        API -->|Business Logic| Service[Service Layer]
        Service -->|CRUD| DB_Layer[SQLAlchemy Async]
        Service -->|Hash/Verify| Security[Bcrypt & JWT Provider]
    end
    
    DB_Layer -->|Async Driver| DB[(PostgreSQL)]
```

## 🚀 Key Technical Features

### Security First
- **JWT & Refresh Token Rotation**: Implements dual-token architecture to minimize access token lifespan while maintaining user session UX.
- **Bcrypt Hashing**: Industry-standard adaptive hashing for password storage.
- **Input Validation**: Rigorous data validation using **Pydantic v2**, ensuring type safety at the API boundary.

### High Performance
- **Fully Asynchronous**: Built on `asyncio` and SQLAlchemy Async to handle high-concurrency workloads non-blockingly.
- **Database Optimization**: Uses connection pooling and optimized queries.

## 🛠 Tech Stack

| Component | Technology | Reasoning |
|-----------|------------|-----------|
| **Framework** | **FastAPI** | High performance, auto-generated OpenAPI docs, native async support. |
| **Database** | **PostgreSQL** | Reliable OLTP database suitable for structured user data. |
| **ORM** | **SQLAlchemy (Async)** | Powerful ORM with modern async support (v2.0 style). |
| **Validation** | **Pydantic v2** | The fastest data validation library for Python, core to FastAPI. |
| **Auth** | **PyJWT + Passlib** | Standard, battle-tested libraries for token and password handling. |

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
    pip install -r requirements.txt
    ```

2. **Configuration**
    Copy `.env.example` to `.env` and configure your local Postgres credentials.

3. **Run Application**
    ```bash
    uvicorn app.main:app --reload
    ```
    Access documentation at: `http://localhost:8000/docs`

## 🧪 Testing

We use **Pytest** for ensuring reliability.

```bash
pytest tests/ -v
```
