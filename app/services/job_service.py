"""
Job service for managing extraction jobs.
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import UploadFile
from sqlmodel import Session, select

from app.core.logging import get_logger
from app.models.job import ExtractionJob, ExtractedRow, JobStatus, JobType, QAWarning
from app.schemas.job import JobStatusResponse, ExtractionResult, QAReport
from app.services.file_storage_service import file_storage_service

logger = get_logger(__name__)


class JobService:
    """
    Service for managing extraction jobs.
    Coordinates between storage, extraction, and database.
    """

    def __init__(self, session: Session):
        self.session = session

    def create_job(
        self,
        job_type: JobType,
        file: UploadFile,
        user_id: Optional[int] = None
    ) -> ExtractionJob:
        """
        Create a new extraction job.

        Args:
            job_type: Type of extraction to perform
            file: The uploaded file
            user_id: Optional user ID for tracking

        Returns:
            The created job
        """
        try:
            # Create job record
            job = ExtractionJob(
                job_type=job_type,
                original_filename=file.filename,
                status=JobStatus.QUEUED,
                user_id=user_id
            )
            self.session.add(job)
            self.session.commit()

            # Save uploaded file
            file_path = file_storage_service.save_uploaded_file(file, job.id)
            job.file_path = file_path
            self.session.commit()

            logger.info(f"Created job {job.id} for file {file.filename}")
            return job

        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            self.session.rollback()
            raise

    def get_job(self, job_id: str) -> Optional[ExtractionJob]:
        """Get a job by ID."""
        return self.session.get(ExtractionJob, job_id)

    def get_jobs(
        self,
        user_id: Optional[int] = None,
        status: Optional[JobStatus] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[ExtractionJob]:
        """
        Get jobs with optional filtering.

        Args:
            user_id: Filter by user ID
            status: Filter by status
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip

        Returns:
            List of jobs
        """
        query = select(ExtractionJob)

        if user_id is not None:
            query = query.where(ExtractionJob.user_id == user_id)

        if status is not None:
            query = query.where(ExtractionJob.status == status)

        query = query.order_by(ExtractionJob.created_at.desc())
        query = query.limit(limit).offset(offset)

        return list(self.session.exec(query))

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> Optional[ExtractionJob]:
        """
        Update job status and progress.

        Args:
            job_id: The job ID
            status: New status
            progress: Optional progress update (0-100)
            error_message: Optional error message

        Returns:
            Updated job or None if not found
        """
        job = self.get_job(job_id)
        if not job:
            return None

        job.status = status
        if progress is not None:
            job.progress = min(max(progress, 0), 100)

        # Update timestamps based on status
        if status == JobStatus.RUNNING and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        elif status in [JobStatus.SUCCEEDED, JobStatus.FAILED]:
            job.completed_at = datetime.now(timezone.utc)
            if status == JobStatus.SUCCEEDED:
                job.progress = 100
        elif status == JobStatus.FINALIZED:
            job.finalized_at = datetime.now(timezone.utc)

        if error_message:
            job.error_message = error_message

        self.session.commit()
        logger.info(f"Updated job {job_id} status to {status}")
        return job

    def save_extraction_results(
        self,
        job_id: str,
        result: ExtractionResult,
        qa_report: QAReport
    ) -> bool:
        """
        Save extraction results to database and file storage.

        Args:
            job_id: The job ID
            result: The extraction results
            qa_report: The QA report

        Returns:
            True if successful
        """
        try:
            job = self.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return False

            # Save results to database
            job.result = result.model_dump()
            job.qa_report = qa_report.model_dump()

            # Save individual rows for better querying
            for row_data in result.rows:
                # Extract provenance if present
                provenance = row_data.pop("__provenance", {})

                extracted_row = ExtractedRow(
                    job_id=job_id,
                    data=row_data,
                    sheet_name=provenance.get("sheet_name"),
                    excel_row_index=provenance.get("excel_row_index"),
                    source_cell_range=provenance.get("source_cell_range"),
                    has_warnings=len(qa_report.warnings) > 0
                )
                self.session.add(extracted_row)

            # Save QA warnings
            for warning in qa_report.warnings:
                qa_warning = QAWarning(
                    job_id=job_id,
                    warning_type=warning.get("type", "unknown"),
                    severity=warning.get("severity", "warning"),
                    message=warning.get("message", ""),
                    details=warning,
                    sheet_name=warning.get("sheet_name"),
                    row_index=warning.get("row"),
                    column_name=warning.get("header")
                )
                self.session.add(qa_warning)

            # Save results to file storage
            results_data = {
                "extraction": result.model_dump(),
                "qa": qa_report.model_dump()
            }
            result_path = file_storage_service.save_extraction_results(job_id, results_data)
            job.result_path = result_path

            # Update job status
            job.status = JobStatus.SUCCEEDED
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)

            self.session.commit()
            logger.info(f"Saved extraction results for job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save extraction results: {e}")
            self.session.rollback()
            return False

    def finalize_job(self, job_id: str) -> Optional[ExtractionJob]:
        """
        Finalize a job, making its results immutable.

        Args:
            job_id: The job ID

        Returns:
            The finalized job or None if not found/already finalized
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return None

        if job.status == JobStatus.FINALIZED:
            logger.warning(f"Job {job_id} is already finalized")
            return job

        if job.status != JobStatus.SUCCEEDED:
            logger.error(f"Cannot finalize job {job_id} with status {job.status}")
            return None

        job.status = JobStatus.FINALIZED
        job.finalized_at = datetime.now(timezone.utc)
        self.session.commit()

        logger.info(f"Finalized job {job_id}")
        return job

    def get_job_status_response(self, job_id: str) -> Optional[JobStatusResponse]:
        """
        Get job status as a response schema.

        Args:
            job_id: The job ID

        Returns:
            JobStatusResponse or None if not found
        """
        job = self.get_job(job_id)
        if not job:
            return None

        # Convert stored dictionaries back to Pydantic models
        result = None
        qa = None

        if job.result:
            result = ExtractionResult(**job.result)

        if job.qa_report:
            qa = QAReport(**job.qa_report)

        return JobStatusResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            result=result,
            qa=qa,
            error=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            finalized_at=job.finalized_at
        )

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job and all associated data.

        Args:
            job_id: The job ID

        Returns:
            True if successful
        """
        try:
            job = self.get_job(job_id)
            if not job:
                return False

            # Delete files
            file_storage_service.delete_job_files(job_id)

            # Delete database records (cascade will handle related rows)
            self.session.delete(job)
            self.session.commit()

            logger.info(f"Deleted job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete job: {e}")
            self.session.rollback()
            return False

    def get_job_results_file(self, job_id: str) -> Optional[str]:
        """
        Get the path to the results file for a job.

        Args:
            job_id: The job ID

        Returns:
            File path or None if not found
        """
        job = self.get_job(job_id)
        if job and job.result_path:
            return job.result_path
        return None
