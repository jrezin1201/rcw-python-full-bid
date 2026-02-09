# Takeoff Extraction Service

A deterministic Excel extraction service that normalizes construction takeoff data and maps it to predefined sections/items using fuzzy matching.

## Overview

This service processes Excel files from takeoff programs with the following format:
- **Columns**: Classification | Quantity | Quantity1 UOM | Quantity2 | Quantity2 UOM | Quantity3 | Quantity3 UOM
- **Rows**: Classification labels with up to 3 quantity measures and their units of measure (SF/EA/LF/etc)

The service:
1. Normalizes rows deterministically (no LLM/AI)
2. Maps classifications to expected structure using exact and fuzzy matching
3. Provides async job processing with polling endpoints
4. Returns comprehensive QA reports with confidence scores

## Quick Start

### Installation

```bash
# Install dependencies
poetry install

# Or using pip
pip install openpyxl fuzzywuzzy python-Levenshtein
```

### Environment Setup

#### Option 1: SQLite for Local Development (Recommended)

```bash
# Set up SQLite database (no server needed!)
export DATABASE_URL="sqlite:///./data/dev.db"
export API_KEY="test-api-key-local-dev"
export DISABLE_BOOTSTRAP_USERS=true  # Skip user creation (we use API keys)

# Create data directory
mkdir -p data

# Start the server
uvicorn app.main:app --reload --port 8000
```

#### Option 2: PostgreSQL Setup

Create a `.env` file:

```env
# PostgreSQL Configuration
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=takeoff_service

# API Security
API_KEY=your-secure-api-key-here

# CORS (NextJS origins)
BACKEND_CORS_ORIGINS=["http://localhost:3000"]

# File Storage
FILE_STORAGE_PATH=./data
```

#### Option 3: Custom Database URL

```env
# Use any SQLAlchemy-compatible database URL
DATABASE_URL=postgresql://user:pass@host:5432/dbname
# Or for SQLite:
DATABASE_URL=sqlite:///./data/dev.db

API_KEY=your-secure-api-key-here
```

### Run the Service

```bash
# For SQLite local development (fastest setup):
export DATABASE_URL="sqlite:///./data/dev.db"
export API_KEY="test-api-key"
export DISABLE_BOOTSTRAP_USERS=true
mkdir -p data
uvicorn app.main:app --reload --port 8000

# API docs available at:
# http://localhost:8000/api/v1/docs
```

## API Endpoints

### 1. Create Job - `POST /api/v1/jobs`

Upload an Excel file for processing.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
  -H "X-API-Key: your-secure-api-key-here" \
  -F "file=@takeoff_data.xlsx" \
  -F "template=rc_wendt_v1"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "QUEUED"
}
```

### 2. Get Job Status - `GET /api/v1/jobs/{job_id}`

Poll for job status and results.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: your-secure-api-key-here"
```

**Response (Running):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "progress": 45,
  "result": null,
  "qa": null,
  "error": null
}
```

**Response (Completed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCEEDED",
  "progress": 100,
  "result": {
    "sections": [
      {
        "name": "General",
        "items": [
          {
            "key": "Units Count",
            "qty": 14,
            "uom": "EA",
            "source_classification": "Unit Count",
            "confidence": 0.95
          },
          {
            "key": "Total SF",
            "qty": 25000,
            "uom": "SF",
            "source_classification": "Total SF",
            "confidence": 1.0
          }
        ]
      },
      {
        "name": "Corridors",
        "items": [
          {
            "key": "Ceiling SF",
            "qty": 3500,
            "uom": "SF",
            "source_classification": "Cor. Lid",
            "confidence": 1.0
          }
        ]
      }
    ],
    "unmapped": [
      {
        "classification": "Unknown Item XYZ",
        "measures": [{"value": 100, "uom": "EA", "source": "Quantity"}],
        "provenance": {"sheet": "Takeoff Data", "row": 15}
      }
    ]
  },
  "qa": {
    "warnings": [
      {
        "type": "ambiguous_match",
        "classification": "Corridor Ceiling",
        "matched_to": "Ceiling SF",
        "confidence": 85.5,
        "message": "Fuzzy matched 'Corridor Ceiling' to 'Ceiling SF' with 85.5% confidence"
      },
      {
        "type": "multiple_measures",
        "classification": "Window",
        "measures": [
          {"value": 10, "uom": "EA", "source": "Quantity"},
          {"value": 15, "uom": "EA", "source": "Quantity2"}
        ],
        "selected": {"value": 15, "uom": "EA", "source": "Quantity2"},
        "message": "Multiple EA measures found for 'Window', selected largest value"
      }
    ],
    "confidence": 0.85,
    "stats": {
      "rows_total": 20,
      "rows_with_measures": 18,
      "items_mapped": 15,
      "items_missing": 5,
      "items_unmapped": 2,
      "ambiguous_matches": 3
    }
  },
  "error": null
}
```

