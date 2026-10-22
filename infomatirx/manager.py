"""
Infomatirx Manager
High-level service interface to manage tasks, handoff events, and tangible artifacts.
"""

import json
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any

from infomatirx.db import get_connection, initialize_database, DEFAULT_DB_DIR
from infomatirx.models import (
    Task,
    Event,
    Artifact,
    TaskStatus,
    AgentRole,
    EventType,
    ArtifactType,
    current_iso_time,
)


class InfomatirxManager:
    """Core manager orchestrating database state, artifact files, and event audit trails."""

    def __init__(self, db_path: Optional[str] = None, artifacts_dir: Optional[str] = None):
        self.db_path = db_path
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else DEFAULT_DB_DIR / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        initialize_database(self.db_path)

    def create_task(
        self,
        title: str,
        description: str,
        task_id: Optional[str] = None,
        initial_status: TaskStatus = TaskStatus.BACKLOG,
        initial_role: AgentRole = AgentRole.DESIGNBOT,
        created_by: str = "Founder",
    ) -> Task:
        """Create a new task and log its creation in the audit timeline."""
        tid = task_id or f"task_{uuid.uuid4().hex[:8]}"
        now = current_iso_time()
        task = Task(
            id=tid,
            title=title,
            description=description,
            status=initial_status,
            assigned_role=initial_role,
            created_at=now,
            updated_at=now,
        )

        conn = get_connection(self.db_path)
        with conn:
            conn.execute(
                """
                INSERT INTO tasks (id, title, description, status, assigned_role, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.title,
                    task.description,
                    task.status.value,
                    task.assigned_role.value,
                    task.created_at,
                    task.updated_at,
                ),
            )
        conn.close()

        # Log creation event
        self.log_event(
            task_id=task.id,
            actor=created_by,
            event_type=EventType.STATUS_CHANGE,
            content=f"Task '{title}' created in status {initial_status.value}, assigned to {initial_role.value}.",
            metadata={"initial_status": initial_status.value, "initial_role": initial_role.value},
        )

        return task

    def update_task_status(
        self,
        task_id: str,
        new_status: TaskStatus,
        actor: str,
        new_role: Optional[AgentRole] = None,
        note: Optional[str] = None,
    ) -> Task:
        """Update the status and assignment of a task, logging the transition event."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task with ID '{task_id}' not found.")

        old_status = task.status
        old_role = task.assigned_role
        target_role = new_role or old_role
        now = current_iso_time()

        conn = get_connection(self.db_path)
        with conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, assigned_role = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_status.value, target_role.value, now, task_id),
            )
        conn.close()

        content = f"Status moved from {old_status.value} to {new_status.value}."
        if new_role and new_role != old_role:
            content += f" Reassigned from {old_role.value} to {new_role.value}."
        if note:
            content += f" Note: {note}"

        self.log_event(
            task_id=task_id,
            actor=actor,
            event_type=EventType.STATUS_CHANGE,
            content=content,
            metadata={
                "from_status": old_status.value,
                "to_status": new_status.value,
                "from_role": old_role.value,
                "to_role": target_role.value,
                "note": note,
            },
        )

        return self.get_task(task_id)

    def log_event(
        self,
        task_id: str,
        actor: str,
        event_type: EventType,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Event:
        """Record an immutable event in the task timeline."""
        meta = metadata or {}
        meta_json = json.dumps(meta)
        now = current_iso_time()

        conn = get_connection(self.db_path)
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (task_id, actor, event_type, content, metadata_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, actor, event_type.value, content, meta_json, now),
            )
            event_id = cursor.lastrowid
        conn.close()

        return Event(
            id=event_id,
            task_id=task_id,
            actor=actor,
            event_type=event_type,
            content=content,
            metadata=meta,
            timestamp=now,
        )

    def save_artifact(
        self,
        task_id: str,
        artifact_type: ArtifactType,
        filename: str,
        content: str,
        created_by: str,
    ) -> Artifact:
        """
        Save a tangible deliverable to disk and record its metadata in SQLite.
        Also automatically registers an ARTIFACT_CREATED event in the audit timeline.
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task with ID '{task_id}' not found.")

        # Ensure directory for this task's artifacts exists
        task_artifact_dir = self.artifacts_dir / task_id
        task_artifact_dir.mkdir(parents=True, exist_ok=True)

        artifact_file = task_artifact_dir / filename
        artifact_file.write_text(content, encoding="utf-8")

        artifact_id = f"art_{uuid.uuid4().hex[:8]}"
        now = current_iso_time()
        file_path_str = str(artifact_file.resolve()).replace("\\", "/")

        conn = get_connection(self.db_path)
        with conn:
            conn.execute(
                """
                INSERT INTO artifacts (id, task_id, artifact_type, filename, file_path, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    task_id,
                    artifact_type.value,
                    filename,
                    file_path_str,
                    created_by,
                    now,
                ),
            )
        conn.close()

        # Log artifact creation in the audit trail
        self.log_event(
            task_id=task_id,
            actor=created_by,
            event_type=EventType.ARTIFACT_CREATED,
            content=f"Saved deliverable '{filename}' ({artifact_type.value}) by {created_by}.",
            metadata={"artifact_id": artifact_id, "file_path": file_path_str, "size_bytes": len(content.encode("utf-8"))},
        )

        return Artifact(
            id=artifact_id,
            task_id=task_id,
            artifact_type=artifact_type,
            filename=filename,
            file_path=file_path_str,
            created_by=created_by,
            created_at=now,
        )

    def get_task(self, task_id: str) -> Optional[Task]:
        """Fetch a single task by ID."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            assigned_role=AgentRole(row["assigned_role"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_task_events(self, task_id: str) -> List[Event]:
        """Retrieve all audit events for a task in chronological order."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE task_id = ? ORDER BY id ASC", (task_id,))
        rows = cursor.fetchall()
        conn.close()

        events = []
        for r in rows:
            meta = {}
            try:
                meta = json.loads(r["metadata_json"])
            except Exception:
                meta = {}
            events.append(
                Event(
                    id=r["id"],
                    task_id=r["task_id"],
                    actor=r["actor"],
                    event_type=EventType(r["event_type"]),
                    content=r["content"],
                    metadata=meta,
                    timestamp=r["timestamp"],
                )
            )
        return events

    def get_task_artifacts(self, task_id: str) -> List[Artifact]:
        """Retrieve all recorded artifacts for a task."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM artifacts WHERE task_id = ? ORDER BY created_at ASC", (task_id,))
        rows = cursor.fetchall()
        conn.close()

        return [
            Artifact(
                id=r["id"],
                task_id=r["task_id"],
                artifact_type=ArtifactType(r["artifact_type"]),
                filename=r["filename"],
                file_path=r["file_path"],
                created_by=r["created_by"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List tasks, optionally filtered by status."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC", (status.value,))
        else:
            cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()

        return [
            Task(
                id=r["id"],
                title=r["title"],
                description=r["description"],
                status=TaskStatus(r["status"]),
                assigned_role=AgentRole(r["assigned_role"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def get_full_task_summary(self, task_id: str) -> Dict[str, Any]:
        """Compile a complete view of a task including its status, timeline, and artifacts."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task with ID '{task_id}' not found.")

        events = self.get_task_events(task_id)
        artifacts = self.get_task_artifacts(task_id)

        return {
            "task": task.to_dict(),
            "events": [e.to_dict() for e in events],
            "artifacts": [a.to_dict() for a in artifacts],
        }
