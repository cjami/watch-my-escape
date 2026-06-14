"""Environment diagnostics for local and Space LLM setup."""

from __future__ import annotations

import importlib.util
import platform
import sys
from typing import TYPE_CHECKING

from watch_my_escape.llm.config import is_huggingface_space, load_config

if TYPE_CHECKING:
    from collections.abc import Sequence


def _installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def build_report() -> list[str]:
    """Build a human-readable diagnostic report."""
    config = load_config()
    lines = [
        "Watch My Escape LLM doctor",
        f"Python: {sys.version.split()[0]} ({platform.platform()})",
        f"Hugging Face Space: {'yes' if is_huggingface_space() else 'no'}",
        f"Provider: {config.provider}",
        f"llama_cpp installed: {'yes' if _installed('llama_cpp') else 'no'}",
        f"spaces installed: {'yes' if _installed('spaces') else 'no'}",
        f"torch installed: {'yes' if _installed('torch') else 'no'}",
        f"Model path: {config.model_path or '(not set)'}",
        f"Model repo: {config.model_repo_id or '(not set)'}",
        f"Model filename: {config.model_filename or '(not set)'}",
        f"GPU layers: {config.gpu_layers}",
        f"Flash Attention: {_format_optional_bool(value=config.flash_attn)}",
    ]
    if not _installed("llama_cpp"):
        lines.append("Suggested fix: uv run watch-my-escape --setup-only")
    if not config.has_model_source:
        lines.append("Suggested fix: set WME_MODEL_PATH or WME_MODEL_REPO_ID plus WME_MODEL_FILENAME.")
    return lines


def _format_optional_bool(*, value: bool | None) -> str:
    if value is None:
        return "auto"
    return "yes" if value else "no"


def main(argv: Sequence[str] | None = None) -> None:
    """Print the diagnostics report."""
    _ = argv
    for line in build_report():
        print(line)


if __name__ == "__main__":
    main()
