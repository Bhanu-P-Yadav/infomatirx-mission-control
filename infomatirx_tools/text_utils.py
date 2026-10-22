"""
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
    cleaned = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"[-\s]+", "-", cleaned).strip("-")


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
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", text.strip())
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower().replace("-", "_")
