"""
Simplified job model for takeoff extraction service using SQLite.
"""
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import uuid4

from sqlmodel import Field, SQLModel, Session, create_engine


class JobStatus(str, Enum):
    """Job status enumeration."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class TakeoffJob(SQLModel, table=True):
    """
    Simplified job model for takeoff extraction.
    Uses JSON fields for complex data to work well with SQLite.
    """
    __tablename__ = "takeoff_jobs"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    status: JobStatus = Field(default=JobStatus.QUEUED)
    progress: int = Field(default=0, ge=0, le=100)
    template: str = Field(default="baycrest_v1")

    # File info
    original_filename: str
    file_path: Optional[str] = None

    # Sheet selection (JSON array of sheet names)
    sheets_json: Optional[str] = None  # Selected sheets to process

    # Results stored as JSON strings (SQLite-friendly)
    raw_data_json: Optional[str] = None  # Normalized rows
    result_json: Optional[str] = None    # Mapped sections
    qa_json: Optional[str] = None        # QA report

    # Error tracking
    error_message: Optional[str] = None
    error_detail: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def sheets(self) -> Optional[List[str]]:
        """Parse sheets_json to Python object."""
        if self.sheets_json:
            return json.loads(self.sheets_json)
        return None

    @sheets.setter
    def sheets(self, value: List[str]):
        """Set sheets from Python object."""
        self.sheets_json = json.dumps(value)

    @property
    def raw_data(self) -> Optional[List[Dict[str, Any]]]:
        """Parse raw_data_json to Python object."""
        if self.raw_data_json:
            return json.loads(self.raw_data_json)
        return None

    @raw_data.setter
    def raw_data(self, value: List[Dict[str, Any]]):
        """Set raw_data from Python object."""
        self.raw_data_json = json.dumps(value)

    @property
    def result(self) -> Optional[Dict[str, Any]]:
        """Parse result_json to Python object."""
        if self.result_json:
            return json.loads(self.result_json)
        return None

    @result.setter
    def result(self, value: Dict[str, Any]):
        """Set result from Python object."""
        self.result_json = json.dumps(value)

    @property
    def qa(self) -> Optional[Dict[str, Any]]:
        """Parse qa_json to Python object."""
        if self.qa_json:
            return json.loads(self.qa_json)
        return None

    @qa.setter
    def qa(self, value: Dict[str, Any]):
        """Set qa from Python object."""
        self.qa_json = json.dumps(value)


# Database engine configuration
def get_engine(db_url: str = None):
    """
    Create database engine.
    Uses DATABASE_URL from environment if available, otherwise SQLite.
    """
    import os

    if db_url is None:
        # Try to get from environment
        db_url = os.getenv("DATABASE_URL", "sqlite:///./data/takeoff.db")

    if db_url.startswith("sqlite"):
        return create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False}  # Allow multi-threading for SQLite
        )
    else:
        # PostgreSQL or other databases
        return create_engine(
            db_url,
            echo=False
        )


def init_db(engine=None):
    """Initialize database tables."""
    if engine is None:
        engine = get_engine()
    SQLModel.metadata.create_all(engine)


def get_session(engine=None):
    """Get database session."""
    if engine is None:
        engine = get_engine()
    return Session(engine)
