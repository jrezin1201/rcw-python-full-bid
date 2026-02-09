# FastAPI SaaS Starter Template

A production-ready FastAPI starter template designed for building SaaS backends, APIs, background jobs, and data pipelines that complement Next.js frontends.

## Features

- **FastAPI** with Pydantic v2 for high-performance API development
- **SQLModel** ORM with PostgreSQL for type-safe database operations
- **Alembic** migrations for database schema management
- **Redis** for caching and message queuing
- **RQ (Redis Queue)** for background job processing
- **JWT Authentication** with role-based access control (RBAC)
- **Async-ready** architecture for high concurrency
- **Structured logging** with JSON output for production
- **OpenAPI docs** automatically generated
- **Comprehensive test suite** with pytest
- **Docker** and docker-compose for local development
- **Type hints** throughout the codebase

## Project Structure

```
.
├── app/
│   ├── api/
│   │   ├── deps.py              # Dependency injection
│   │   └── routes/              # API route handlers
│   │       ├── auth.py          # Authentication endpoints
│   │       ├── health.py        # Health check endpoints
│   │       ├── jobs.py          # Background job endpoints
│   │       └── users.py         # User management endpoints
│   ├── core/
│   │   ├── config.py            # Application settings
│   │   ├── logging.py           # Logging configuration
│   │   └── security.py          # Security utilities (JWT, passwords)
│   ├── db/
│   │   └── session.py           # Database session management
│   ├── models/
│   │   └── user.py              # SQLModel database models
│   ├── schemas/
│   │   ├── token.py             # Pydantic schemas for tokens
│   │   └── user.py              # Pydantic schemas for users
│   ├── services/
│   │   └── user_service.py      # Business logic layer
│   ├── workers/
│   │   ├── queue.py             # RQ queue configuration
│   │   └── tasks.py             # Background task definitions
│   └── main.py                  # Application entry point
├── alembic/                     # Database migrations
├── tests/                       # Test suite
├── scripts/                     # Utility scripts
├── docker-compose.yml           # Docker services configuration
├── Dockerfile                   # Application container
├── pyproject.toml              # Dependencies and tooling
└── README.md

```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (recommended)
- OR PostgreSQL 16+ and Redis 7+ (if running locally)

### Option 1: Docker (Recommended)

1. **Clone and setup**
   ```bash
   git clone <your-repo-url>
   cd fastapi-saas-starter
   cp .env.example .env
   ```

2. **Start all services**
   ```bash
   docker-compose up -d
   ```

   This starts:
   - PostgreSQL (port 5432)
   - Redis (port 6379)
   - FastAPI API (port 8000)
   - RQ Worker (background jobs)

3. **Access the application**
   - API: http://localhost:8000
   - Interactive API docs: http://localhost:8000/api/v1/docs
   - Alternative docs: http://localhost:8000/api/v1/redoc

4. **View logs**
   ```bash
   docker-compose logs -f api
   docker-compose logs -f worker
   ```

### Option 2: Local Development

1. **Install dependencies**
   ```bash
   pip install poetry
   poetry install
   ```

2. **Setup environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database and Redis credentials
   ```

3. **Start PostgreSQL and Redis**
   ```bash
   # Using Docker for just the databases
   docker-compose up -d postgres redis
   ```

4. **Run migrations**
   ```bash
   alembic upgrade head
   ```

5. **Start the API server**
   ```bash
   uvicorn app.main:app --reload
   ```

6. **Start the RQ worker** (in another terminal)
   ```bash
   rq worker default --with-scheduler
   ```

## Usage

### Authentication

#### Register a new user
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "full_name": "John Doe"
  }'
```

#### Login
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=securepassword123"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Access protected routes
```bash
curl -X GET "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer <your-access-token>"
```

### Background Jobs

#### Enqueue a job
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/example?name=my-task&duration=5" \
  -H "Authorization: Bearer <your-access-token>"
```

#### Check job status
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/<job-id>/status" \
  -H "Authorization: Bearer <your-access-token>"
```

### Default Admin User

A default admin user is created on first startup:
- **Email:** admin@example.com
- **Password:** changethis123

**Important:** Change these credentials in production!

## Database Migrations

### Create a new migration
```bash
alembic revision --autogenerate -m "describe your changes"
# OR use the helper script
./scripts/create_migration.sh "describe your changes"
```

### Apply migrations
```bash
alembic upgrade head
# OR use the helper script
./scripts/migrate.sh
```

### Rollback migration
```bash
alembic downgrade -1
```

## Testing

### Run all tests
```bash
pytest
```

### Run smoke tests (fast confidence)
```bash
pytest -m smoke
```

### Run with coverage
```bash
pytest --cov=app --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_auth.py -v
```

## Repository Hygiene

- Active automated tests live in `tests/`.
- Archived one-off scripts have been moved to `archive/legacy_scripts`.
- Historical reports/notes have been moved to `docs/archive`.

## Architecture Overview

### Layer Separation

