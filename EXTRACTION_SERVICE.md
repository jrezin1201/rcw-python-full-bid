# Extraction Service API

## Overview

This FastAPI service provides document extraction capabilities with async job processing, designed to extract structured data from Excel files (PDF support planned for Phase 2). The service is built for integration with NextJS applications and provides comprehensive QA reporting.

## Features

- **Async Job Processing**: Non-blocking document extraction using Redis Queue
- **Excel Extraction**: Robust handling of .xlsx/.xls files with merged cells, type detection, and header normalization
- **QA Reporting**: Detailed quality assurance with confidence scoring and anomaly detection
- **API Key Authentication**: Secure access via X-API-Key header
- **Job Management**: Create, poll, finalize, and download extraction results
- **CORS Support**: Configured for NextJS integration

## Quick Start

### 1. Install Dependencies

```bash
# Using Poetry (recommended)
poetry install

# Or using pip
pip install -r requirements.txt
```

### 2. Set Up Environment

Update the `.env` file with your configuration:

```env
# API Configuration
API_KEY="your-secure-api-key-here"

# Database
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=extraction_service

# Redis (for background jobs)
REDIS_HOST=localhost
REDIS_PORT=6379

# CORS (add your NextJS URL)
BACKEND_CORS_ORIGINS=["http://localhost:3000"]
```

### 3. Run Database Migrations

```bash
# Create migration for new models
alembic revision --autogenerate -m "Add extraction job models"

# Apply migrations
alembic upgrade head
```

### 4. Start Services

```bash
# Using Docker Compose (recommended)
docker-compose up -d

# Or manually:
# 1. Start PostgreSQL and Redis
# 2. Start the API server
uvicorn app.main:app --reload --port 8000

# 3. Start the background worker
rq worker default --with-scheduler
```

### 5. Generate Sample Data

```bash
# Create a sample Excel file for testing
python examples/generate_sample_excel.py
```

## API Endpoints

All extraction endpoints require the `X-API-Key` header.

### Create Extraction Job

```bash
POST /api/v1/jobs
```

**Request:**
- Multipart form data with:
  - `file`: Excel file (.xlsx or .xls)
  - `job_type`: "rc_wendt_bid_v1"

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
  -H "X-API-Key: test-api-key-change-in-production" \
  -F "file=@examples/sample_bid.xlsx" \
  -F "job_type=rc_wendt_bid_v1"
```

**Response:**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "QUEUED"
}
```

### Get Job Status

```bash
GET /api/v1/jobs/{job_id}
```

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/123e4567-e89b-12d3-a456-426614174000" \
  -H "X-API-Key: test-api-key-change-in-production"
```

**Response (Running):**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "RUNNING",
  "progress": 42,
  "result": null,
  "qa": null,
  "error": null
}
```

**Response (Completed):**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "SUCCEEDED",
  "progress": 100,
  "result": {
    "rows": [
      {
        "item_code": "MAT-001",
        "description": "Concrete Mix",
        "quantity": 150,
        "unit": "CY",
        "unit_price": 125.50,
        "total_price": 18825.00,
        "notes": "Standard mix"
      }
    ],
    "columns": ["item_code", "description", "quantity", "unit", "unit_price", "total_price", "notes"],
    "provenance": {
      "file": "sample_bid.xlsx",
      "sheet": "Bid Items",
      "extracted_at": "2024-01-15T10:30:00Z"
    }
  },
  "qa": {
    "rows_extracted": 12,
    "unmapped_columns": [],
    "empty_rows_removed": 3,
    "suspected_totals_rows": [15, 19],
    "type_anomalies": [
      {
        "type": "non_numeric_quantity",
        "header": "quantity",
        "value": "TBD",
        "row": 11,
        "message": "Expected numeric value for 'quantity', got text: 'TBD'"
      }
    ],
    "confidence": 0.85,
    "warnings": [...]
  },
  "error": null
}
```

### Download Results

```bash
GET /api/v1/jobs/{job_id}/download
```

Downloads the extraction results as a JSON file.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/123e4567-e89b-12d3-a456-426614174000/download" \
  -H "X-API-Key: test-api-key-change-in-production" \
  -o results.json
```

### Finalize Job

```bash
POST /api/v1/jobs/{job_id}/finalize
```

Makes job results immutable (cannot be modified or deleted).

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/123e4567-e89b-12d3-a456-426614174000/finalize" \
  -H "X-API-Key: test-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

### List Jobs

```bash
GET /api/v1/jobs
```

**Query Parameters:**
- `status`: Filter by status (QUEUED, RUNNING, SUCCEEDED, FAILED, FINALIZED)
- `page`: Page number (default: 1)
- `per_page`: Results per page (default: 20, max: 100)

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/jobs?status=SUCCEEDED&page=1&per_page=10" \
  -H "X-API-Key: test-api-key-change-in-production"
```

## Testing Locally

### 1. Using the Sample Excel File

```bash
# Generate sample file
python examples/generate_sample_excel.py

