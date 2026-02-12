# RCW Python Full Bid

## Project Overview
Construction bid estimation SaaS: FastAPI + Jinja2/Alpine.js/HTMX. Extracts takeoff data from Excel, maps to catalog with pricing.

## Key Architecture
- **Extraction pipeline**: Excel → BaycrestNormalizer → TakeoffMapper → BidCatalog → BidFormState
- **4-tier matching**: Exact → Contains → Regex → Fuzzy (fuzzywuzzy/rapidfuzz)
- **Two item views**: `items` (catalog-driven, standardized) and `raw_items` (Excel-order, raw names)
- **State**: In-memory `_bid_forms` dict. Single-user MVP. `get_item()` searches both items and raw_items.
- **Toggle system REMOVED from UI** — ToggleMask still in model but no user-facing controls. Always ON (1.0). Don't reference toggles in docs/instructions.

## Key Files
- `config/bid_catalog.json` - Pricing catalog (rates per difficulty 1-5), aliases
- `config/baycrest_v1.mapping.json` - Match strings for fuzzy matching
- `app/ui/excel_mapper.py` - `map_excel_with_catalog()` builds both catalog + raw items
- `app/ui/viewmodels.py` - LineItem, BidFormState models
- `app/services/takeoff_mapper.py` - 4-tier matching engine
- `app/services/canonical_id.py` - Deterministic ID generation
- `app/templates/partials/bid_row.html` - Row template (Alpine.js collapse/expand)
- `app/templates/logic.html` - "Logic & Instructions" page (10 collapsible sections)

## Pages
- **Upload** (`/`) - Excel file upload. Just "Excel files (.xlsx, .xls)" — no mention of Baycrest template format
- **Bid Form** (`/bid`) - Main editing interface with sections, difficulty, exclusions
- **Logic & Instructions** (`/logic`) - 10-section help/reference page (no toggle section)
- **Print** (`/print`) - Print-optimized view

## Pricing Formula
`row_total = qty × (base_price + difficulty_add[level]) × multiplier`
No toggle multiplier — toggles removed from UI.

## Dev Environment
- Python venv at `./venv/` — run with `./venv/bin/python`
- Uses `requirements.txt` (pip)
- Start server: `./venv/bin/python -m uvicorn app.main:app --reload`

## Deployment (Render)
- Uses `requirements.txt` (pip), NOT Poetry
- `python-json-logger` v2 API: `from pythonjsonlogger import jsonlogger` (NOT v3 `.json` import)
- `SECRET_KEY` needs default in config.py or env var set in Render dashboard

## Rules
- Toggle system is removed from UI. Never add toggle references to templates, instructions, or docs.
- Upload page should not mention "Baycrest template format" — just say "Excel files"
- Always check current UI state before writing docs or instructions — features may have been removed
- Collapsed rows: `rowOpen: false` for qty==0 items, `notesOpen: false` always
