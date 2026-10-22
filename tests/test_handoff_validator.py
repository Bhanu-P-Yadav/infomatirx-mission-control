"""
Unit and integration tests for the Handoff Validator (Phase 2).
Validates quality gates, anti-hallucination checks, and human gatekeeper enforcement.
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
from infomatirx.validator import HandoffValidator


class TestHandoffValidator(unittest.TestCase):

    def setUp(self):
        """Create isolated test workspace."""
        self.test_dir = tempfile.mkdtemp(prefix="infomatirx_val_test_")
        self.db_path = os.path.join(self.test_dir, "test.db")
        self.artifacts_dir = os.path.join(self.test_dir, "artifacts")
        self.manager = InfomatirxManager(
            db_path=self.db_path,
            artifacts_dir=self.artifacts_dir,
        )
        self.validator = HandoffValidator(self.manager)

        # Create a sample task
        self.task = self.manager.create_task(
            title="Slugifier Utility",
            description="Create a python function to turn text strings into clean URL slugs.",
            task_id="task_slug_01",
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_design_handoff_validation(self):
        # 1. Initially no spec exists -> Should FAIL
        res = self.validator.validate_design_handoff(self.task.id)
        self.assertFalse(res.is_valid)
        self.assertIn("No design specification (spec.md) found", res.errors[0])

        # 2. Spec exists but lacks required sections -> Should FAIL
        incomplete_spec = "# Overview\nA slugifier."
        self.manager.save_artifact(
            task_id=self.task.id,
            artifact_type=ArtifactType.SPEC,
            filename="spec.md",
            content=incomplete_spec,
            created_by="DesignBot",
        )
        res = self.validator.validate_design_handoff(self.task.id)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("User Journey" in e for e in res.errors))
        self.assertTrue(any("Acceptance Criteria" in e for e in res.errors))

        # 3. Complete spec -> Should PASS
        valid_spec = (
            "# Overview\nA slugifier function.\n\n"
            "# User Journey\n1. Import slugify.\n2. Call slugify('Hello World').\n\n"
            "# Acceptance Criteria\n- Lowercases string\n- Replaces spaces with hyphens\n"
        )
        self.manager.save_artifact(
            task_id=self.task.id,
            artifact_type=ArtifactType.SPEC,
            filename="spec.md",
            content=valid_spec,
            created_by="DesignBot",
        )
        res = self.validator.validate_design_handoff(self.task.id)
        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.errors), 0)

    def test_dev_handoff_syntax_and_file_checks(self):
        # 1. Broken Python syntax in code file -> Should FAIL
        broken_code_path = Path(self.test_dir) / "broken.py"
        broken_code_path.write_text("def slugify(text\n    return text", encoding="utf-8")

        res = self.validator.validate_dev_handoff(self.task.id, code_files=[str(broken_code_path)])
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Syntax error" in e for e in res.errors))

        # 2. Valid Python code -> Should PASS
        valid_code_path = Path(self.test_dir) / "slugifier.py"
        valid_code_path.write_text("def slugify(text: str) -> str:\n    return text.lower().replace(' ', '-')\n", encoding="utf-8")

        res = self.validator.validate_dev_handoff(self.task.id, code_files=[str(valid_code_path)])
        self.assertTrue(res.is_valid)

    def test_testbot_anti_hallucination_check(self):
        # 1. Agent only talks in chat with NO actual tool execution -> Should FAIL
        self.manager.log_event(
            task_id=self.task.id,
            actor="TestBot",
            event_type=EventType.SIMULATED_MESSAGE,
            content="I ran the test suite and all 10 tests passed!",
        )
        self.manager.save_artifact(
            task_id=self.task.id,
            artifact_type=ArtifactType.TEST_REPORT,
            filename="test_report.md",
            content="# Test Execution Summary\nAll passed.",
            created_by="TestBot",
        )
        res = self.validator.validate_test_handoff(self.task.id)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("No verified TOOL_EXECUTION event found" in e for e in res.errors))

        # 2. Real tool execution logged, but test failed (exit_code != 0) -> Should FAIL
        self.manager.log_event(
            task_id=self.task.id,
            actor="TestBot",
            event_type=EventType.TOOL_EXECUTION,
            content="Ran pytest tests/test_slug.py",
            metadata={"command": "pytest", "exit_code": 1, "failures": 1},
        )
        res = self.validator.validate_test_handoff(self.task.id)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("failed with exit code 1" in e for e in res.errors))

        # 3. Test execution succeeds with exit_code == 0 -> Should PASS
        self.manager.log_event(
            task_id=self.task.id,
            actor="TestBot",
            event_type=EventType.TOOL_EXECUTION,
            content="Ran pytest tests/test_slug.py",
            metadata={"command": "pytest", "exit_code": 0, "passed": 5},
        )
        res = self.validator.validate_test_handoff(self.task.id)
        self.assertTrue(res.is_valid)

    def test_human_gatekeeper_enforcement(self):
        # Save release notes
        self.manager.save_artifact(
            task_id=self.task.id,
            artifact_type=ArtifactType.RELEASE_NOTES,
            filename="release_notes.md",
            content="# Release Notes v0.1.0\nReady for launch.",
            created_by="ReleaseBot",
        )

        # 1. Attempting transition to RELEASED without human approval -> BLOCKED
        res = self.validator.validate_release_handoff(self.task.id, target_status=TaskStatus.RELEASED)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("CONSEQUENTIAL ACTION BLOCKED" in e for e in res.errors))

        # 2. Moving to WAITING_APPROVAL is allowed for ReleaseBot
        res_waiting = self.validator.validate_release_handoff(self.task.id, target_status=TaskStatus.WAITING_APPROVAL)
        self.assertTrue(res_waiting.is_valid)

        # 3. Human logs approval -> RELEASED is permitted
        self.manager.log_event(
            task_id=self.task.id,
            actor="Founder",
            event_type=EventType.HUMAN_APPROVAL,
            content="Approved public release v0.1.0.",
        )
        res_approved = self.validator.validate_release_handoff(self.task.id, target_status=TaskStatus.RELEASED)
        self.assertTrue(res_approved.is_valid)


if __name__ == "__main__":
    unittest.main()
