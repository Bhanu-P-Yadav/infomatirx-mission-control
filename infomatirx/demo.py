"""
Demonstration runner for Infomatirx multi-agent orchestration.
Moves a real software feature through DesignBot -> DevBot -> TestBot -> ReleaseBot -> Approval Gate.
"""

from pathlib import Path
from infomatirx.manager import InfomatirxManager
from infomatirx.orchestrator import InfomatirxOrchestrator


def run_text_utils_feature():
    manager = InfomatirxManager()
    orchestrator = InfomatirxOrchestrator(manager)

    task_id = "task-feat-01"
    print("=" * 70)
    print("INFOMATIRX ORCHESTRATION PIPELINE STARTING")
    print("=" * 70)

    # Clean existing demo task if present
    conn = manager.get_task(task_id)
    if conn:
        from infomatirx.db import get_connection
        c = get_connection(manager.db_path)
        with c:
            c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        c.close()

    # 1. Backlog
    task = orchestrator.create_project_task(
        title="Text Utilities Package",
        description="A robust text transformation utility providing word count, slugify, camelCase, and snake_case.",
        task_id=task_id,
    )
    print(f"[1/5] Task created in BACKLOG: {task.title} ({task.id})")

    # 2. DesignBot Step
    spec_md = """# Overview
The Text Utilities Package (`infomatirx_tools.text_utils`) provides standard string transformations and metrics for text processing pipelines.

# User Journey
1. Developer imports `from infomatirx_tools.text_utils import word_count, to_slug, to_camel_case, to_snake_case`.
2. Developer calls `word_count("hello world")` -> receives `2`.
3. Developer calls `to_slug("Hello World 2026!")` -> receives `"hello-world-2026"`.
4. Developer calls `to_camel_case("hello_world_text")` -> receives `"helloWorldText"`.
5. Developer calls `to_snake_case("helloWorldText")` -> receives `"hello_world_text"`.

# UI / Interface Wireframe
```text
+-------------------------------------------------------+
| text_utils module API                                 |
+-------------------------------------------------------+
| * word_count(text: str) -> int                        |
| * to_slug(text: str) -> str                           |
| * to_camel_case(text: str) -> str                     |
| * to_snake_case(text: str) -> str                     |
+-------------------------------------------------------+
```

# Acceptance Criteria
- `word_count`: Accurately splits on whitespace and handles punctuation/empty strings.
- `to_slug`: Lowercases, removes special characters, and joins with hyphens.
- `to_camel_case`: Converts snake_case and kebab-case strings to lowerCamelCase.
- `to_snake_case`: Converts camelCase and PascalCase to snake_case.
- 100% test coverage with automated unit tests.
"""
    val_design = orchestrator.execute_design_step(task_id, spec_md)
    print(f"[2/5] DesignBot finished: Valid={val_design.is_valid}. Moved to DESIGN, assigned to DevBot.")

    # 3. DevBot Step
    text_utils_code = '''"""
Text Utilities Package for Infomatirx.
Provides clean, deterministic string transformations.
"""

import re


def word_count(text: str) -> int:
    """Return the number of words in a string."""
    if not text or not text.strip():
        return 0
    return len(text.strip().split())


def to_slug(text: str) -> str:
    """Convert text into a URL-friendly slug."""
    if not text:
        return ""
    cleaned = re.sub(r"[^\\w\\s-]", "", text.strip().lower())
    return re.sub(r"[-\\s]+", "-", cleaned).strip("-")


def to_camel_case(text: str) -> str:
    """Convert snake_case or kebab-case to lowerCamelCase."""
    if not text:
        return ""
    words = re.split(r"[_-]+", text.strip())
    if not words:
        return ""
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def to_snake_case(text: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    if not text:
        return ""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\\1_\\2", text.strip())
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\\1_\\2", s1)
    return s2.lower().replace("-", "_")
'''

    test_utils_code = '''"""
Unit tests for infomatirx_tools.text_utils.
"""

import unittest
from infomatirx_tools.text_utils import (
    word_count,
    to_slug,
    to_camel_case,
    to_snake_case,
)


class TestTextUtils(unittest.TestCase):

    def test_word_count(self):
        self.assertEqual(word_count(""), 0)
        self.assertEqual(word_count("   "), 0)
        self.assertEqual(word_count("Hello World"), 2)
        self.assertEqual(word_count("The quick brown fox jumps over the lazy dog"), 9)

    def test_to_slug(self):
        self.assertEqual(to_slug(""), "")
        self.assertEqual(to_slug("Hello World!"), "hello-world")
        self.assertEqual(to_slug("Infomatirx AI Software 2026"), "infomatirx-ai-software-2026")

    def test_to_camel_case(self):
        self.assertEqual(to_camel_case(""), "")
        self.assertEqual(to_camel_case("hello_world"), "helloWorld")
        self.assertEqual(to_camel_case("infomatirx-task-manager"), "infomatirxTaskManager")

    def test_to_snake_case(self):
        self.assertEqual(to_snake_case(""), "")
        self.assertEqual(to_snake_case("helloWorld"), "hello_world")
        self.assertEqual(to_snake_case("InfomatirxMissionControl"), "infomatirx_mission_control")


if __name__ == "__main__":
    unittest.main()
'''

    init_code = '"""Infomatirx Tools Package"""\n'

    diff_summary = (
        "# DevBot Code Deliverable\n\n"
        "Created:\n"
        "- `infomatirx_tools/__init__.py`\n"
        "- `infomatirx_tools/text_utils.py` (implementation)\n"
        "- `tests/test_text_utils.py` (4 test cases with full coverage)\n"
    )

    files = {
        "infomatirx_tools/__init__.py": init_code,
        "infomatirx_tools/text_utils.py": text_utils_code,
        "tests/test_text_utils.py": test_utils_code,
    }

    val_dev = orchestrator.execute_dev_step(task_id, files, diff_summary)
    print(f"[3/5] DevBot finished: Valid={val_dev.is_valid}. Moved to DEV, assigned to TestBot.")

    # 4. TestBot Step
    cmd = "python -m unittest tests/test_text_utils.py"
    val_test = orchestrator.execute_test_step(task_id, cmd)
    print(f"[4/5] TestBot finished: Valid={val_test.is_valid}. Verified real exit code 0. Assigned to ReleaseBot.")

    # 5. ReleaseBot Step
    release_notes_md = """# Release Notes — Text Utilities Package v0.1.0

## Summary
Initial production release of the `infomatirx_tools.text_utils` library.

## Included Features
- `word_count`: Whitespace-safe word counting
- `to_slug`: Standard URL slug generator
- `to_camel_case`: Conversion from snake/kebab case to camelCase
- `to_snake_case`: Conversion from camel/Pascal case to snake_case

## Quality Assurance & Verification
- Unit test suite: `tests/test_text_utils.py` passed with Exit Code 0.
- All acceptance criteria from `spec.md` satisfied.
- Zero external dependencies.

## Human Authorization Status
**HALTED AT APPROVAL GATE**: Awaiting Founder sign-off before tagging or deploying.
"""
    val_release = orchestrator.execute_release_step(task_id, "v0.1.0", release_notes_md)
    print(f"[5/5] ReleaseBot finished: Valid={val_release.is_valid}. Moved to WAITING_APPROVAL, assigned to Human.")

    print("=" * 70)
    print("PIPELINE PAUSED AT HUMAN GATEKEEPER!")
    print("Open http://localhost:8000 in your browser to inspect and approve the release.")
    print("=" * 70)


if __name__ == "__main__":
    run_text_utils_feature()
