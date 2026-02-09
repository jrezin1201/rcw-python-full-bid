"""
File storage service for managing uploaded files and extraction results.
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import UploadFile

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class FileStorageService:
    """
    Manages file storage for:
    - Uploaded documents (Excel, PDF, etc.)
    - Extracted results (JSON)
    - Temporary processing files
    """

    def __init__(self):
        # Use settings if available, otherwise use defaults
        self.base_path = Path(getattr(settings, 'FILE_STORAGE_PATH', './data'))
        self.uploads_path = self.base_path / 'uploads'
        self.results_path = self.base_path / 'results'
        self.temp_path = self.base_path / 'temp'

        # Create directories if they don't exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure all required directories exist."""
        for path in [self.uploads_path, self.results_path, self.temp_path]:
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {path}")

    def save_uploaded_file(
        self,
        file: UploadFile,
        job_id: str
    ) -> str:
        """
        Save an uploaded file to the storage system.

        Args:
            file: The uploaded file from FastAPI
            job_id: The job ID to associate with the file

        Returns:
            The path where the file was saved
        """
        try:
            # Create job-specific directory
            job_upload_path = self.uploads_path / job_id
            job_upload_path.mkdir(parents=True, exist_ok=True)

            # Sanitize filename
            safe_filename = self._sanitize_filename(file.filename)

            # Add timestamp to prevent collisions
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            final_filename = f"{timestamp}_{safe_filename}"

            # Full file path
            file_path = job_upload_path / final_filename

            # Save the file
            with file_path.open('wb') as buffer:
                shutil.copyfileobj(file.file, buffer)

            logger.info(f"Saved uploaded file: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Failed to save uploaded file: {e}")
            raise

    def save_extraction_results(
        self,
        job_id: str,
        results: Dict[str, Any]
    ) -> str:
        """
        Save extraction results as JSON.

        Args:
            job_id: The job ID
            results: The extraction results dictionary

        Returns:
            The path where the results were saved
        """
        try:
            # Create results file path
            result_file = self.results_path / f"{job_id}.json"

            # Add metadata
            results_with_metadata = {
                "job_id": job_id,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "version": "1.0",
                **results
            }

            # Save as JSON
            with result_file.open('w') as f:
                json.dump(results_with_metadata, f, indent=2, default=str)

            logger.info(f"Saved extraction results: {result_file}")
            return str(result_file)

        except Exception as e:
            logger.error(f"Failed to save extraction results: {e}")
            raise

    def get_extraction_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Load extraction results from storage.

        Args:
            job_id: The job ID

        Returns:
            The extraction results or None if not found
        """
        try:
            result_file = self.results_path / f"{job_id}.json"

            if not result_file.exists():
                logger.warning(f"Results file not found: {result_file}")
                return None

            with result_file.open('r') as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Failed to load extraction results: {e}")
            return None

    def get_uploaded_file_path(self, job_id: str) -> Optional[str]:
        """
        Get the path to the uploaded file for a job.

        Args:
            job_id: The job ID

        Returns:
            The file path or None if not found
        """
        job_upload_path = self.uploads_path / job_id

        if not job_upload_path.exists():
            return None

        # Get the first file in the directory (should only be one)
        files = list(job_upload_path.iterdir())
        if files:
            return str(files[0])

        return None

    def delete_job_files(self, job_id: str) -> bool:
        """
        Delete all files associated with a job.

        Args:
            job_id: The job ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete uploaded files
            job_upload_path = self.uploads_path / job_id
            if job_upload_path.exists():
                shutil.rmtree(job_upload_path)
                logger.info(f"Deleted upload directory: {job_upload_path}")

            # Delete results file
            result_file = self.results_path / f"{job_id}.json"
            if result_file.exists():
                result_file.unlink()
                logger.info(f"Deleted results file: {result_file}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete job files: {e}")
            return False

    def get_file_size(self, file_path: str) -> int:
        """Get the size of a file in bytes."""
        try:
            path = Path(file_path)
            if path.exists():
                return path.stat().st_size
            return 0
        except Exception as e:
            logger.error(f"Failed to get file size: {e}")
            return 0

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename to prevent path traversal attacks.

        Args:
            filename: The original filename

        Returns:
            A safe filename
        """
        # Remove any path components
        filename = Path(filename).name

        # Replace spaces and special characters
        safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-')
        sanitized = ''.join(c if c in safe_chars else '_' for c in filename)

        # Ensure it has an extension
        if '.' not in sanitized:
            sanitized = f"{sanitized}.unknown"

        return sanitized

    def cleanup_old_files(self, days: int = 7) -> int:
        """
        Clean up files older than specified days.

        Args:
            days: Number of days to keep files

        Returns:
            Number of files deleted
        """
        try:
            deleted_count = 0
            cutoff_time = datetime.now(timezone.utc).timestamp() - (days * 24 * 60 * 60)

            # Clean uploads
            for job_path in self.uploads_path.iterdir():
                if job_path.is_dir() and job_path.stat().st_mtime < cutoff_time:
                    shutil.rmtree(job_path)
                    deleted_count += 1
                    logger.info(f"Deleted old upload directory: {job_path}")

            # Clean results
            for result_file in self.results_path.glob('*.json'):
                if result_file.stat().st_mtime < cutoff_time:
                    result_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old results file: {result_file}")

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return 0


# Create a singleton instance
file_storage_service = FileStorageService()
