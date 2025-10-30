"""Prompt loader utilities for Penzer.

This module reads prompt files from the configured prompts directory.
Prompt files are plain text or markdown files named like `system_prompt.md` or
`planner_prompt.txt`. Use `load_prompt("system_prompt")` to fetch text.
"""
from pathlib import Path
from typing import Optional
import config.config as cfg


def _prompt_path(name: str) -> Path:
    base = Path(cfg.PROMPT_DIR)
    # try common extensions
    for ext in (".md", ".txt", ".prompt", ""):
        p = base / (name + ext)
        if p.exists():
            return p
    # default to markdown path
    return base / (name + ".md")


def load_prompt(name: str, default: Optional[str] = None) -> str:
    """Load prompt text by name from the prompts directory.

    name: filename without extension (e.g., 'system_prompt')
    Returns: file contents as str, or `default`/empty string if missing.
    """
    p = _prompt_path(name)
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return default or ""


def list_prompts() -> list:
    """Return a list of available prompt filenames (without directory)."""
    base = Path(cfg.PROMPT_DIR)
    if not base.exists():
        return []
    return [p.name for p in base.iterdir() if p.is_file()]
