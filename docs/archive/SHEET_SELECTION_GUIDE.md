# Sheet Selection Feature Guide

## ✅ Feature Implemented!

You can now select which sheets to process and how many. The API has been updated to support flexible sheet selection.

## How to Use

### 1. Start the Service First
```bash
cd /Users/jordanhill/code/py-py-code/rcw-extract
venv/bin/uvicorn app.main:app --port 8000 --reload
```

### 2. API Usage Options

#### Option A: Default (Single Sheet)
If you don't specify sheets, it will use the default sheet ("1 Bldg" or auto-detected):

**Swagger UI:**
- File: Select your Excel file
- Template: `baycrest_v1`
- Sheets: Leave empty

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/" \
  -H "X-API-Key: test-api-key" \
  -F "file=@baycrest_new.xlsx" \
  -F "template=baycrest_v1"
```

#### Option B: Specific Sheet
Process a specific sheet by name:

**Swagger UI:**
- File: Select your Excel file
- Template: `baycrest_v1`
- Sheets: `1 Bldg`

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/" \
  -H "X-API-Key: test-api-key" \
  -F "file=@baycrest_new.xlsx" \
  -F "template=baycrest_v1" \
  -F "sheets=1 Bldg"
```

#### Option C: Multiple Sheets
Process multiple sheets (comma-separated):

**Swagger UI:**
- File: Select your Excel file
- Template: `baycrest_v1`
- Sheets: `1 Bldg,2 Bldgs,3 Bldgs`

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/" \
  -H "X-API-Key: test-api-key" \
  -F "file=@baycrest_new.xlsx" \
  -F "template=baycrest_v1" \
  -F "sheets=1 Bldg,2 Bldgs,3 Bldgs"
```

#### Option D: All Sheets
Process ALL data sheets in the file:

**Swagger UI:**
- File: Select your Excel file
- Template: `baycrest_v1`
- Sheets: `all`

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/" \
  -H "X-API-Key: test-api-key" \
  -F "file=@baycrest_new.xlsx" \
  -F "template=baycrest_v1" \
  -F "sheets=all"
```

## What Happens with Multiple Sheets

When processing multiple sheets:

1. **Each sheet is processed independently**
   - Extraction runs on each sheet
   - Items are normalized from each sheet

2. **Results are combined**
   - All items from all sheets are merged
   - Statistics are summed
   - Sheet name is preserved in `provenance`

3. **Provenance tracking**
   - Each item remembers which sheet it came from
   - Example: `provenance: { sheet: "2 Bldgs", row: 15 }`

## Example Results

### Single Sheet (1 Bldg)
```json
{
  "qa": {
    "stats": {
      "items_mapped": 60,
      "rows_total": 127
    }
  }
}
```

### Multiple Sheets (1 Bldg, 2 Bldgs, 3 Bldgs)
```json
{
  "qa": {
    "stats": {
      "items_mapped": 180,   // 60 × 3
      "rows_total": 381      // 127 × 3
    }
  }
}
```

### All Sheets
```json
{
  "qa": {
    "stats": {
      "items_mapped": 420,   // All data sheets
      "rows_total": 889      // All rows from all sheets
    }
  }
}
```

## Sheets That Are Skipped

When using "all", these sheets are automatically skipped:
- `Sample`
- `Landscape Sample`
- `Bid Form`

These are considered non-data sheets.

## Use Cases

### 1. Single Building Project
```
sheets: "1 Bldg"
```

### 2. Multi-Building Project
```
sheets: "1 Bldg,2 Bldgs,3 Bldgs"
```

### 3. Complete Project Analysis
```
sheets: "all"
```

### 4. Custom Selection
```
sheets: "1 Bldg,Landscape,Units"
```

## Important Notes

1. **Sheet names must match exactly** (case-sensitive)
   - ✅ `"1 Bldg"`
   - ❌ `"1 bldg"` (wrong case)

2. **Comma-separated, no spaces after comma**
   - ✅ `"1 Bldg,2 Bldgs,3 Bldgs"`
   - ❌ `"1 Bldg, 2 Bldgs, 3 Bldgs"` (spaces)

3. **Unknown sheets are skipped**
   - If a sheet doesn't exist, it's skipped
   - Processing continues with valid sheets

4. **"all" is special keyword**
   - Must be lowercase
   - Processes all valid data sheets

## Swagger UI Instructions

1. Go to `http://127.0.0.1:8000/docs`
2. Find `POST /api/v1/jobs/`
3. Click "Try it out"
4. Fill in:
   - file: Choose your Excel file
   - template: `baycrest_v1`
   - sheets: (optional) Your sheet selection
   - x-api-key: `test-api-key`
5. Click "Execute"

## Verification

Check the results to see which sheets were processed:

```python
# In the result, check provenance
result["result"]["raw_data"][0]["provenance"]["sheet"]  # Shows sheet name
```

## Summary

✅ **Feature Complete**: Sheet selection is fully implemented
✅ **Flexible**: Choose one, multiple, or all sheets
✅ **Combined Results**: Multiple sheets are merged intelligently
✅ **Provenance**: Track which sheet each item came from
✅ **Production Ready**: Safe for bidding with any sheet combination