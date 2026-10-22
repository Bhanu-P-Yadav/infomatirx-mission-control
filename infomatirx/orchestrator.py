"""
Infomatirx Orchestrator Bridge.
Coordinates specialist agents, executes verified tool commands, enforces handoff quality gates,
and halts at the Human Gatekeeper.
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from infomatirx.manager import InfomatirxManager
from infomatirx.models import (
    Task,
    TaskStatus,
    AgentRole,
    EventType,
    ArtifactType,
)
from infomatirx.validator import HandoffValidator, ValidationResult


class InfomatirxOrchestrator:
    """High-level multi-agent pipeline orchestrator."""

    def __init__(self, manager: Optional[InfomatirxManager] = None):
        self.manager = manager or InfomatirxManager()
        self.validator = HandoffValidator(self.manager)

    def create_project_task(self, title: str, description: str, task_id: Optional[str] = None) -> Task:
        """Initialize a new task in BACKLOG assigned to DesignBot."""
        return self.manager.create_task(
            title=title,
            description=description,
            task_id=task_id,
            initial_status=TaskStatus.BACKLOG,
            initial_role=AgentRole.DESIGNBOT,
        )

    def execute_design_step(self, task_id: str, spec_markdown: str) -> ValidationResult:
        """
        Step 1: DesignBot drafts product specification.
        Saves spec.md and validates acceptance criteria.
        """
        self.manager.log_event(
            task_id=task_id,
            actor="DesignBot",
            event_type=EventType.SIMULATED_MESSAGE,
            content="Completed product requirements, user journey, and low-fidelity wireframes.",
        )

        self.manager.save_artifact(
            task_id=task_id,
            artifact_type=ArtifactType.SPEC,
            filename="spec.md",
            content=spec_markdown,
            created_by="DesignBot",
        )

        val = self.validator.validate_design_handoff(task_id)
        if not val.is_valid:
            self.manager.log_event(
                task_id=task_id,
                actor="Orchestrator",
                event_type=EventType.ERROR,
                content=f"Design handoff rejected: {', '.join(val.errors)}",
            )
            return val

        self.manager.update_task_status(
            task_id=task_id,
            new_status=TaskStatus.DESIGN,
            actor="DesignBot",
            new_role=AgentRole.DEVBOT,
            note="Spec approved by validator. Ready for development.",
        )
        return val

    def execute_dev_step(
        self,
        task_id: str,
        files: Dict[str, str],
        diff_summary: str,
    ) -> ValidationResult:
        """
        Step 2: DevBot writes code files and saves code diff summary.
        Verifies syntax of all written Python files before handoff.
        """
        created_paths = []
        for rel_path, file_content in files.items():
            path = Path(rel_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(file_content, encoding="utf-8")
            created_paths.append(str(path.resolve()).replace("\\", "/"))

        self.manager.log_event(
            task_id=task_id,
            actor="DevBot",
            event_type=EventType.SIMULATED_MESSAGE,
            content=f"Implemented {len(files)} source files. Architecture and unit tests verified.",
            metadata={"created_files": list(files.keys())},
        )

        self.manager.save_artifact(
            task_id=task_id,
            artifact_type=ArtifactType.CODE_DIFF,
            filename="code_diff.md",
            content=diff_summary,
            created_by="DevBot",
        )

        val = self.validator.validate_dev_handoff(task_id, code_files=created_paths)
        if not val.is_valid:
            self.manager.log_event(
                task_id=task_id,
                actor="Orchestrator",
                event_type=EventType.ERROR,
                content=f"Dev handoff rejected: {', '.join(val.errors)}",
            )
            return val

        self.manager.update_task_status(
            task_id=task_id,
            new_status=TaskStatus.DEV,
            actor="DevBot",
            new_role=AgentRole.TESTBOT,
            note="Source code syntax verified. Ready for QA test suite.",
        )
        return val

    def execute_test_step(self, task_id: str, test_command: str) -> ValidationResult:
        """
        Step 3: TestBot runs real test command on machine.
        ANTI-HALLUCINATION: Executes subprocess, checks exit code, logs TOOL_EXECUTION event.
        """
        start_time = time.time()
        proc = subprocess.run(
            test_command,
            shell=True,
            capture_output=True,
            text=True,
        )
        duration_ms = int((time.time() - start_time) * 1000)

        # Log real machine execution evidence
        self.manager.log_event(
            task_id=task_id,
            actor="TestBot",
            event_type=EventType.TOOL_EXECUTION,
            content=f"Executed QA test command `{test_command}`",
            metadata={
                "command": test_command,
                "exit_code": proc.returncode,
                "duration_ms": duration_ms,
                "stdout": proc.stdout[-1000:] if proc.stdout else "",
                "stderr": proc.stderr[-1000:] if proc.stderr else "",
            },
        )

        status_text = "PASSED" if proc.returncode == 0 else "FAILED"
        report_md = (
            f"# Test Execution Report\n\n"
            f"- **Verdict**: {status_text}\n"
            f"- **Command**: `{test_command}`\n"
            f"- **Exit Code**: {proc.returncode}\n"
            f"- **Execution Time**: {duration_ms} ms\n\n"
            f"## Standard Output\n```text\n{proc.stdout}\n```\n"
        )
        if proc.stderr:
            report_md += f"\n## Standard Error\n```text\n{proc.stderr}\n```\n"

        self.manager.save_artifact(
            task_id=task_id,
            artifact_type=ArtifactType.TEST_REPORT,
            filename="test_report.md",
            content=report_md,
            created_by="TestBot",
        )

        val = self.validator.validate_test_handoff(task_id)
        if not val.is_valid:
            self.manager.log_event(
                task_id=task_id,
                actor="Orchestrator",
                event_type=EventType.ERROR,
                content=f"Test handoff rejected: {', '.join(val.errors)}",
            )
            return val

        self.manager.update_task_status(
            task_id=task_id,
            new_status=TaskStatus.TEST,
            actor="TestBot",
            new_role=AgentRole.RELEASEBOT,
            note="Automated test suite passed with Exit Code 0. Ready for release preparation.",
        )
        return val

    def execute_release_step(self, task_id: str, version_tag: str, release_notes: str) -> ValidationResult:
        """
        Step 4: ReleaseBot packages release notes and halts at Human Gatekeeper.
        """
        self.manager.log_event(
            task_id=task_id,
            actor="ReleaseBot",
            event_type=EventType.SIMULATED_MESSAGE,
            content=f"Prepared release documentation for {version_tag}. Halting at Human Gatekeeper for authorization.",
        )

        self.manager.save_artifact(
            task_id=task_id,
            artifact_type=ArtifactType.RELEASE_NOTES,
            filename="release_notes.md",
            content=release_notes,
            created_by="ReleaseBot",
        )

        # Move to WAITING_APPROVAL
        self.manager.update_task_status(
            task_id=task_id,
            new_status=TaskStatus.WAITING_APPROVAL,
            actor="ReleaseBot",
            new_role=AgentRole.HUMAN,
            note=f"Release package {version_tag} ready. Awaiting Founder authorization.",
        )

        return self.validator.validate_release_handoff(task_id, TaskStatus.WAITING_APPROVAL)

    def founder_approve_and_release(
        self,
        task_id: str,
        approver: str = "Founder",
        comment: str = "Approved for public release.",
    ) -> ValidationResult:
        """
        Step 5: Human Founder authorizes release.
        Logs HUMAN_APPROVAL event and transitions to RELEASED.
        """
        self.manager.log_event(
            task_id=task_id,
            actor=approver,
            event_type=EventType.HUMAN_APPROVAL,
            content=f"Consequential action authorized by {approver}: {comment}",
            metadata={"approver": approver},
        )

        val = self.validator.validate_release_handoff(task_id, TaskStatus.RELEASED)
        if not val.is_valid:
            return val

        self.manager.update_task_status(
            task_id=task_id,
            new_status=TaskStatus.RELEASED,
            actor=approver,
            new_role=AgentRole.HUMAN,
            note=comment,
        )
        return val
