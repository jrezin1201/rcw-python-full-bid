"""
Job models for extraction service.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import uuid4

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel, Column, JSON, Relationship


class JobStatus(str, Enum):
    """Job status enumeration."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    FINALIZED = "FINALIZED"


class JobType(str, Enum):
    """Job type enumeration."""
    RC_WENDT_BID_V1 = "rc_wendt_bid_v1"
    # TODO: Add more extraction types as needed


class ExtractionJob(SQLModel, table=True):
    """
    Main job model for tracking extraction requests.
    """
    __tablename__ = "extraction_jobs"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    status: JobStatus = Field(default=JobStatus.QUEUED)
    job_type: JobType
    progress: int = Field(default=0, ge=0, le=100)

    # File information
    original_filename: str
    file_path: Optional[str] = None  # Path to uploaded file
    result_path: Optional[str] = None  # Path to result JSON

    # Extraction results (stored as JSON)
    result: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    qa_report: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Error tracking
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None

    # User tracking (optional, for multi-tenant scenarios)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")

    # Relationship to extracted rows
    extracted_rows: List["ExtractedRow"] = Relationship(back_populates="job")

    model_config = ConfigDict(use_enum_values=True)


class ExtractedRow(SQLModel, table=True):
    """
    Individual extracted row from a document.
    Stored separately for better querying and analysis.
    """
    __tablename__ = "extracted_rows"

    id: int = Field(default=None, primary_key=True)
    job_id: str = Field(foreign_key="extraction_jobs.id")

    # Provenance information
    sheet_name: Optional[str] = None
    excel_row_index: Optional[int] = None
    source_cell_range: Optional[str] = None

    # Row data (stored as JSON)
    data: Dict[str, Any] = Field(sa_column=Column(JSON))

    # Quality indicators
    has_warnings: bool = Field(default=False)
    warnings: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationship back to job
    job: Optional[ExtractionJob] = Relationship(back_populates="extracted_rows")


class QAWarning(SQLModel, table=True):
    """
    Quality assurance warnings for extraction jobs.
    """
    __tablename__ = "qa_warnings"

    id: int = Field(default=None, primary_key=True)
    job_id: str = Field(foreign_key="extraction_jobs.id")

    warning_type: str  # e.g., "unmapped_column", "type_anomaly", "suspected_total"
    severity: str = Field(default="warning")  # "info", "warning", "error"
    message: str
    details: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Location information
    sheet_name: Optional[str] = None
    row_index: Optional[int] = None
    column_name: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