### 3. Get Raw Data (Optional) - `GET /api/v1/jobs/{job_id}/raw`

Get normalized rows before mapping (useful for debugging).

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/raw" \
  -H "X-API-Key: your-secure-api-key-here"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCEEDED",
  "raw_data": [
    {
      "classification": "Unit Count",
      "measures": [
        {"value": 14, "uom": "EA", "source": "Quantity"}
      ],
      "provenance": {"sheet": "Takeoff Data", "row": 2}
    },
    {
      "classification": "Kitchen Cabinet",
      "measures": [
        {"value": 150, "uom": "LF", "source": "Quantity"},
        {"value": 200, "uom": "SF", "source": "Quantity2"},
        {"value": 50, "uom": "EA", "source": "Quantity3"}
      ],
      "provenance": {"sheet": "Takeoff Data", "row": 5}
    }
  ],
  "original_filename": "takeoff_data.xlsx",
  "template": "rc_wendt_v1"
}
```

## Normalization Rules

The service applies these rules deterministically:

1. **Classification**: Trimmed of leading/trailing whitespace
2. **UOM Normalization**:
   - `FT` → `LF` (Linear Feet)
   - `SQFT`, `SQ FT` → `SF` (Square Feet)
   - `EACH`, `PCS` → `EA` (Each)
   - Case-insensitive, uppercase output
3. **Numeric Conversion**:
   - Handles comma separators (1,000 → 1000)
   - Empty strings → null (dropped)
   - Non-numeric values → null (dropped)
4. **Headers**: Auto-detected from first rows
5. **Empty Rows**: Skipped

## Mapping Configuration

The mapping is defined in `/config/rc_wendt_v1.mapping.json`:

```json
{
  "sections": {
    "General": {
      "Units Count": {
        "uom": "EA",
        "match": ["Unit Count", "Units Count", "Total Units"],
        "description": "Total number of units"
      },
      "Total SF": {
        "uom": "SF",
        "match": ["Total SF", "Total Square Feet", "Gross SF"],
        "description": "Total square footage"
      }
    },
    "Corridors": {
      "Ceiling SF": {
        "uom": "SF",
        "match": ["Cor. Lid", "Corridor Lid", "Corridor Ceiling"],
        "description": "Corridor ceiling square footage"
      }
    }
  },
  "mapping_config": {
    "fuzzy_threshold": 0.8,
    "prefer_largest_measure": true,
    "uom_mappings": {
      "FT": "LF",
      "SQFT": "SF"
    }
  }
}
```

## Matching Behavior

1. **Exact Match** (case-insensitive) - Confidence: 1.0
2. **Fuzzy Match** (if no exact match):
   - Uses token sort ratio algorithm
   - Minimum threshold: 80%
   - Adds QA warning with confidence score
3. **Multiple Measures**:
   - Selects measure with required UOM
   - If multiple with same UOM, selects largest value
   - Adds QA warning about selection

## NextJS Integration

```typescript
// Example TypeScript client
class TakeoffClient {
  constructor(
    private apiUrl: string,
    private apiKey: string
  ) {}

  async createJob(file: File, template = 'rc_wendt_v1'): Promise<{job_id: string, status: string}> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('template', template);

    const response = await fetch(`${this.apiUrl}/api/v1/jobs`, {
      method: 'POST',
      headers: {
        'X-API-Key': this.apiKey,
      },
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Failed to create job: ${response.statusText}`);
    }

    return response.json();
  }

  async getJobStatus(jobId: string): Promise<JobStatus> {
    const response = await fetch(`${this.apiUrl}/api/v1/jobs/${jobId}`, {
      headers: {
        'X-API-Key': this.apiKey,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get job status: ${response.statusText}`);
    }

    return response.json();
  }

  async pollJobCompletion(jobId: string, intervalMs = 2000, maxAttempts = 30): Promise<JobStatus> {
    for (let i = 0; i < maxAttempts; i++) {
      const status = await this.getJobStatus(jobId);

      if (status.status === 'SUCCEEDED') {
        return status;
      }

      if (status.status === 'FAILED') {
        throw new Error(status.error?.message || 'Job failed');
      }

      // Show progress
      console.log(`Progress: ${status.progress}%`);

      await new Promise(resolve => setTimeout(resolve, intervalMs));
    }

    throw new Error('Job timeout');
  }
}

