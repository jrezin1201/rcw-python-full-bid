# Quick Start - Local Development with SQLite

The fastest way to get the Takeoff Extraction Service running locally.

## 1-Minute Setup

```bash
# 1. Clone and enter the directory
cd rcw-extract

# 2. Install dependencies
poetry install
# OR
pip install -r requirements.txt

# 3. Set environment variables (SQLite - no database server needed!)
export DATABASE_URL="sqlite:///./data/dev.db"
export API_KEY="test-api-key"
export DISABLE_BOOTSTRAP_USERS=true  # Skip user creation (we use API keys)

# 4. Create data directory
mkdir -p data

# 5. Start the server
uvicorn app.main:app --reload --port 8000
```

That's it! The service is now running at http://localhost:8000

## Test the API

### 1. Check API Docs
Open http://localhost:8000/api/v1/docs in your browser

### 2. Create a Test Job

```bash
# Generate test Excel file
python tests/test_data/generate_test_files.py

# Upload the file
curl -X POST "http://localhost:8000/api/v1/jobs" \
  -H "X-API-Key: test-api-key" \
  -F "file=@tests/test_data/standard_takeoff.xlsx" \
  -F "template=rc_wendt_v1"
```

### 3. Check Job Status

```bash
# Replace {job_id} with the ID from the previous response
curl "http://localhost:8000/api/v1/jobs/{job_id}" \
  -H "X-API-Key: test-api-key" | python -m json.tool
```

## What Just Happened?

1. **SQLite Database**: Automatically created at `./data/dev.db` - no server needed!
2. **File Storage**: Uploads saved to `./data/uploads/`
3. **Background Processing**: Jobs run async with FastAPI BackgroundTasks
4. **API Key Auth**: Protected by `X-API-Key` header

## NextJS Integration

```javascript
// Your NextJS app can now connect:
const API_URL = 'http://localhost:8000';
const API_KEY = 'test-api-key';

const response = await fetch(`${API_URL}/api/v1/jobs`, {
  method: 'POST',
  headers: { 'X-API-Key': API_KEY },
  body: formData
});
```

## Troubleshooting

### Permission Denied on data/dev.db
```bash
chmod 755 data
chmod 644 data/dev.db
```

### Port 8000 Already in Use
```bash
# Use a different port
uvicorn app.main:app --reload --port 8001
```

### Module Not Found
```bash
# Make sure you're in the right directory and dependencies are installed
poetry install
# OR
pip install openpyxl fuzzywuzzy python-Levenshtein sqlmodel fastapi uvicorn
```

## Production Setup

When ready for production, switch to PostgreSQL:

1. Remove `DATABASE_URL` from environment
2. Set PostgreSQL variables:
   ```bash
   export POSTGRES_SERVER=your-server
   export POSTGRES_USER=your-user
   export POSTGRES_PASSWORD=your-password
   export POSTGRES_DB=takeoff_service
   ```

Or use a direct DATABASE_URL:
```bash
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
```