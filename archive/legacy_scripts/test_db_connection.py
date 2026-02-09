#!/usr/bin/env python3
"""
Test database connection and TakeoffJob model.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.takeoff_job import TakeoffJob, get_engine, init_db, get_session, JobStatus
from datetime import datetime


def test_database():
    """Test database operations with TakeoffJob model."""

    print("Testing database connection...")

    # Initialize database
    engine = get_engine("sqlite:///./data/takeoff.db")
    init_db(engine)

    # Get a session
    session = get_session(engine)

    try:
        # Create a test job
        test_job = TakeoffJob(
            status=JobStatus.QUEUED,
            template="baycrest_v1",
            original_filename="test.xlsx",
            sheets=["Sheet1", "Sheet2"]  # This will set sheets_json
        )

        # Add to session and commit
        session.add(test_job)
        session.commit()

        print(f"✓ Created test job: {test_job.id}")
        print(f"  - Status: {test_job.status}")
        print(f"  - Template: {test_job.template}")
        print(f"  - Filename: {test_job.original_filename}")
        print(f"  - Sheets: {test_job.sheets}")
        print(f"  - Sheets JSON: {test_job.sheets_json}")

        # Query the job back
        retrieved_job = session.get(TakeoffJob, test_job.id)
        print(f"\n✓ Retrieved job: {retrieved_job.id}")
        print(f"  - Sheets from property: {retrieved_job.sheets}")

        # Update the job
        retrieved_job.status = JobStatus.RUNNING
        retrieved_job.started_at = datetime.utcnow()
        session.commit()
        print(f"\n✓ Updated job status to: {retrieved_job.status}")

        # Clean up - delete test job
        session.delete(retrieved_job)
        session.commit()
        print(f"\n✓ Deleted test job")

        print("\n✅ All database operations successful!")
        print("The database is properly configured with the sheets_json column.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    test_database()