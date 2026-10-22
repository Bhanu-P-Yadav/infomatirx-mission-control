"""
Command-Line Interface (CLI) for Infomatirx Mission Control Core Engine.
Allows managing tasks, reviewing events, and inspecting deliverables directly from the terminal,
or launching the Mission Control local Web UI.
"""

import argparse
import json
import sys
from infomatirx.manager import InfomatirxManager
from infomatirx.models import TaskStatus, AgentRole, EventType
from infomatirx.validator import HandoffValidator
from infomatirx.agents.contracts import get_agent_contract
from infomatirx.server import run_server


def format_table(rows, headers):
    """Simple terminal table formatter with standard library."""
    if not rows:
        return "No records found."
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    header_str = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator = "-+-".join("-" * widths[i] for i in range(len(headers)))
    data_strs = [
        " | ".join(str(val).ljust(widths[i]) for i, val in enumerate(row))
        for row in rows
    ]
    return f"{header_str}\n{separator}\n" + "\n".join(data_strs)


def main():
    parser = argparse.ArgumentParser(
        prog="infomatirx",
        description="Infomatirx AI Software Company Mission Control CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: init
    subparsers.add_parser("init", help="Initialize local SQLite database and directory structure")

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Launch the local Mission Control Web UI dashboard")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

    # Command: task-create
    create_parser = subparsers.add_parser("task-create", help="Create a new task")
    create_parser.add_argument("--title", required=True, help="Task title")
    create_parser.add_argument("--desc", required=True, help="Task description")
    create_parser.add_argument("--id", required=False, default=None, help="Optional custom task ID")

    # Command: task-list
    list_parser = subparsers.add_parser("task-list", help="List tasks")
    list_parser.add_argument("--status", required=False, choices=[s.value for s in TaskStatus], help="Filter by status")

    # Command: task-show
    show_parser = subparsers.add_parser("task-show", help="Show full details and timeline of a task")
    show_parser.add_argument("task_id", help="The task ID")

    # Command: task-status
    status_parser = subparsers.add_parser("task-status", help="Update task status")
    status_parser.add_argument("task_id", help="The task ID")
    status_parser.add_argument("status", choices=[s.value for s in TaskStatus], help="New status")
    status_parser.add_argument("--actor", default="Founder", help="Who made this change")
    status_parser.add_argument("--note", default=None, help="Optional transition note")

    # Command: agent-contract
    contract_parser = subparsers.add_parser("agent-contract", help="Display system prompt contract for an agent")
    contract_parser.add_argument("role", choices=["DesignBot", "DevBot", "TestBot", "ReleaseBot"], help="Agent role name")

    # Command: validate-handoff
    val_parser = subparsers.add_parser("validate-handoff", help="Validate handoff quality gate for a task")
    val_parser.add_argument("task_id", help="The task ID")
    val_parser.add_argument("stage", choices=["design", "dev", "test", "release"], help="Handoff stage to validate")
    val_parser.add_argument("--files", nargs="*", default=None, help="Optional code files to check (for dev stage)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    manager = InfomatirxManager()
    validator = HandoffValidator(manager)

    if args.command == "serve":
        run_server(host=args.host, port=args.port)

    elif args.command == "init":
        print("Infomatirx workspace initialized successfully.")
        print("Database ready at: .infomatirx/infomatirx.db")
        print("Artifacts directory ready at: .infomatirx/artifacts/")

    elif args.command == "agent-contract":
        try:
            role = AgentRole(args.role)
            content = get_agent_contract(role)
            print(content)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "task-create":
        task = manager.create_task(title=args.title, description=args.desc, task_id=args.id)
        print("Task created successfully!")
        print(f"ID:       {task.id}")
        print(f"Title:    {task.title}")
        print(f"Status:   {task.status.value}")
        print(f"Assigned: {task.assigned_role.value}")

    elif args.command == "task-list":
        filter_status = TaskStatus(args.status) if args.status else None
        tasks = manager.list_tasks(status=filter_status)
        headers = ["Task ID", "Title", "Status", "Assigned Role", "Updated At"]
        rows = [
            [t.id, t.title[:30], t.status.value, t.assigned_role.value, t.updated_at[:19]]
            for t in tasks
        ]
        print(format_table(rows, headers))

    elif args.command == "task-show":
        try:
            summary = manager.get_full_task_summary(args.task_id)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        t = summary["task"]
        print("=" * 70)
        print(f"TASK: {t['title']} (ID: {t['id']})")
        print(f"Status: {t['status']} | Assigned: {t['assigned_role']}")
        print(f"Description: {t['description']}")
        print("=" * 70)

        print("\n--- TIMELINE & AUDIT TRAIL ---")
        for ev in summary["events"]:
            type_badge = f"[{ev['event_type']}]"
            actor = f"<{ev['actor']}>"
            time_str = ev["timestamp"][:19]
            print(f"{time_str} {type_badge:<20} {actor:<15} {ev['content']}")
            if ev["metadata"]:
                print(f"    Metadata: {json.dumps(ev['metadata'])}")

        print("\n--- ARTIFACTS ON DISK ---")
        if not summary["artifacts"]:
            print("No artifacts saved yet.")
        for art in summary["artifacts"]:
            print(f"* [{art['artifact_type']}] {art['filename']} (created by {art['created_by']})")
            print(f"  Path: {art['file_path']}")
        print("=" * 70)

    elif args.command == "task-status":
        try:
            updated = manager.update_task_status(
                task_id=args.task_id,
                new_status=TaskStatus(args.status),
                actor=args.actor,
                note=args.note,
            )
            print(f"Task '{updated.id}' status updated to {updated.status.value}.")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "validate-handoff":
        if args.stage == "design":
            res = validator.validate_design_handoff(args.task_id)
        elif args.stage == "dev":
            res = validator.validate_dev_handoff(args.task_id, code_files=args.files)
        elif args.stage == "test":
            res = validator.validate_test_handoff(args.task_id)
        elif args.stage == "release":
            res = validator.validate_release_handoff(args.task_id, target_status=TaskStatus.RELEASED)

        print(f"Handoff Stage: {res.stage}")
        print(f"Status:        {'PASS [OK]' if res.is_valid else 'FAIL [BLOCKED]'}")
        if res.errors:
            print("\nBlocking Errors:")
            for err in res.errors:
                print(f"  [ERROR] {err}")
        if res.warnings:
            print("\nWarnings:")
            for w in res.warnings:
                print(f"  [WARN]  {w}")
        if not res.is_valid:
            sys.exit(1)


if __name__ == "__main__":
    main()
