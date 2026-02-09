# NextJS Development Integration Guide

This guide helps you integrate your NextJS application with the RC Wendt Takeoff Extraction API.

## Server Setup

1. Start the FastAPI server:
```bash
export DATABASE_URL="sqlite:///./data/dev.db"
export API_KEY="your-dev-api-key"
export DISABLE_BOOTSTRAP_USERS=true
uvicorn app.main:app --port 8000 --host 127.0.0.1
```

2. Verify the server is running:
```bash
curl http://127.0.0.1:8000/api/v1/health
```

## CORS Configuration

The API is pre-configured for NextJS development with the following CORS settings:
- **Allowed Origin:** `http://localhost:3000`
- **Allowed Methods:** GET, POST, OPTIONS
- **Allowed Headers:** x-api-key, content-type, accept
- **Credentials:** Allowed

## API Connectivity Examples

### 1. Upload Excel File (POST)

**Using curl:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/" \
  -H "X-API-Key: your-dev-api-key" \
  -F "file=@test.xlsx" \
  -F "template=rc_wendt_v1"
```

**Using NextJS fetch with FormData:**
```javascript
// Upload function in your NextJS app
async function uploadTakeoffFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('template', 'rc_wendt_v1');

  const response = await fetch('http://127.0.0.1:8000/api/v1/jobs/', {
    method: 'POST',
    headers: {
      'X-API-Key': 'your-dev-api-key',
    },
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }

  return response.json();
}
```

### 2. Check Job Status (GET)

**Using curl:**
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/jobs/{job_id}" \
  -H "X-API-Key: your-dev-api-key"
```

**Using NextJS fetch:**
```javascript
// Poll for job status
async function getJobStatus(jobId) {
  const response = await fetch(`http://127.0.0.1:8000/api/v1/jobs/${jobId}`, {
    method: 'GET',
    headers: {
      'X-API-Key': 'your-dev-api-key',
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get job status: ${response.statusText}`);
  }

  return response.json();
}
```

## Complete NextJS Integration Example

```javascript
import { useState } from 'react';

export function TakeoffUploader() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      // Upload file
      const formData = new FormData();
      formData.append('file', file);
      formData.append('template', 'rc_wendt_v1');

      const uploadResponse = await fetch('http://127.0.0.1:8000/api/v1/jobs/', {
        method: 'POST',
        headers: {
          'X-API-Key': 'your-dev-api-key',
        },
        body: formData,
      });

      if (!uploadResponse.ok) {
        throw new Error('Upload failed');
      }

      const { job_id } = await uploadResponse.json();

      // Poll for results
      const pollInterval = setInterval(async () => {
        const statusResponse = await fetch(
          `http://127.0.0.1:8000/api/v1/jobs/${job_id}`,
          {
            method: 'GET',
            headers: {
              'X-API-Key': 'your-dev-api-key',
              'Content-Type': 'application/json',
            },
          }
        );

        const job = await statusResponse.json();

        if (job.status === 'SUCCEEDED') {
          clearInterval(pollInterval);
          setResult(job.result);
          setLoading(false);
        } else if (job.status === 'FAILED') {
          clearInterval(pollInterval);
          setError(job.error?.message || 'Extraction failed');
          setLoading(false);
        }
      }, 2000); // Poll every 2 seconds

    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div>
      <input
        type="file"
        accept=".xlsx,.xls"
        onChange={handleFileUpload}
        disabled={loading}
      />

      {loading && <div>Processing...</div>}
      {error && <div>Error: {error}</div>}

      {result && (
        <div>
          {/* Display sections with stable React keys */}
          {result.sections.map(section => (
            <div key={`section-${section.name}`}>
              <h3>{section.name}</h3>
              {section.items.map(item => (
                <div key={`item-${section.name}-${item.key}`}>
                  {item.key}: {item.qty} {item.uom}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

## Environment Variables

For production, use environment variables instead of hardcoding values:

**.env.local (NextJS):**
```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_API_KEY=your-dev-api-key
```

**Usage in NextJS:**
```javascript
const API_URL = process.env.NEXT_PUBLIC_API_URL;
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;
```

## Troubleshooting

### CORS Errors
If you see CORS errors in the browser console:
1. Ensure the FastAPI server is running on `http://127.0.0.1:8000`
2. Confirm your NextJS app is on `http://localhost:3000`
3. Check that the API_KEY header is included in all requests

### FormData Issues
- The API expects `multipart/form-data` for file uploads
- Do NOT set `Content-Type` header manually when sending FormData - the browser sets it automatically with the correct boundary

### Connection Refused
- Verify the FastAPI server is running: `curl http://127.0.0.1:8000/api/v1/health`
- Check that no firewall is blocking port 8000

## API Response Format

The API returns deterministic, stable responses suitable for React:

```typescript
interface JobResponse {
  job_id: string;
  status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  progress: number;
  result: {
    sections: Array<{
      name: string;           // Stable section name from config
      items: Array<{
        key: string;          // Stable item key from config
        qty: number;          // Formatted quantity (int for EA, decimal for SF/FT)
        qty_raw: number;      // Raw value for audit
        uom: string;          // Canonicalized UOM ("FT" instead of "LF")
        uom_raw: string;      // Original normalized UOM
        source_classification: string;
        confidence: number;
      }>;
    }>;
    unmapped: Array<{
      classification: string;
      measures: Array<{
        value: number;        // Formatted value
        value_raw: number;    // Raw value for audit
        uom: string;          // Canonicalized UOM
        uom_raw: string;      // Original normalized UOM
        source: string;
      }>;
      provenance: {
        sheet: string;
        row: number;
      };
    }>;
  } | null;
  qa: {
    warnings: Array<...>;
    confidence: number;
    stats: {...};
  } | null;
  error: {
    message: string;
    details?: string;
  } | null;
}
```

## Quick Test

Test the API directly from your browser console:

```javascript
// Test from browser console (with CORS)
fetch('http://127.0.0.1:8000/api/v1/health')
  .then(r => r.json())
  .then(console.log);

// Test file upload
const input = document.createElement('input');
input.type = 'file';
input.onchange = async (e) => {
  const file = e.target.files[0];
  const formData = new FormData();
  formData.append('file', file);
  formData.append('template', 'rc_wendt_v1');

  const response = await fetch('http://127.0.0.1:8000/api/v1/jobs/', {
    method: 'POST',
    headers: { 'X-API-Key': 'your-dev-api-key' },
    body: formData
  });

  console.log(await response.json());
};
input.click();
```