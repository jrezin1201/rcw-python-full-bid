# Sheet Selection Summary

## ✅ Implementation Complete!

The API now has flexible sheet selection with smart defaults:

## Default Behavior (What You Wanted)

**When you DON'T specify sheets:**
- ✅ **Processes:** ONLY "1 Bldg" sheet (first data tab)
- ❌ **Ignores:** All other sheets (2 Bldgs, 3 Bldgs, Multi Plex, etc.)

This is perfect for your standard Baycrest projects where you only need the first building tab.

## How to Use in Swagger UI

### Standard Usage (Most Common)
```
file: [Select your Excel file]
template: baycrest_v1
sheets: [LEAVE EMPTY]
```
**Result:** Only processes "1 Bldg" sheet

### For Different Projects

#### Process Different Sheet
```
sheets: "2 Bldgs"
```
**Result:** Only processes "2 Bldgs" sheet

#### Process Multiple Sheets
```
sheets: "1 Bldg,2 Bldgs,3 Bldgs"
```
**Result:** Processes all 3 specified sheets

#### Process Everything
```
sheets: "all"
```
**Result:** Processes all data sheets (skips Sample, Bid Form)

## Examples for Different Project Types

### Current Baycrest Project
```
sheets: [leave empty]  # Default to "1 Bldg"
```

### Multi-Building Project
```
sheets: "1 Bldg,2 Bldgs,3 Bldgs"
```

### Project with Different Sheet Names
```
sheets: "Building A"
sheets: "North Tower,South Tower"
sheets: "Phase 1,Phase 2"
```

### Complete Analysis
```
sheets: "all"
```

## What's in baycrest_new.xlsx

The file contains 9 sheets:
1. Sample (ignored by "all")
2. Landscape Sample (ignored by "all")
3. **1 Bldg** ← DEFAULT (processed by default)
4. 2 Bldgs (ignored by default)
5. 3 Bldgs (ignored by default)
6. Multi Plex (ignored by default)
7. Landscape (ignored by default)
8. Units (ignored by default)
9. Bid Form (ignored by "all")

## Key Points

✅ **Default = "1 Bldg" only** (exactly what you need)
✅ **Can override** for different projects
✅ **Flexible** for any sheet names
✅ **Production ready** for all scenarios

## API Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| file | Yes | - | Excel file to upload |
| template | No | rc_wendt_v1 | Use "baycrest_v1" |
| **sheets** | No | "1 Bldg" | Leave empty for default, or specify sheets |
| x-api-key | No | - | API key if configured |

## Testing

After starting the service:
```bash
venv/bin/uvicorn app.main:app --port 8000 --reload
```

Run the test:
```bash
venv/bin/python test_sheet_behavior.py
```

This will show you exactly how the sheet selection works.