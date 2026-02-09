"""
Job schemas for extraction service.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.models.job import JobStatus, JobType


class JobCreateResponse(BaseModel):
    """Response after creating a job."""
    job_id: str
    status: JobStatus


class ExtractedRowData(BaseModel):
    """Data for an extracted row."""
    data: Dict[str, Any]
    provenance: Dict[str, Any] = Field(
        description="Source information (sheet_name, row_index, etc.)"
    )
    warnings: Optional[List[str]] = None


class ExtractionResult(BaseModel):
    """Extraction result data structure."""
    rows: List[Dict[str, Any]]
    columns: List[str]
    provenance: Dict[str, Any]  # Global provenance info


class QAReport(BaseModel):
    """Quality assurance report."""
    rows_extracted: int
    unmapped_columns: List[str] = Field(default_factory=list)
    empty_rows_removed: int = 0
    suspected_totals_rows: List[int] = Field(default_factory=list)
    type_anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)


class JobStatusResponse(BaseModel):
    """Response for job status queries."""
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    result: Optional[ExtractionResult] = None
    qa: Optional[QAReport] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None


class JobFinalizeRequest(BaseModel):
    """Request to finalize a job."""
    confirm: bool = Field(
        description="Must be true to confirm finalization",
        default=True
    )


class JobFinalizeResponse(BaseModel):
    """Response after finalizing a job."""
    job_id: str
    status: JobStatus
    finalized_at: datetime
    message: str = "Job has been finalized and results are now immutable"


class JobListResponse(BaseModel):
    """Response for listing jobs."""
    jobs: List[JobStatusResponse]
    total: int
    page: int = 1
    per_page: int = 20


class JobDownloadMetadata(BaseModel):
    """Metadata for downloaded results."""
    job_id: str
    job_type: JobType
    filename: str
    created_at: datetime
    rows_count: int
    qa_confidence: float