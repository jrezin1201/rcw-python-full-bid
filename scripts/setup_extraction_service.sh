#!/bin/bash
# Setup script for the Extraction Service
# This script creates necessary directories, runs migrations, and generates sample data

set -e  # Exit on error

echo "========================================="
echo "Extraction Service Setup Script"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if we're in the project root
if [ ! -f "pyproject.toml" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Step 1: Create necessary directories
echo ""
echo "Step 1: Creating directories..."
mkdir -p data/uploads
mkdir -p data/results
mkdir -p data/temp
print_status "Created data directories"

# Step 2: Check environment file
echo ""
echo "Step 2: Checking environment configuration..."
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Creating from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_status "Created .env file from template"
    else
        print_error ".env file not found. Please create one based on the documentation"
        exit 1
    fi
else
    print_status ".env file found"
fi

# Check for API_KEY in .env
if grep -q "API_KEY=" .env; then
    print_status "API_KEY is configured"
else
    print_warning "API_KEY not found in .env. Adding default..."
    echo 'API_KEY="test-api-key-change-in-production"' >> .env
    print_status "Added default API_KEY to .env (please change in production)"
fi

# Step 3: Install Python dependencies
echo ""
echo "Step 3: Installing Python dependencies..."
if command -v poetry &> /dev/null; then
    poetry install
    print_status "Dependencies installed with Poetry"
else
    print_warning "Poetry not found. Attempting pip install..."
    pip install -r requirements.txt
    print_status "Dependencies installed with pip"
fi

# Step 4: Check database connection
echo ""
echo "Step 4: Checking database connection..."
python -c "
from app.core.config import settings
from sqlalchemy import create_engine
try:
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    conn = engine.connect()
    conn.close()
    print('Database connection successful')
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
" || {
    print_error "Database connection failed. Please check your PostgreSQL settings in .env"
    echo "Make sure PostgreSQL is running and the database exists"
    echo "You can create the database with: createdb extraction_service"
    exit 1
}
print_status "Database connection verified"

# Step 5: Run database migrations
echo ""
echo "Step 5: Running database migrations..."

# Check if there are any existing migrations
if ls alembic/versions/*.py 2>/dev/null | grep -v __pycache__ > /dev/null; then
    print_status "Found existing migrations"
    alembic upgrade head
    print_status "Applied existing migrations"
else
    print_warning "No migrations found. Creating initial migration..."
    alembic revision --autogenerate -m "Add extraction job models"
    print_status "Created initial migration"
    alembic upgrade head
    print_status "Applied initial migration"
fi

# Step 6: Generate sample Excel file
echo ""
echo "Step 6: Generating sample data..."
if [ -f "examples/generate_sample_excel.py" ]; then
    python examples/generate_sample_excel.py
    print_status "Sample Excel file created"
else
    print_warning "Sample generator not found. Skipping..."
fi

# Step 7: Check Redis connection
echo ""
echo "Step 7: Checking Redis connection..."
python -c "
import redis
from app.core.config import settings
try:
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
    r.ping()
    print('Redis connection successful')
except Exception as e:
    print(f'Redis connection failed: {e}')
    exit(1)
" || {
    print_warning "Redis connection failed. Background jobs will not work."
    echo "To install Redis:"
    echo "  macOS: brew install redis && brew services start redis"
    echo "  Ubuntu: sudo apt-get install redis-server"
    echo "  Docker: docker run -d -p 6379:6379 redis"
}

# Step 8: Print next steps
echo ""
echo "========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Start the API server:"
echo "   uvicorn app.main:app --reload --port 8000"
echo ""
echo "2. Start the background worker (in another terminal):"
echo "   rq worker default --with-scheduler"
echo ""
echo "3. Test the API:"
echo "   curl -X POST \"http://localhost:8000/api/v1/jobs\" \\"
echo "     -H \"X-API-Key: test-api-key-change-in-production\" \\"
echo "     -F \"file=@examples/sample_bid.xlsx\" \\"
echo "     -F \"job_type=rc_wendt_bid_v1\""
echo ""
echo "4. View API documentation:"
echo "   http://localhost:8000/api/v1/docs"
echo ""
echo "For more information, see EXTRACTION_SERVICE.md"