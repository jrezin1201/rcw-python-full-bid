/**
 * Example NextJS integration with RC Wendt Takeoff Extraction API
 * This demonstrates how to upload files and poll for results from a NextJS app
 */

// Example API service (e.g., in lib/api/takeoff.ts)
const API_BASE_URL = 'http://localhost:8000/api/v1';
const API_KEY = 'your-api-key-here'; // In production, use environment variables

/**
 * Upload an Excel file for extraction
 */
export async function uploadTakeoffFile(file: File): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('template', 'rc_wendt_v1');

  const response = await fetch(`${API_BASE_URL}/jobs/`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
    },
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Poll for job status and results
 */
export async function getJobStatus(jobId: string) {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
    method: 'GET',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get job status: ${response.statusText}`);
  }

  return response.json();
}

// Example React component using the API
import { useState } from 'react';

export function TakeoffUploader() {
  const [uploading, setUploading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      // Upload file
      const { job_id } = await uploadTakeoffFile(file);
      setJobId(job_id);

      // Poll for results
      const pollInterval = setInterval(async () => {
        try {
          const job = await getJobStatus(job_id);

          if (job.status === 'SUCCEEDED') {
            clearInterval(pollInterval);
            setResult(job.result);
            setUploading(false);
          } else if (job.status === 'FAILED') {
            clearInterval(pollInterval);
            setError(job.error?.message || 'Extraction failed');
            setUploading(false);
          }
        } catch (err) {
          clearInterval(pollInterval);
          setError(err instanceof Error ? err.message : 'Unknown error');
          setUploading(false);
        }
      }, 2000); // Poll every 2 seconds
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setUploading(false);
    }
  };

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold mb-4">RC Wendt Takeoff Extraction</h2>

      <input
        type="file"
        accept=".xlsx,.xls"
        onChange={handleFileUpload}
        disabled={uploading}
        className="mb-4"
      />

      {uploading && (
        <div className="text-blue-600">Processing takeoff file...</div>
      )}

      {error && (
        <div className="text-red-600 mb-4">Error: {error}</div>
      )}

      {result && (
        <div className="mt-4">
          <h3 className="font-bold mb-2">Extraction Results:</h3>

          {/* Display sections */}
          {result.sections.map((section: any) => (
            <div key={`section-${section.name}`} className="mb-4">
              <h4 className="font-semibold">{section.name}</h4>
              <ul className="ml-4">
                {section.items.map((item: any) => (
                  <li key={`item-${section.name}-${item.key}`}>
                    {item.key}: {item.qty} {item.uom}
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {/* Display unmapped items if any */}
          {result.unmapped?.length > 0 && (
            <div className="mt-4">
              <h4 className="font-semibold">Unmapped Items:</h4>
              <ul className="ml-4">
                {result.unmapped.map((item: any) => (
                  <li key={`unmapped-${item.classification}-row-${item.provenance.row}`}>
                    {item.classification}:
                    {item.measures.map((m: any) => ` ${m.value} ${m.uom}`).join(', ')}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Example environment variables (.env.local)
/*
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_API_KEY=your-api-key-here
*/