"""
Database management for Infomatirx using SQLite.
Zero external dependencies, serverless, single-file storage.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional

# Default database path inside .infomatirx directory in the workspace root
DEFAULT_DB_DIR = Path(".infomatirx")
DEFAULT_DB_FILE = DEFAULT_DB_DIR / "infomatirx.db"


def get_db_path(custom_path: Optional[str] = None) -> Path:
    """Resolve the database path, ensuring parent directories exist."""
    path = Path(custom_path) if custom_path else DEFAULT_DB_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection(custom_path: Optional[str] = None) -> sqlite3.Connection:
    """Create a database connection with foreign key enforcement and row factory."""
    db_path = get_db_path(custom_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(custom_path: Optional[str] = None) -> None:
    """Create the core database schema if it does not already exist."""
    conn = get_connection(custom_path)
    with conn:
        cursor = conn.cursor()

        # 1. Tasks Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                assigned_role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # 2. Events Table (Audit Log & Timeline)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
            );
        """)

        # 3. Artifacts Table (Deliverables on disk)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
            );
        """)

        # Create indexes for quick retrieval
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_task_id ON events (task_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_task_id ON artifacts (task_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);")

    conn.close()
