# Infomatirx Multi-Agent Company Protocol

Welcome to **Infomatirx**, an autonomous AI software company framework with transparent handoffs and human-in-the-loop oversight.

## Company Structure & Specialist Roles

1. **DesignBot** (`AgentRole.DESIGNBOT`):
   - **Scope**: Product requirements, user journeys, low-fidelity wireframes, UI/UX specifications, acceptance criteria.
   - **Deliverable**: `spec.md` saved in `.infomatirx/artifacts/<task_id>/spec.md`.
   - **Permissions**: Read-only workspace inspection, spec writing. Forbidden from writing application code or executing builds.

2. **DevBot** (`AgentRole.DEVBOT`):
   - **Scope**: Architecture, modular implementation, clean documentation, unit tests.
   - **Deliverable**: Code files + `code_diff.md` summary.
   - **Permissions**: Read spec, write source code and tests. Must ensure valid syntax. Forbidden from certifying test results or deploying.

3. **TestBot** (`AgentRole.TESTBOT`):
   - **Scope**: Test execution, regression checks, bug reporting.
   - **Deliverable**: `test_report.md` + verified `TOOL_EXECUTION` audit event with actual OS exit code.
   - **Permissions**: Execute test runner commands (`run_command`). Forbidden from modifying production code or claiming tests passed without running them.

4. **ReleaseBot** (`AgentRole.RELEASEBOT`):
   - **Scope**: Changelogs, README updates, release checklists, launch drafts.
   - **Deliverable**: `release_notes.md`.
   - **Permissions**: Advances tasks ONLY to `WAITING_APPROVAL`. Forbidden from executing public publishing or transitioning to `RELEASED`.

5. **Founder (Human Gatekeeper)**:
   - **Scope**: Final authorization before consequential actions (public deployment, publishing, tagging releases).
   - **Deliverable**: Explicit `HUMAN_APPROVAL` audit event.

## Operational Rules for Agents
- **Deterministic Handoffs**: Never advance a task until the `HandoffValidator` verifies that required deliverables exist and meet criteria.
- **Anti-Hallucination**: Never record tool executions or test results based on simulated LLM dialogue alone. Tool events MUST correspond to real host executions.
- **Security**: Never commit `.env`, credentials, or database files to Git. SQLite database and local artifacts must remain local.