1. **API Layer** (`app/api/routes/`)
   - Handles HTTP requests/responses
   - Input validation with Pydantic
   - Minimal business logic

2. **Service Layer** (`app/services/`)
   - Contains business logic
   - Orchestrates database operations
   - Reusable across different endpoints

3. **Data Layer** (`app/models/`)
   - SQLModel models for database tables
   - Database schema definitions

4. **Schema Layer** (`app/schemas/`)
   - Pydantic models for API contracts
   - Request/response validation
   - Decoupled from database models

### Authentication & Authorization

- **JWT tokens** for stateless authentication
- **OAuth2 password flow** for token generation
- **Role-based access control** (admin/user roles)
- **Dependency injection** for protected routes

### Background Jobs

- **RQ (Redis Queue)** for async task processing
- **Worker process** runs independently
- **Job status tracking** via job IDs
- Examples: email sending, data processing, long-running operations

### Logging

- **Structured JSON logging** in production
- **Human-readable format** in development
- **Automatic request/response logging**
- **Contextual logging** with service name and version

## Extending the Template

### Adding a New Model

1. Create model in `app/models/`:
```python
from sqlmodel import Field, SQLModel
from typing import Optional

class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    price: float
```

2. Create schemas in `app/schemas/`:
```python
from pydantic import BaseModel

class ProductCreate(BaseModel):
    name: str
    price: float

class ProductResponse(BaseModel):
    id: int
    name: str
    price: float

    model_config = {"from_attributes": True}
```

3. Create service in `app/services/`:
```python
from sqlmodel import Session, select
from app.models.product import Product

class ProductService:
    @staticmethod
    def create(session: Session, product_create: ProductCreate) -> Product:
        db_product = Product(**product_create.model_dump())
        session.add(db_product)
        session.commit()
        session.refresh(db_product)
        return db_product
```

4. Create routes in `app/api/routes/`:
```python
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.db.session import get_session

router = APIRouter(prefix="/products", tags=["products"])

@router.post("/", response_model=ProductResponse)
def create_product(
    product: ProductCreate,
    session: Session = Depends(get_session),
):
    return ProductService.create(session, product)
```

5. Register router in `app/main.py`:
```python
from app.api.routes import products
app.include_router(products.router, prefix=settings.API_V1_PREFIX)
```

6. Create migration:
```bash
alembic revision --autogenerate -m "add products table"
alembic upgrade head
```

### Adding a New Background Task

1. Define task in `app/workers/tasks.py`:
```python
def process_invoice(invoice_id: int) -> dict:
    logger.info(f"Processing invoice {invoice_id}")
    # Your processing logic here
    return {"invoice_id": invoice_id, "status": "processed"}
```

2. Create endpoint to enqueue in `app/api/routes/jobs.py`:
```python
@router.post("/process-invoice")
def create_invoice_job(
    invoice_id: int,
    current_user: User = Depends(get_current_active_user),
):
    job_id = enqueue_task(process_invoice, invoice_id=invoice_id)
    return {"job_id": job_id, "task": "process_invoice"}
```

## Production Deployment

### Environment Variables

Ensure these are set in production:

```bash
# Security - CRITICAL
SECRET_KEY=<generate-a-strong-secret-key>
FIRST_SUPERUSER_PASSWORD=<strong-password>

# Database
POSTGRES_SERVER=<your-db-host>
POSTGRES_PASSWORD=<strong-password>

# Application
DEBUG=False
```

### Generate Secret Key

```python
import secrets
print(secrets.token_urlsafe(32))
```

### Docker Production Build

```bash
docker build -t fastapi-saas:latest .
docker run -p 8000:8000 --env-file .env.production fastapi-saas:latest
```

### Scaling Workers

```bash
docker-compose up -d --scale worker=3
```

## Common Commands

```bash
# Development
poetry install                    # Install dependencies
poetry add <package>             # Add new dependency
uvicorn app.main:app --reload    # Run dev server

# Docker
docker-compose up -d             # Start all services
docker-compose down              # Stop all services
docker-compose logs -f api       # View API logs
docker-compose exec api bash     # Shell into API container

# Database
alembic upgrade head             # Apply migrations
alembic downgrade -1             # Rollback one migration
alembic revision --autogenerate  # Create migration

# Testing
pytest                           # Run all tests
pytest -v                        # Verbose output
pytest --cov=app                 # With coverage
pytest -k "test_auth"           # Run specific tests

# Code Quality
black .                          # Format code
ruff check .                     # Lint code
mypy app                         # Type check
```

## Troubleshooting

### Database connection errors
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres

# Recreate database
docker-compose down -v
docker-compose up -d postgres
```

### Redis connection errors
```bash
# Check if Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

### Worker not processing jobs
```bash
# Check worker logs
docker-compose logs -f worker

# Restart worker
docker-compose restart worker

# Check Redis queue
docker-compose exec redis redis-cli LLEN rq:queue:default
```

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions, please open a GitHub issue.