// Usage
const client = new TakeoffClient(
  process.env.NEXT_PUBLIC_API_URL,
  process.env.API_KEY
);

async function handleFileUpload(file: File) {
  try {
    // Create job
    const { job_id } = await client.createJob(file);
    console.log('Job created:', job_id);

    // Poll for completion
    const result = await client.pollJobCompletion(job_id);
    console.log('Extraction complete!');

    // Check confidence
    if (result.qa.confidence < 0.7) {
      console.warn('Low confidence extraction - manual review recommended');
    }

    // Process results
    for (const section of result.result.sections) {
      console.log(`Section: ${section.name}`);
      for (const item of section.items) {
        console.log(`  ${item.key}: ${item.qty} ${item.uom} (confidence: ${item.confidence})`);
      }
    }

    // Handle unmapped items
    if (result.result.unmapped.length > 0) {
      console.warn('Unmapped items:', result.result.unmapped);
    }

    return result;

  } catch (error) {
    console.error('Extraction failed:', error);
  }
}
```

## QA Report Interpretation

### Confidence Score (0-1)
- **0.9-1.0**: Excellent - Most items mapped with high confidence
- **0.7-0.89**: Good - Acceptable with some warnings
- **0.5-0.69**: Fair - Manual review recommended
- **< 0.5**: Poor - Significant issues, manual intervention needed

### Warning Types
- **`ambiguous_match`**: Fuzzy match used, includes confidence %
- **`multiple_measures`**: Multiple values with same UOM found
- **`missing_uom`**: Required UOM not found in measures
- **`unmapped`**: Classification couldn't be matched

### Statistics
- **`rows_total`**: Total data rows processed
- **`rows_with_measures`**: Rows that had valid quantities
- **`items_mapped`**: Successfully mapped to sections/items
- **`items_missing`**: Expected items not found in data
- **`items_unmapped`**: Data rows that couldn't be mapped
- **`ambiguous_matches`**: Count of fuzzy matches

## Testing

Run unit tests:

```bash
# Generate test Excel files
python tests/test_data/generate_test_files.py

# Run tests
pytest tests/test_takeoff_extraction.py -v

# Run with coverage
pytest tests/test_takeoff_extraction.py --cov=app.services --cov-report=html
```

Test files included:
- `standard_takeoff.xlsx` - Normal takeoff data
- `edge_case_takeoff.xlsx` - Edge cases and problematic data
- `minimal_takeoff.xlsx` - Minimal valid file

## File Storage

- **Uploads**: `./data/uploads/{job_id}/`
- **Database**: `./data/takeoff.db` (SQLite)
- **Config**: `/config/rc_wendt_v1.mapping.json`

## Performance

- **File Size**: Tested up to 10MB Excel files
- **Row Limit**: Optimized for up to 10,000 rows
- **Processing Time**: 1-5 seconds for typical takeoffs
- **Concurrent Jobs**: Supports multiple simultaneous extractions

## Extending the Service

### Adding New Mapping Templates

1. Create new config file: `/config/your_template.mapping.json`
2. Define sections, items, and match rules
3. Use template name in API: `template=your_template`

### Adding New UOM Mappings

Edit the mapping config:
```json
"uom_mappings": {
  "FT": "LF",
  "YOUR_UOM": "STANDARD_UOM"
}
```

### TODO: PDF Support

Future implementation marked with TODO comments:
- Use `pdfplumber` for PDF table extraction
- Add PDF-specific normalization rules
- Handle scanned PDFs with OCR (pytesseract)

## Troubleshooting

### Bcrypt Password Too Long Error
Bcrypt has a maximum password length of 72 bytes. If you see this error:
- Set `DISABLE_BOOTSTRAP_USERS=true` to skip user creation (recommended for API key auth)
- OR use a shorter password (< 72 characters) for `FIRST_SUPERUSER_PASSWORD`

### Job Stuck in QUEUED
- Check server logs for errors
- Verify file upload completed
- Check file permissions in `./data` directory

### Low Confidence Scores
- Review unmapped items in response
- Check if classifications match expected patterns
- Adjust fuzzy threshold in config if needed

### API Key Issues
- Verify `API_KEY` is set in `.env`
- Check header is exactly `X-API-Key`
- Restart server after changing `.env`

## Architecture Notes

- **Deterministic**: No AI/LLM, pure rule-based
- **SQLite for Dev**: Easy migration path to PostgreSQL
- **Background Processing**: FastAPI BackgroundTasks (upgradeable to Redis/RQ)
- **Fuzzy Matching**: FuzzyWuzzy with Levenshtein distance
- **Modular Design**: Separate normalization, mapping, and API layers

## License

Part of the RC Wendt extraction service suite.