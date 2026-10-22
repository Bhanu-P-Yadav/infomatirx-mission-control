"""
Specialist agent contract definitions and prompt loaders.
"""

from pathlib import Path
from infomatirx.models import AgentRole

PROMPTS_DIR = Path(__file__).parent / "prompts"


def get_agent_contract(role: AgentRole) -> str:
    """Retrieve the markdown contract and prompt instructions for a given role."""
    role_file_map = {
        AgentRole.DESIGNBOT: "designbot.md",
        AgentRole.DEVBOT: "devbot.md",
        AgentRole.TESTBOT: "testbot.md",
        AgentRole.RELEASEBOT: "releasebot.md",
    }

    filename = role_file_map.get(role)
    if not filename:
        raise ValueError(f"No prompt contract defined for role '{role}'.")

    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Contract file not found at {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")
