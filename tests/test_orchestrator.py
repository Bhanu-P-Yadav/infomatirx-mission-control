"""
Integration test for Infomatirx Orchestrator Bridge (Phase 4).
Tests the multi-agent pipeline from Backlog -> Design -> Dev -> Test -> Approval Gate -> Released.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from infomatirx.manager import InfomatirxManager
from infomatirx.models import TaskStatus, AgentRole
from infomatirx.orchestrator import InfomatirxOrchestrator


class TestInfomatirxOrchestrator(unittest.TestCase):

    def setUp(self):
        # Create temp dir within workspace mount so Windows cross-drive pathing doesn't fail
        self.test_dir = tempfile.mkdtemp(prefix="tmp_orch_", dir=os.getcwd())
        self.db_path = os.path.join(self.test_dir, "orch_test.db")
        self.artifacts_dir = os.path.join(self.test_dir, "artifacts")
        self.manager = InfomatirxManager(db_path=self.db_path, artifacts_dir=self.artifacts_dir)
        self.orchestrator = InfomatirxOrchestrator(self.manager)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_pipeline_orchestration(self):
        # 1. Create task
        task = self.orchestrator.create_project_task(
            title="Calculator Module",
            description="A simple math module with add and multiply functions.",
            task_id="task_calc_01",
        )
        self.assertEqual(task.status, TaskStatus.BACKLOG)
        self.assertEqual(task.assigned_role, AgentRole.DESIGNBOT)

        # 2. DesignBot Step
        spec_text = (
            "# Overview\nMath calculator library.\n\n"
            "# User Journey\n1. Import math module.\n2. Call add(a, b).\n\n"
            "# UI / Interface Wireframe\nCLI interface.\n\n"
            "# Acceptance Criteria\n- add(2, 3) == 5\n- multiply(4, 5) == 20\n"
        )
        val_design = self.orchestrator.execute_design_step(task.id, spec_text)
        self.assertTrue(val_design.is_valid, f"Design errors: {val_design.errors}")
        t = self.manager.get_task(task.id)
        self.assertEqual(t.status, TaskStatus.DESIGN)
        self.assertEqual(t.assigned_role, AgentRole.DEVBOT)

        # 3. DevBot Step
        code_file = os.path.join(self.test_dir, "calc.py")
        code_content = "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n"
        diff_text = "# Code Changes\nCreated `calc.py` with `add` and `multiply` functions."
        val_dev = self.orchestrator.execute_dev_step(
            task.id,
            files={code_file: code_content},
            diff_summary=diff_text,
        )
        self.assertTrue(val_dev.is_valid, f"Dev errors: {val_dev.errors}")
        t = self.manager.get_task(task.id)
        self.assertEqual(t.status, TaskStatus.DEV)
        self.assertEqual(t.assigned_role, AgentRole.TESTBOT)

        # 4. TestBot Step (runs real python subprocess test)
        test_file = os.path.join(self.test_dir, "test_calc.py")
        test_content = (
            "import unittest\n"
            "import sys\n"
            f"sys.path.insert(0, r'{self.test_dir}')\n"
            "from calc import add, multiply\n\n"
            "class TestCalc(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n"
            "    def test_multiply(self):\n"
            "        self.assertEqual(multiply(4, 5), 20)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        Path(test_file).write_text(test_content, encoding="utf-8")

        # Run test script directly
        cmd = f"python {test_file}"
        val_test = self.orchestrator.execute_test_step(task.id, cmd)
        self.assertTrue(val_test.is_valid, f"Test errors: {val_test.errors}")
        t = self.manager.get_task(task.id)
        self.assertEqual(t.status, TaskStatus.TEST)
        self.assertEqual(t.assigned_role, AgentRole.RELEASEBOT)

        # 5. ReleaseBot Step
        notes = "# Release Notes v0.1.0\nCalculator ready for release."
        val_rel = self.orchestrator.execute_release_step(task.id, "v0.1.0", notes)
        self.assertTrue(val_rel.is_valid, f"Release errors: {val_rel.errors}")
        t = self.manager.get_task(task.id)
        self.assertEqual(t.status, TaskStatus.WAITING_APPROVAL)
        self.assertEqual(t.assigned_role, AgentRole.HUMAN)

        # 6. Founder Human Authorization
        val_approved = self.orchestrator.founder_approve_and_release(
            task.id,
            approver="Founder",
            comment="Verified on Mission Control. Approved for production.",
        )
        self.assertTrue(val_approved.is_valid, f"Approval errors: {val_approved.errors}")
        final_task = self.manager.get_task(task.id)
        self.assertEqual(final_task.status, TaskStatus.RELEASED)


if __name__ == "__main__":
    unittest.main()
