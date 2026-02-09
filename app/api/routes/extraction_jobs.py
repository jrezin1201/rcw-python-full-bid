"""
API routes for extraction jobs.
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from sqlmodel import Session

from app.api.deps import get_current_active_user, get_api_key
from app.core.logging import get_logger
from app.db.session import get_session
from app.models.job import JobStatus, JobType
from app.models.user import User
from app.schemas.job import (
    JobCreateResponse,
    JobFinalizeRequest,
    JobFinalizeResponse,
    JobListResponse,
    JobStatusResponse,
)
from app.services.file_storage_service import file_storage_service
from app.services.job_service import JobService
from app.workers.queue import enqueue_task
from app.workers.tasks import extract_document_task

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=JobCreateResponse)
async def create_extraction_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_type: str = Form(...),
    session: Session = Depends(get_session),
    api_key: str = Depends(get_api_key),
):
    """
    Create a new extraction job.

    Accepts a multipart form with:
    - file: The document to extract (Excel/PDF)
    - job_type: Type of extraction (e.g., "rc_wendt_bid_v1")
    """
    try:
        # Validate job type
        try:
            job_type_enum = JobType(job_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid job type: {job_type}. Valid types: {[e.value for e in JobType]}"
            )

        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        allowed_extensions = {'.xlsx', '.xls'}  # PDF support coming later
        file_ext = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {allowed_extensions}"
            )

        # Create job in database
        job_service = JobService(session)
        job = job_service.create_job(
            job_type=job_type_enum,
            file=file,
            user_id=None  # API key auth doesn't have user context
        )

        # Enqueue extraction task
        task_result = enqueue_task(extract_document_task, job.id)

        if not task_result:
            # Fallback to background tasks if queue is not available
            logger.warning("Queue not available, using FastAPI background tasks")
            background_tasks.add_task(extract_document_task, job.id)

        logger.info(f"Created extraction job {job.id}")

        return JobCreateResponse(
            job_id=job.id,
            status=job.status
        )

    except Exception as e:
        logger.error(f"Failed to create extraction job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    session: Session = Depends(get_session),
    api_key: str = Depends(get_api_key),
):
    """
    Get the status and results of an extraction job.
    """
    job_service = JobService(session)
    job_status = job_service.get_job_status_response(job_id)

    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return job_status


@router.get("/{job_id}/download")
async def download_job_results(
    job_id: str,
    session: Session = Depends(get_session),
    api_key: str = Depends(get_api_key),
):
    """
    Download the extraction results as a JSON file.
    """
    job_service = JobService(session)
    job = job_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status != JobStatus.SUCCEEDED and job.status != JobStatus.FINALIZED:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not complete. Current status: {job.status}"
        )

    # Get the results file path
    results_path = job_service.get_job_results_file(job_id)
    if not results_path:
        raise HTTPException(status_code=404, detail="Results file not found")

    # Return as file download
    return FileResponse(
        path=results_path,
        media_type='application/json',
        filename=f"extraction_results_{job_id}.json"
    )


@router.post("/{job_id}/finalize", response_model=JobFinalizeResponse)
async def finalize_job(
    job_id: str,
    request: JobFinalizeRequest,
    session: Session = Depends(get_session),
    api_key: str = Depends(get_api_key),
):
    """
    Finalize a job, making its results immutable.
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Must confirm finalization by setting 'confirm' to true"
        )

    job_service = JobService(session)
    job = job_service.finalize_job(job_id)

    if not job:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot finalize job {job_id}. It may not exist or is not in SUCCEEDED state."
        )

    return JobFinalizeResponse(
        job_id=job.id,
        status=job.status,
        finalized_at=job.finalized_at
    )


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    status: Optional[JobStatus] = None,
    page: int = 1,
    per_page: int = 20,
    session: Session = Depends(get_session),
    api_key: str = Depends(get_api_key),
):
    """
    List extraction jobs with optional filtering.
    """
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    offset = (page - 1) * per_page

    job_service = JobService(session)
    jobs = job_service.get_jobs(
        user_id=None,  # API key auth doesn't have user context
        status=status,
        limit=per_page,
        offset=offset
    )

    # Convert to response models
    job_responses = []
    for job in jobs:
        job_response = job_service.get_job_status_response(job.id)
        if job_response:
            job_responses.append(job_response)

    return JobListResponse(
        jobs=job_responses,
        total=len(job_responses),
        page=page,
        per_page=per_page
    )


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    session: Session = Depends(get_session),
    api_key: str = Depends(get_api_key),
):
    """
    Delete a job and all associated data.
    Note: This is a destructive operation and cannot be undone.
    """
    job_service = JobService(session)

    # Check if job exists
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Prevent deletion of finalized jobs
    if job.status == JobStatus.FINALIZED:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete finalized jobs"
        )

    success = job_service.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete job")

    return {"message": f"Job {job_id} deleted successfully"}