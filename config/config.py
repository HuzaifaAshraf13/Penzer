"""Minimal configuration for Penzer orchestrator.

This file provides defaults expected by `Agent/main.py` and other subsystems.
Update values or override via environment variables as needed.
"""
from pathlib import Path

SELECTED_MODEL = "gemini-2.0"
API_KEYS = {}
LLM_RETRY_MAX = 3
RATE_LIMITS = {}
PROMPT_DIR = str(Path("prompts").resolve())
FAISS_INDEX_PATH = str(Path("faiss_index").resolve())

# Behavior toggles
AUTO_VERIFY = True  # if True, simple verification stubs auto-pass