# Create a job
JOB_ID=$(curl -X POST "http://localhost:8000/api/v1/jobs" \
  -H "X-API-Key: test-api-key-change-in-production" \
  -F "file=@examples/sample_bid.xlsx" \
  -F "job_type=rc_wendt_bid_v1" \
  | jq -r '.job_id')

echo "Created job: $JOB_ID"

# Poll for status (repeat until status is SUCCEEDED)
curl -X GET "http://localhost:8000/api/v1/jobs/$JOB_ID" \
  -H "X-API-Key: test-api-key-change-in-production" \
  | jq '.status, .progress'

# Get full results when done
curl -X GET "http://localhost:8000/api/v1/jobs/$JOB_ID" \
  -H "X-API-Key: test-api-key-change-in-production" \
  | jq '.'
```

### 2. NextJS Integration Example

```javascript
// Example NextJS API client
class ExtractionService {
  constructor(apiUrl, apiKey) {
    this.apiUrl = apiUrl;
    this.apiKey = apiKey;
  }

  async createJob(file, jobType) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('job_type', jobType);

    const response = await fetch(`${this.apiUrl}/api/v1/jobs`, {
      method: 'POST',
      headers: {
        'X-API-Key': this.apiKey,
      },
      body: formData,
    });

    return response.json();
  }

  async getJobStatus(jobId) {
    const response = await fetch(`${this.apiUrl}/api/v1/jobs/${jobId}`, {
      headers: {
        'X-API-Key': this.apiKey,
      },
    });

    return response.json();
  }

  async pollJob(jobId, interval = 2000) {
    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const status = await this.getJobStatus(jobId);

          if (status.status === 'SUCCEEDED') {
            resolve(status);
          } else if (status.status === 'FAILED') {
            reject(new Error(status.error));
          } else {
            setTimeout(poll, interval);
          }
        } catch (error) {
          reject(error);
        }
      };

      poll();
    });
  }
}

// Usage
const extraction = new ExtractionService(
  process.env.NEXT_PUBLIC_API_URL,
  process.env.API_KEY
);

// Handle file upload
const handleFileUpload = async (file) => {
  try {
    // Create job
    const { job_id } = await extraction.createJob(file, 'rc_wendt_bid_v1');
    console.log('Job created:', job_id);

    // Poll for completion
    const result = await extraction.pollJob(job_id);
    console.log('Extraction complete:', result);

    // Process results
    if (result.qa.confidence < 0.7) {
      console.warn('Low confidence extraction:', result.qa.warnings);
    }

    return result;
  } catch (error) {
    console.error('Extraction failed:', error);
  }
};
```

## QA Report Fields

The extraction service provides comprehensive quality assurance reporting:

### Confidence Score (0-1)
- **1.0**: Perfect extraction with no issues
- **0.8-0.9**: High quality with minor issues
- **0.6-0.7**: Acceptable with some warnings
- **< 0.6**: Low confidence, manual review recommended

### Warning Types
- **unmapped_columns**: Columns without clear headers
- **type_anomaly**: Data type inconsistencies (text in numeric fields, etc.)
- **suspected_totals**: Rows that appear to be totals/summaries
- **empty_rows**: Blank rows that were filtered out
- **scientific_notation_risk**: Large numbers that may lose precision

## File Storage

Extracted files and results are stored in:
- Uploads: `./data/uploads/{job_id}/`
- Results: `./data/results/{job_id}.json`

## Performance Considerations

- **File Size**: Tested with files up to 10MB
- **Row Limit**: Optimized for up to 10,000 rows per sheet
- **Processing Time**: ~2-10 seconds for typical bid documents
- **Concurrent Jobs**: Supports multiple simultaneous extractions

## Troubleshooting

### Common Issues

1. **Job stuck in QUEUED status**
   - Check if Redis is running: `redis-cli ping`
   - Check if worker is running: `ps aux | grep "rq worker"`
   - Start worker: `rq worker default --with-scheduler`

2. **API Key not working**
   - Verify API_KEY is set in .env
   - Restart the server after changing .env
   - Check header name is exactly "X-API-Key"

3. **CORS errors from NextJS**
   - Add your NextJS URL to BACKEND_CORS_ORIGINS in .env
   - Format: `["http://localhost:3000"]`

4. **Database connection errors**
   - Check PostgreSQL is running
   - Verify database credentials in .env
   - Run migrations: `alembic upgrade head`

## API Documentation

Interactive API documentation is available at:
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

## Phase 2: PDF Support (TODO)

Future implementation will include:
- PDF text extraction with pdfplumber
- Table detection and extraction with tabula-py
- OCR support for scanned PDFs with pytesseract
- Layout analysis for complex documents

## Security Notes

- **API Key**: Change the default API key in production
- **File Uploads**: Implement file size limits and virus scanning in production
- **Rate Limiting**: Add rate limiting for production deployments
- **HTTPS**: Always use HTTPS in production

## License

This extraction service is part of the FastAPI SaaS Starter template.