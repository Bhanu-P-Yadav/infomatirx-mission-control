"""
Handoff Validator Engine for Infomatirx.
Enforces deterministic quality gates and prevents hallucinated task transitions.
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from infomatirx.manager import InfomatirxManager
from infomatirx.models import (
    TaskStatus,
    EventType,
    ArtifactType,
)


@dataclass
class ValidationResult:
    """Outcome of a handoff validation check."""
    is_valid: bool
    stage: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "stage": self.stage,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details,
        }


class HandoffValidator:
    """Validates deliverables and audit trails before allowing pipeline transitions."""

    def __init__(self, manager: InfomatirxManager):
        self.manager = manager

    def validate_design_handoff(self, task_id: str) -> ValidationResult:
        """
        Validates DesignBot's deliverable (spec.md).
        Requires file presence, non-empty content, and key sections:
        Overview, User Journey, and Acceptance Criteria.
        """
        errors = []
        artifacts = self.manager.get_task_artifacts(task_id)
        spec_artifact = next((a for a in artifacts if a.artifact_type == ArtifactType.SPEC or a.filename == "spec.md"), None)

        if not spec_artifact:
            return ValidationResult(
                is_valid=False,
                stage="DESIGN -> DEV",
                errors=["No design specification (spec.md) found for this task."],
            )

        spec_file = Path(spec_artifact.file_path)
        if not spec_file.exists():
            return ValidationResult(
                is_valid=False,
                stage="DESIGN -> DEV",
                errors=[f"Spec file registered in DB but missing on disk: {spec_artifact.file_path}"],
            )

        content = spec_file.read_text(encoding="utf-8")
        if len(content.strip()) < 50:
            errors.append("Spec content is too short or empty (< 50 characters).")

        required_sections = ["Overview", "User Journey", "Acceptance Criteria"]
        for section in required_sections:
            if section.lower() not in content.lower():
                errors.append(f"Spec is missing required section: '{section}'.")

        return ValidationResult(
            is_valid=len(errors) == 0,
            stage="DESIGN -> DEV",
            errors=errors,
            details={"spec_path": spec_artifact.file_path, "bytes": len(content)},
        )

    def validate_dev_handoff(self, task_id: str, code_files: Optional[List[str]] = None) -> ValidationResult:
        """
        Validates DevBot's code deliverable.
        Verifies files exist, are non-empty, and all Python code compiles with valid syntax.
        """
        errors = []
        files_to_check = code_files or []

        if not files_to_check:
            # Check if any artifacts or events mention code files
            artifacts = self.manager.get_task_artifacts(task_id)
            code_diff_art = next((a for a in artifacts if a.artifact_type == ArtifactType.CODE_DIFF), None)
            if not code_diff_art:
                errors.append("No code files or CODE_DIFF artifact provided for DevBot handoff.")

        syntax_checked = []
        for file_path_str in files_to_check:
            path = Path(file_path_str)
            if not path.exists():
                errors.append(f"Declared source code file does not exist on disk: {file_path_str}")
                continue

            if path.stat().st_size == 0:
                errors.append(f"Source code file is empty (0 bytes): {file_path_str}")
                continue

            # Check Python syntax compilation
            if path.suffix == ".py":
                try:
                    code_text = path.read_text(encoding="utf-8")
                    ast.parse(code_text, filename=str(path))
                    syntax_checked.append(file_path_str)
                except SyntaxError as e:
                    errors.append(f"Syntax error in {file_path_str} at line {e.lineno}: {e.msg}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            stage="DEV -> TEST",
            errors=errors,
            details={"checked_files": files_to_check, "syntax_verified": syntax_checked},
        )

    def validate_test_handoff(self, task_id: str) -> ValidationResult:
        """
        Validates TestBot's QA signoff.
        ANTI-HALLUCINATION REQUIREMENT:
        1. A test_report.md artifact must exist.
        2. At least one real TOOL_EXECUTION event must be recorded in the task events.
        3. The tool execution event must have exit_code == 0.
        """
        errors = []
        artifacts = self.manager.get_task_artifacts(task_id)
        report_art = next((a for a in artifacts if a.artifact_type == ArtifactType.TEST_REPORT or a.filename == "test_report.md"), None)

        if not report_art:
            errors.append("Missing test deliverable (test_report.md).")
        else:
            report_file = Path(report_art.file_path)
            if not report_file.exists():
                errors.append(f"Test report registered but missing on disk: {report_art.file_path}")

        # Anti-hallucination check: Inspect actual tool executions
        events = self.manager.get_task_events(task_id)
        tool_executions = [e for e in events if e.event_type == EventType.TOOL_EXECUTION]

        if not tool_executions:
            errors.append("No verified TOOL_EXECUTION event found. TestBot cannot certify tests without running an actual test suite.")
        else:
            latest_execution = tool_executions[-1]
            meta = latest_execution.metadata or {}
            exit_code = meta.get("exit_code")

            if exit_code is None:
                errors.append("Latest TOOL_EXECUTION lacks exit_code metadata.")
            elif exit_code != 0:
                errors.append(
                    f"Test execution failed with exit code {exit_code}. "
                    f"Command was: '{meta.get('command', 'unknown')}'. Must fix bugs before release handoff."
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            stage="TEST -> RELEASE",
            errors=errors,
            details={
                "has_report": report_art is not None,
                "tool_executions_count": len(tool_executions),
                "last_exit_code": tool_executions[-1].metadata.get("exit_code") if tool_executions else None,
            },
        )

    def validate_release_handoff(self, task_id: str, target_status: TaskStatus) -> ValidationResult:
        """
        Validates ReleaseBot and Human Gatekeeper.
        CRITICAL SAFETY RULE:
        A task cannot transition to RELEASED without an explicit HUMAN_APPROVAL event!
        """
        errors = []
        artifacts = self.manager.get_task_artifacts(task_id)
        release_art = next((a for a in artifacts if a.artifact_type == ArtifactType.RELEASE_NOTES or "release" in a.filename.lower()), None)

        if not release_art:
            errors.append("No release notes or release checklist deliverable found.")

        # Human Gatekeeper Check
        if target_status == TaskStatus.RELEASED:
            events = self.manager.get_task_events(task_id)
            approval_event = next((e for e in events if e.event_type == EventType.HUMAN_APPROVAL), None)

            if not approval_event:
                errors.append(
                    "CONSEQUENTIAL ACTION BLOCKED: Cannot transition task to RELEASED without an explicit "
                    "HUMAN_APPROVAL event from the human operator."
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            stage="RELEASE -> HUMAN GATE",
            errors=errors,
            details={
                "has_release_notes": release_art is not None,
                "target_status": target_status.value,
            },
        )
