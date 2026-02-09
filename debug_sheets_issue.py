#!/usr/bin/env python3
"""
Debug the sheets_json issue
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.takeoff_job import TakeoffJob, get_engine, init_db, get_session, JobStatus
import json


def test_sheets_setter():
    """Test the sheets setter property"""

    print("Testing sheets setter...")

    # Test 1: Direct property assignment
    try:
        job = TakeoffJob(
            template="baycrest_v1",
            original_filename="test.xlsx"
        )

        print(f"Initial sheets: {job.sheets}")
        print(f"Initial sheets_json: {job.sheets_json}")

        # Try setting sheets
        job.sheets = ["1 Bldg", "2 Bldgs"]

        print(f"After setting sheets: {job.sheets}")
        print(f"After setting sheets_json: {job.sheets_json}")

        print("✅ Direct property assignment works")
    except Exception as e:
        print(f"❌ Direct property assignment failed: {e}")

    # Test 2: Database round-trip
    try:
        engine = get_engine("sqlite:///./data/takeoff.db")
        init_db(engine)
        session = get_session(engine)

        # Create job with sheets
        job = TakeoffJob(
            template="baycrest_v1",
            original_filename="test.xlsx",
            status=JobStatus.QUEUED
        )

        # Set sheets using property
        job.sheets = ["Sheet1", "Sheet2"]

        session.add(job)
        session.commit()

        job_id = job.id
        print(f"\nCreated job {job_id}")
        print(f"  sheets: {job.sheets}")
        print(f"  sheets_json: {job.sheets_json}")

        # Retrieve it
        retrieved_job = session.get(TakeoffJob, job_id)
        print(f"\nRetrieved job {job_id}")
        print(f"  sheets: {retrieved_job.sheets}")
        print(f"  sheets_json: {retrieved_job.sheets_json}")

        # Clean up
        session.delete(retrieved_job)
        session.commit()
        session.close()

        print("\n✅ Database round-trip works")
    except Exception as e:
        print(f"\n❌ Database round-trip failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_sheets_setter()