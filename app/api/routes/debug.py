"""
Debug routes for template signature validation and other testing utilities.
"""
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Header
from app.core.logging import get_logger
from app.services.validators.baycrest_signature import validate_baycrest_workbook

logger = get_logger(__name__)

router = APIRouter()


def verify_api_key_optional(x_api_key: Optional[str] = Header(None)) -> str:
    """
    Optionally verify API key from header for debug endpoints.
    """
    expected_key = os.getenv('API_KEY')

    # Skip validation if no key configured (development mode)
    if not expected_key:
        logger.debug("API key validation skipped (not configured)")
        return "dev-mode"

    # Allow access without key for debug endpoints in dev mode
    if not x_api_key and os.getenv('DEBUG', 'False').lower() == 'true':
        return "debug-mode"

    if x_api_key and x_api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return x_api_key or "no-key"


@router.post("/signature/baycrest")
async def debug_baycrest_signature(
    file: UploadFile = File(...),
    api_key: str = Header(None)
):
    """
    Debug endpoint to validate Baycrest template signature.

    This endpoint allows you to upload an Excel file and immediately see
    the signature validation results without creating a job.

    Returns:
        - ok: Whether the file matches the Baycrest template
        - score: Match score (0.0 to 1.0, where 0.78+ is passing)
        - matched_sheet: Sheet that best matches the expected headers
        - warnings: List of validation warnings
        - debug: Additional debug information including sheets list
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed_extensions = {'.xlsx', '.xls'}
    file_ext = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {allowed_extensions}"
        )

    # Save to temporary file
    suffix = os.path.splitext(file.filename)[1] or '.xlsx'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Validate the workbook
        logger.info(f"Running signature validation on {file.filename}")
        sig = validate_baycrest_workbook(tmp_path)

        return {
            "filename": file.filename,
            "ok": sig.ok,
            "score": sig.score,
            "matched_sheet": sig.matched_sheet,
            "warnings": sig.warnings,
            "debug": sig.debug,
            "recommendation": "File matches Baycrest template" if sig.ok else "File does NOT match Baycrest template - check warnings for details"
        }

    except Exception as e:
        logger.error(f"Failed to validate signature: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate signature: {str(e)}"
        )

    finally:
        # Clean up temporary file
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@router.get("/signature/test")
async def test_signature_endpoint():
    """
    Test endpoint to verify debug routes are loaded.
    """
    return {
        "status": "ok",
        "message": "Debug signature validation endpoint is available at POST /api/v1/debug/signature/baycrest"
    }