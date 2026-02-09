# Takeoff Extraction API Contract

## Overview
This document defines the stable JSON contract for the Takeoff Extraction Service API. All keys and structures are deterministic and stable across runs to support React hydration and reliable frontend integration.

## Key Stability Guarantees

1. **Section Names**: Always from the mapping config, in config-defined order (NOT alphabetical)
2. **Item Keys**: Always from the mapping config, never change for same template
3. **All Response Keys**: Fixed and always present (null if no value)
4. **Quantity Formatting**: EA quantities as integers (14), SF/LF with decimals as needed (25.5 or 100)
5. **No Random IDs**: All identifiers are deterministic based on input data

## Endpoints

### POST /api/v1/jobs/
Upload Excel file for extraction.

**Request:**
```
Content-Type: multipart/form-data
X-API-Key: {api_key}

file: {excel_file}
template: "rc_wendt_v1"
```

**Response:**
```json
{
    "job_id": "uuid-v4",
    "status": "QUEUED"
}
```

### GET /api/v1/jobs/{job_id}
Poll for job status and results.

**Response Structure:**
```typescript
interface JobResponse {
    job_id: string;           // UUID, stable for job lifetime
    status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
    progress: number;          // 0-100
    result: ExtractionResult | null;
    qa: QAReport | null;
    error: ErrorInfo | null;
}

interface ExtractionResult {
    sections: Section[];       // Always array, can be empty
    unmapped: UnmappedItem[]; // Always array, can be empty
}

interface Section {
    name: string;             // From config, e.g. "General", "Corridors"
    items: MappedItem[];      // Always array, can be empty
}

interface MappedItem {
    key: string;              // From config, e.g. "Units Count", "Ceiling SF"
    qty: number;              // Formatted: Integer for EA (14), decimal for SF/FT (25.5)
    qty_raw: number;          // Raw value for audit precision (14.0, 25.5)
    uom: string;              // Canonicalized for UI: "EA", "SF", "FT" (LF becomes FT)
    uom_raw: string;          // Original normalized: "EA", "SF", "LF"
    source_classification: string;  // Original Excel classification
    confidence: number;       // 0.0-1.0, always float
}

interface UnmappedItem {
    classification: string;   // Original Excel classification
    measures: Measure[];      // All measures found
    provenance: {
        sheet: string;        // Excel sheet name
        row: number;          // Excel row number (1-based)
    };
}

interface Measure {
    value: number;           // Formatted: Integer for EA, decimal for SF/FT
    value_raw: number;       // Raw value for audit precision
    uom: string;            // Canonicalized for UI: "EA", "SF", "FT" (LF becomes FT)
    uom_raw: string;        // Original normalized: "EA", "SF", "LF"
    source: string;         // "Quantity", "Quantity2", or "Quantity3"
}

interface QAReport {
    warnings: Warning[];     // Always array, can be empty
    confidence: number;      // 0.0-1.0 overall confidence
    stats: {
        rows_total: number;
        rows_with_measures: number;
        items_mapped: number;
        items_missing: number;
        items_unmapped: number;
        ambiguous_matches: number;
        rows_ignored: number;
    };
}

interface Warning {
    type: "ambiguous_match" | "conflicting_measures" | "missing_uom" | "unmapped";
    severity?: "low" | "medium" | "high";
    classification: string;
    message: string;
    // Additional fields depend on type:
    confidence?: number;           // For ambiguous_match
    measures?: Measure[];          // For conflicting_measures
    selected?: Measure;            // For conflicting_measures
    percent_difference?: number;   // For conflicting_measures
    required_uom?: string;         // For missing_uom
    available_uoms?: string[];     // For missing_uom
}

interface ErrorInfo {
    message: string;
    details?: string;
}
```

## Deterministic Behavior

### Section Order
Sections appear in the order defined by `section_order` array in the config file. This allows control over proposal/UI display order. The default order is:
1. General
2. Corridors
3. Units
4. Stairs
5. Windows
6. Finishes

### Item Keys Within Sections
Items within a section maintain their config-defined keys. The same Excel classification always maps to the same item key.

### React Key Generation
For React components, use these stable keys:
- Sections: `section-${section.name}`
- Items: `item-${section.name}-${item.key}`
- Unmapped: `unmapped-${item.classification}-row-${item.provenance.row}`
- Warnings: `warning-${warning.type}-${warning.classification}`

### Example React Usage
```jsx
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
```

## Confidence Score Interpretation

- **0.9-1.0**: Excellent - Most items mapped exactly
- **0.7-0.89**: Good - Acceptable with some fuzzy matches
- **0.5-0.69**: Fair - Manual review recommended
- **< 0.5**: Poor - Significant issues requiring intervention

## UOM Processing

### Step 1: Normalization (Excel → Internal)
Standard normalizations from Excel input:
- `FT`, `FEET`, `LINEAR FEET` → `LF`
- `SQFT`, `SQ FT`, `SQUARE FEET` → `SF`
- `EACH`, `PCS`, `PIECES` → `EA`

### Step 2: Canonicalization (Internal → UI)
UI canonicalization for display consistency:
- `LF` → `FT` (Linear feet displayed as FT in UI)
- `SF` → `SF` (Square feet unchanged)
- `EA` → `EA` (Each unchanged)

### Audit Trail
Both values are preserved:
- `uom`: Canonicalized value for UI display (e.g., "FT")
- `uom_raw`: Original normalized value (e.g., "LF")

## Error Handling

Failed jobs always have:
- `status: "FAILED"`
- `result: null`
- `qa: null`
- `error: { message: "...", details: "..." }`

## Versioning

The API version is in the URL path (`/api/v1/`). Breaking changes will increment the version.

## Template Configuration

The `rc_wendt_v1` template defines:
- Section names and order
- Item keys within each section
- Fuzzy matching thresholds
- UOM requirements

To add mappings for Door Frame and Flooring, update `/config/rc_wendt_v1.mapping.json`.