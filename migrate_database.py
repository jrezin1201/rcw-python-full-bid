#!/usr/bin/env python3
"""
Database migration script to add missing columns or create database.
"""

import sqlite3
import os
from pathlib import Path

def migrate_database():
    """Add missing columns to existing database or create new one."""

    # Ensure data directory exists
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)

    db_path = "./data/takeoff.db"

    # Connect to database (creates if doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='takeoff_jobs'
        """)
        table_exists = cursor.fetchone() is not None

        if table_exists:
            print("Table 'takeoff_jobs' exists. Checking for missing columns...")

            # Get existing columns
            cursor.execute("PRAGMA table_info(takeoff_jobs)")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"Existing columns: {columns}")

            # Add sheets_json column if it doesn't exist
            if 'sheets_json' not in columns:
                print("Adding 'sheets_json' column...")
                cursor.execute("""
                    ALTER TABLE takeoff_jobs
                    ADD COLUMN sheets_json TEXT
                """)
                print("Column 'sheets_json' added successfully!")
            else:
                print("Column 'sheets_json' already exists.")

        else:
            print("Table 'takeoff_jobs' doesn't exist. Creating with full schema...")

            # Create table with all columns including sheets_json
            cursor.execute("""
                CREATE TABLE takeoff_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    template TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    file_path TEXT,
                    sheets_json TEXT,
                    raw_data_json TEXT,
                    result_json TEXT,
                    qa_json TEXT,
                    error_message TEXT,
                    error_detail TEXT,
                    created_at TIMESTAMP NOT NULL,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            print("Table 'takeoff_jobs' created successfully!")

        # Commit changes
        conn.commit()
        print(f"\nDatabase migration completed successfully!")
        print(f"Database location: {os.path.abspath(db_path)}")

    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()