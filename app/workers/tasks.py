"""
Background tasks using RQ (Redis Queue).
Define long-running or asynchronous tasks here.
"""

import time
from typing import Any

from sqlmodel import Session, create_engine

from app.core.config import settings
from app.core.logging import get_logger
from app.models.job import JobStatus
from app.services.extraction_service import ExcelExtractor, PDFExtractor
from app.services.job_service import JobService

logger = get_logger(__name__)

# Create engine for background tasks
# Note: Each worker needs its own database connection
engine = create_engine(settings.DATABASE_URI, echo=False)


def example_task(name: str, duration: int = 5) -> dict[str, Any]:
    """
    Example background task that simulates a long-running operation.

    Args:
        name: Name identifier for the task
        duration: How long the task should run (seconds)

    Returns:
        Task result dictionary
    """
    logger.info(f"Starting example task: {name} (duration: {duration}s)")

    # Simulate long-running work
    for i in range(duration):
        time.sleep(1)
        logger.debug(f"Task {name} progress: {i + 1}/{duration}")

    result = {
        "task_name": name,
        "duration": duration,
        "status": "completed",
        "message": f"Task {name} completed successfully",
    }

    logger.info(f"Completed example task: {name}")
    return result


def send_email_task(to: str, subject: str, body: str) -> dict[str, Any]:
    """
    Example email sending task.
    In production, this would integrate with an email service.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body

    Returns:
        Task result dictionary
    """
    logger.info(f"Sending email to {to}: {subject}")

    # Simulate email sending
    time.sleep(2)

    # In production, integrate with SendGrid, AWS SES, etc.
    logger.info(f"Email sent to {to}")

    return {
        "to": to,
        "subject": subject,
        "status": "sent",
        "message": "Email sent successfully",
    }


def process_data_task(data: dict[str, Any]) -> dict[str, Any]:
    """
    Example data processing task.
    Useful for ETL operations, data transformations, etc.

    Args:
        data: Input data to process

    Returns:
        Processed data
    """
    logger.info("Starting data processing task")

    # Simulate data processing
    time.sleep(3)

    processed_data = {
        "input": data,
        "processed_at": time.time(),
        "result": "Data processed successfully",
    }

    logger.info("Data processing task completed")
    return processed_data


def extract_document_task(job_id: str) -> dict[str, Any]:
    """
    Background task for document extraction.
    Processes uploaded files and extracts structured data.

    Args:
        job_id: The extraction job ID

    Returns:
        Task result dictionary
    """
    logger.info(f"Starting document extraction for job {job_id}")

    with Session(engine) as session:
        job_service = JobService(session)

        try:
            # Get the job
            job = job_service.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return {
                    "status": "failed",
                    "error": f"Job {job_id} not found"
                }

            # Update job status to running
            job_service.update_job_status(
                job_id,
                JobStatus.RUNNING,
                progress=10
            )

            # Get the file path
            if not job.file_path:
                raise ValueError("No file path associated with job")

            file_path = job.file_path
            logger.info(f"Processing file: {file_path}")

            # Determine file type and extract
            if file_path.lower().endswith(('.xlsx', '.xls')):
                # Excel extraction
                logger.info("Detected Excel file, starting extraction")
                job_service.update_job_status(job_id, JobStatus.RUNNING, progress=30)

                extractor = ExcelExtractor(file_path)
                result, qa_report = extractor.extract()

                job_service.update_job_status(job_id, JobStatus.RUNNING, progress=70)

                # Save results
                success = job_service.save_extraction_results(
                    job_id,
                    result,
                    qa_report
                )

                if success:
                    job_service.update_job_status(
                        job_id,
                        JobStatus.SUCCEEDED,
                        progress=100
                    )
                    logger.info(f"Extraction completed successfully for job {job_id}")
                    return {
                        "status": "completed",
                        "job_id": job_id,
                        "rows_extracted": len(result.rows),
                        "confidence": qa_report.confidence
                    }
                else:
                    raise Exception("Failed to save extraction results")

            elif file_path.lower().endswith('.pdf'):
                # PDF extraction (not yet implemented)
                raise NotImplementedError("PDF extraction not yet implemented")

            else:
                raise ValueError(f"Unsupported file type: {file_path}")

        except Exception as e:
            logger.error(f"Extraction failed for job {job_id}: {str(e)}")
            job_service.update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message=str(e)
            )
            return {
                "status": "failed",
                "job_id": job_id,
                "error": str(e)
            }


def update_job_progress(job_id: str, progress: int) -> dict[str, Any]:
    """
    Helper task to update job progress.
    Useful for complex multi-step extractions.

    Args:
        job_id: The job ID
        progress: Progress percentage (0-100)

    Returns:
        Update result
    """
    with Session(engine) as session:
        job_service = JobService(session)
        job = job_service.update_job_status(
            job_id,
            JobStatus.RUNNING,
            progress=progress
        )

        if job:
            logger.info(f"Updated job {job_id} progress to {progress}%")
            return {
                "status": "updated",
                "job_id": job_id,
                "progress": progress
            }
        else:
            logger.error(f"Failed to update job {job_id}")
            return {
                "status": "failed",
                "error": f"Job {job_id} not found"
            }
