"""
Unit and integration test for Infomatirx Core Engine (Phase 1).
Verifies database initialization, task state transitions, event audit logging,
distinction between simulated and executed events, and tangible artifact storage.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from infomatirx.manager import InfomatirxManager
from infomatirx.models import (
    TaskStatus,
    AgentRole,
    EventType,
    ArtifactType,
)


class TestInfomatirxCoreEngine(unittest.TestCase):

    def setUp(self):
        """Set up an isolated temporary workspace for the test run."""
        self.test_dir = tempfile.mkdtemp(prefix="infomatirx_test_")
        self.db_path = os.path.join(self.test_dir, "test_infomatirx.db")
        self.artifacts_dir = os.path.join(self.test_dir, "artifacts")
        self.manager = InfomatirxManager(
            db_path=self.db_path,
            artifacts_dir=self.artifacts_dir,
        )

    def tearDown(self):
        """Clean up temporary test directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_task_lifecycle_and_audit_trail(self):
        # 1. Create a task
        task = self.manager.create_task(
            title="Markdown Preview CLI",
            description="Build a CLI tool that parses and renders Markdown in the terminal.",
            task_id="task_test_001",
            initial_status=TaskStatus.BACKLOG,
            initial_role=AgentRole.DESIGNBOT,
            created_by="Founder",
        )

        self.assertEqual(task.id, "task_test_001")
        self.assertEqual(task.status, TaskStatus.BACKLOG)
        self.assertEqual(task.assigned_role, AgentRole.DESIGNBOT)

        # 2. Advance to DESIGN stage
        updated_task = self.manager.update_task_status(
            task_id=task.id,
            new_status=TaskStatus.DESIGN,
            actor="Orchestrator",
            note="Starting design and requirements drafting.",
        )
        self.assertEqual(updated_task.status, TaskStatus.DESIGN)

        # 3. Log a simulated LLM message (DesignBot chatting)
        self.manager.log_event(
            task_id=task.id,
            actor="DesignBot",
            event_type=EventType.SIMULATED_MESSAGE,
            content="I have reviewed the CLI requirements and drafted the user journey and spec.",
        )

        # 4. Save Design Spec Artifact
        spec_content = (
            "# Markdown Preview CLI Spec\n\n"
            "## User Journey\n"
            "1. User runs `python preview.py README.md`\n"
            "2. Formatted terminal output is displayed with colors.\n"
        )
        artifact = self.manager.save_artifact(
            task_id=task.id,
            artifact_type=ArtifactType.SPEC,
            filename="spec.md",
            content=spec_content,
            created_by="DesignBot",
        )
        self.assertEqual(artifact.artifact_type, ArtifactType.SPEC)
        self.assertTrue(Path(artifact.file_path).exists(), "Artifact file must exist on disk")
        self.assertEqual(Path(artifact.file_path).read_text(encoding="utf-8"), spec_content)

        # 5. Log a real tool execution (DevBot / TestBot executing tests)
        self.manager.log_event(
            task_id=task.id,
            actor="TestBot",
            event_type=EventType.TOOL_EXECUTION,
            content="Executed unit test runner `pytest tests/`",
            metadata={
                "command": "pytest tests/",
                "exit_code": 0,
                "passed_tests": 4,
                "failed_tests": 0,
                "duration_ms": 320,
            },
        )

        # 6. Log Human Approval Gate
        self.manager.log_event(
            task_id=task.id,
            actor="Founder",
            event_type=EventType.HUMAN_APPROVAL,
            content="Approved release draft for public tag v0.1.0.",
        )

        # 7. Final status transition to RELEASED
        final_task = self.manager.update_task_status(
            task_id=task.id,
            new_status=TaskStatus.RELEASED,
            actor="ReleaseBot",
            new_role=AgentRole.HUMAN,
            note="Release complete.",
        )
        self.assertEqual(final_task.status, TaskStatus.RELEASED)

        # 8. Query summary and verify the audit trail
        summary = self.manager.get_full_task_summary(task.id)

        self.assertEqual(summary["task"]["status"], "RELEASED")
        self.assertEqual(len(summary["artifacts"]), 1)
        self.assertEqual(summary["artifacts"][0]["filename"], "spec.md")

        event_types = [e["event_type"] for e in summary["events"]]
        self.assertIn("STATUS_CHANGE", event_types)
        self.assertIn("SIMULATED_MESSAGE", event_types)
        self.assertIn("ARTIFACT_CREATED", event_types)
        self.assertIn("TOOL_EXECUTION", event_types)
        self.assertIn("HUMAN_APPROVAL", event_types)

        # Verify tool execution metadata was recorded accurately
        tool_event = next(e for e in summary["events"] if e["event_type"] == "TOOL_EXECUTION")
        self.assertEqual(tool_event["metadata"]["exit_code"], 0)
        self.assertEqual(tool_event["metadata"]["passed_tests"], 4)


if __name__ == "__main__":
    unittest.main()
