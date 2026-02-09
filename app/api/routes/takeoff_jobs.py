"""
API routes for takeoff extraction jobs.
"""
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, Header
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.core.logging import get_logger
from app.models.takeoff_job import TakeoffJob, JobStatus, get_session, init_db
from app.services.file_storage_service import file_storage_service
from app.services.takeoff_normalizer import TakeoffNormalizer
from app.services.baycrest_normalizer import BaycrestNormalizer
from app.services.takeoff_mapper import TakeoffMapper
from app.services.validators.baycrest_signature import validate_baycrest_workbook

logger = get_logger(__name__)

router = APIRouter()

# Initialize database on module load
init_db()


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """
    Verify API key from header.
    """
    expected_key = os.getenv('API_KEY')

    # Skip validation if no key configured (development mode)
    if not expected_key:
        logger.debug("API key validation skipped (not configured)")
        return "dev-mode"

    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header"
        )

    if x_api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return x_api_key


def process_takeoff_job(job_id: str):
    """
    Background task to process a takeoff extraction job.
    This runs in a background thread via FastAPI BackgroundTasks.
    """
    logger.info(f"Processing takeoff job {job_id}")

    with get_session() as session:
        try:
            # Get the job
            job = session.get(TakeoffJob, job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            # Update status to running
            job.status = JobStatus.RUNNING
            job.progress = 10
            session.commit()

            # Initialize variables that will be used later
            raw_rows = []
            raw_data = []
            extraction_stats = {}

            # Validate template signature for Baycrest format
            selected_takeoff_sheet = None
            if job.template == 'baycrest_v1':
                logger.info(f"Validating Baycrest template signature for file: {job.file_path}")
                sig = validate_baycrest_workbook(job.file_path)

                # Always attach warnings/debug to QA so the UI can display it
                if not job.qa:
                    job.qa = {}

                # Add validation warnings (for debugging)
                job.qa['validation'] = {
                    'warnings': sig.warnings
                }

                # Add sheet selection info (for debugging)
                if sig.sheet_selection:
                    job.qa['sheet_selection'] = {
                        'selected_sheet': sig.sheet_selection.selected_sheet,
                        'method': sig.sheet_selection.method,
                        'candidates_tried': sig.sheet_selection.candidates_tried,
                        'score': sig.sheet_selection.score
                    }
                    selected_takeoff_sheet = sig.sheet_selection.selected_sheet

                # Legacy signature info
                job.qa['signature'] = {
                    'ok': sig.ok,
                    'score': sig.score,
                    'matched_sheet': sig.matched_sheet,
                    'warnings': sig.warnings,
                    'debug': sig.debug
                }

                # Hard fail if mismatch
                if not sig.ok:
                    job.status = JobStatus.FAILED
                    job.error_message = "Uploaded Excel does not look like Baycrest template."
                    job.error_detail = f"TEMPLATE_MISMATCH: {'; '.join(sig.warnings)}"
                    session.commit()
                    logger.error(f"Job {job_id} failed signature validation: {sig.warnings}")
                    return

                logger.info(f"Signature validation passed with score {sig.score:.2f} on sheet '{sig.matched_sheet}'")

            # Choose normalizer based on template
            if job.template == 'baycrest_v1':
                # Use Baycrest normalizer for new format
                normalizer = BaycrestNormalizer()

                # Determine which sheets to process
                sheets_to_process = []

                if job.sheets:
                    # Use sheets specified in job
                    if job.sheets == ["all"]:
                        # Process all sheets (let normalizer discover them)
                        sheets_to_process = ["all"]
                        logger.info("Processing ALL sheets in the file")
                    else:
                        sheets_to_process = job.sheets
                        logger.info(f"Processing specified sheets: {sheets_to_process}")
                else:
                    # Default behavior: Use the sheet selected by signature validation
                    # This handles "1 Bldg", "1 Bldg (4)", or content-detected sheets
                    if selected_takeoff_sheet:
                        sheets_to_process = [selected_takeoff_sheet]
                        logger.info(f"Using validated sheet: {selected_takeoff_sheet}")
                    else:
                        # Fallback to "1 Bldg" if validation didn't select a sheet
                        sheets_to_process = ["1 Bldg"]
                        logger.info("Using default sheet: 1 Bldg (first tab)")

                # Process sheets
                if sheets_to_process == ["all"] or (sheets_to_process and len(sheets_to_process) > 1):
                    # Multiple sheets - need to combine results
                    all_raw_rows = []
                    all_raw_data = []
                    combined_stats = {
                        'rows_total': 0,
                        'rows_extracted': 0,
                        'rows_ignored': 0,
                        'rows_with_measures': 0
                    }

                    for sheet_name in sheets_to_process:
                        if sheet_name == "all":
                            # Special case - process all sheets
                            import openpyxl
                            workbook = openpyxl.load_workbook(job.file_path, data_only=True)
                            for actual_sheet in workbook.sheetnames:
                                # Skip non-data sheets
                                if actual_sheet in ['Sample', 'Landscape Sample', 'Bid Form']:
                                    continue
                                logger.info(f"Processing sheet: {actual_sheet}")
                                result = normalizer.normalize_file(job.file_path, target_sheet_name=actual_sheet)

                                # Add sheet name to each row's provenance
                                for row in result.get('raw_data', []):
                                    if 'provenance' not in row:
                                        row['provenance'] = {}
                                    row['provenance']['sheet'] = actual_sheet

                                all_raw_rows.extend(result.get('raw_rows', []))
                                all_raw_data.extend(result.get('raw_data', []))

                                # Combine stats
                                stats = result.get('stats', {})
                                for key in combined_stats:
                                    combined_stats[key] += stats.get(key, 0)
                        else:
                            logger.info(f"Processing sheet: {sheet_name}")
                            result = normalizer.normalize_file(job.file_path, target_sheet_name=sheet_name)

                            # Add sheet name to each row's provenance
                            for row in result.get('raw_data', []):
                                if 'provenance' not in row:
                                    row['provenance'] = {}
                                row['provenance']['sheet'] = sheet_name

                            all_raw_rows.extend(result.get('raw_rows', []))
                            all_raw_data.extend(result.get('raw_data', []))

                            # Combine stats
                            stats = result.get('stats', {})
                            for key in combined_stats:
                                combined_stats[key] += stats.get(key, 0)

                    raw_rows = all_raw_rows
                    raw_data = all_raw_data
                    extraction_stats = combined_stats
                    logger.info(f"Combined results from {len(sheets_to_process)} sheets: {len(raw_data)} items")
                else:
                    # Single sheet or default
                    sheet_name = sheets_to_process[0] if sheets_to_process else None
                    logger.info(f"Using Baycrest normalizer for file: {job.file_path}, sheet: {sheet_name}")
                    extraction_result = normalizer.normalize_file(job.file_path, target_sheet_name=sheet_name)

                    # Extract components
                    raw_rows = extraction_result.get('raw_rows', [])
                    raw_data = extraction_result.get('raw_data', [])
                    extraction_stats = extraction_result.get('stats', {})

                # Sanity check: raw_rows length should match rows_total
                rows_total = extraction_stats.get('rows_total', 0)
                rows_extracted = extraction_stats.get('rows_extracted', 0)
                rows_ignored = extraction_stats.get('rows_ignored', 0)
                logger.info(f"Extractor stats: rows_total={rows_total} rows_extracted={rows_extracted} rows_ignored={rows_ignored}")
                logger.info(f"raw_rows_len={len(raw_rows)} raw_data_len={len(raw_data)}")

                if len(raw_rows) != rows_total:
                    logger.warning(
                        f"raw_rows_len ({len(raw_rows)}) != rows_total ({rows_total}). "
                        "Fix raw_rows capture to include every parsed row."
                    )

                # Store raw data for audit (raw_rows will be in result, not job)
                job.raw_data = raw_data

                # Use raw_data for mapping
                normalized_rows = raw_data
            else:
                # Use original Togal normalizer
                logger.info(f"Using Togal normalizer for file: {job.file_path}")
                normalizer = TakeoffNormalizer(job.file_path)
                normalized_rows, normalization_metadata = normalizer.parse_excel_to_normalized_rows()
                extraction_stats = {'rows_ignored': normalization_metadata.get('rows_ignored', 0)}
                raw_rows = []  # Togal format doesn't capture raw_rows
                raw_data = normalized_rows  # For Togal, normalized_rows is the raw_data

            # Update progress
            job.progress = 40
            job.raw_data = raw_data
            session.commit()

            # Map to sections
            logger.info(f"Mapping {len(normalized_rows)} rows using template {job.template}")
            mapper = TakeoffMapper(template=job.template)
            mapping_result = mapper.map_rows_to_sections(normalized_rows)

            # Ensure QA stats always exists (NextJS expects it)
            if 'qa' not in mapping_result:
                mapping_result['qa'] = {}
            if 'stats' not in mapping_result['qa']:
                mapping_result['qa']['stats'] = {}

            # Add extraction stats to QA
            mapping_result['qa']['stats'].update(extraction_stats)

            # Update progress
            job.progress = 80
            session.commit()

            # Store results
            result_dict = {
                'sections': mapping_result['sections'],
                'unmapped': mapping_result['unmapped'],
                'unmapped_summary': mapping_result.get('unmapped_summary', {}),
                'bid_items': mapping_result.get('bid_items', [])  # Flat list for UI
            }

            # Add raw_rows and raw_data for Baycrest format
            if job.template == 'baycrest_v1':
                logger.info(f"Adding raw_rows ({len(raw_rows)} rows) and raw_data ({len(raw_data)} items) to result")
                result_dict['raw_rows'] = raw_rows
                result_dict['raw_data'] = raw_data
                logger.info(f"Result keys after adding: {list(result_dict.keys())}")
                logger.info(f"bid_items count: {len(result_dict.get('bid_items', []))}")

            # Set the complete result (triggers the setter to update result_json)
            job.result = result_dict

            job.qa = mapping_result['qa']

            # Mark as succeeded
            job.status = JobStatus.SUCCEEDED
            job.progress = 100
            session.commit()

            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.error_detail = str(type(e).__name__)
            session.commit()


@router.post("/")
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    template: Optional[str] = Form("baycrest_v1"),
    sheets: Optional[str] = Form(None),  # Comma-separated list of sheet names or "all"
    api_key: str = Depends(verify_api_key),
):
    """
    Create a new takeoff extraction job.

    Args:
        file: Excel file to process
        template: Mapping template to use (default: baycrest_v1)
        sheets: Comma-separated list of sheet names to process, or "all" for all sheets
                Example: "1 Bldg,2 Bldgs,3 Bldgs" or "all"
                If not provided, uses default sheet selection

    Returns:
        Job ID and status
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

    # Validate template exists
    try:
        TakeoffMapper(template=template)
    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template: {template}"
        )

    with get_session() as session:
        # Create job record
        job = TakeoffJob(
            template=template,
            original_filename=file.filename,
            status=JobStatus.QUEUED
        )

        # Parse and store sheet selection if provided
        if sheets:
            if sheets.lower() == "all":
                job.sheets = ["all"]  # Special marker for all sheets
            else:
                # Parse comma-separated sheet names
                sheet_list = [s.strip() for s in sheets.split(",") if s.strip()]
                if sheet_list:
                    job.sheets = sheet_list
                    logger.info(f"Job will process sheets: {sheet_list}")

        session.add(job)
        session.commit()

        # Save uploaded file
        try:
            file_path = file_storage_service.save_uploaded_file(file, job.id)
            job.file_path = file_path
            session.commit()
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise HTTPException(status_code=500, detail="Failed to save uploaded file")

        # Start background processing
        background_tasks.add_task(process_takeoff_job, job.id)

        logger.info(f"Created job {job.id} for file {file.filename}")

        return {
            "job_id": job.id,
            "status": job.status
        }


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    api_key: str = Depends(verify_api_key),
):
    """
    Get job status and results.

    Returns:
        Job status, progress, results, and QA report
    """
    with get_session() as session:
        job = session.get(TakeoffJob, job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        response = {
            "job_id": job.id,
            "status": job.status,
            "progress": job.progress,
            "result": None,
            "qa": None,
            "error": None
        }

        # Add results if succeeded
        if job.status == JobStatus.SUCCEEDED:
            response["result"] = job.result
            response["qa"] = job.qa

        # Add error if failed
        elif job.status == JobStatus.FAILED:
            response["error"] = {
                "message": job.error_message or "Unknown error",
                "detail": job.error_detail
            }

        return response


@router.get("/{job_id}/raw")
async def get_job_raw_data(
    job_id: str,
    api_key: str = Depends(verify_api_key),
):
    """
    Get raw normalized data for debugging.

    Returns:
        Normalized rows before mapping
    """
    with get_session() as session:
        job = session.get(TakeoffJob, job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        if job.status not in [JobStatus.SUCCEEDED, JobStatus.RUNNING]:
            return {
                "job_id": job.id,
                "status": job.status,
                "raw_data": None,
                "message": "Raw data not yet available"
            }

        return {
            "job_id": job.id,
            "status": job.status,
            "raw_data": job.raw_data,
            "original_filename": job.original_filename,
            "template": job.template
        }