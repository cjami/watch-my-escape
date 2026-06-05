"""Environment-driven llama.cpp configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

DEFAULT_CONTEXT_TOKENS: Final = 4096
DEFAULT_MAX_TOKENS: Final = 256
DEFAULT_TEMPERATURE: Final = 1.0
DEFAULT_TOP_P: Final = 0.95
DEFAULT_TOP_K: Final = 64
DEFAULT_GPU_LAYERS: Final = -1
DEFAULT_ZEROGPU_DURATION: Final = 60


class LlmProviderName(StrEnum):
    """Supported inference provider modes."""

    AUTO = "auto"
    LLAMA_CPP = "llama-cpp"
    ZEROGPU = "zerogpu"


@dataclass(frozen=True, slots=True)
class LlamaCppConfig:
    """Resolved llama.cpp runtime configuration."""

    provider: LlmProviderName
    model_path: Path | None
    model_repo_id: str | None
    model_filename: str | None
    chat_format: str | None
    context_tokens: int
    max_tokens: int
    temperature: float | None
    top_p: float | None
    top_k: int | None
    gpu_layers: int
    zerogpu_duration: int

    @property
    def has_model_source(self) -> bool:
        """Return whether a local path or Hub model is configured."""
        return self.model_path is not None or bool(self.model_repo_id and self.model_filename)


def is_huggingface_space(environ: dict[str, str] | None = None) -> bool:
    """Return whether the process appears to be running in a Hugging Face Space."""
    env = dict(os.environ) if environ is None else environ
    return bool(env.get("SPACE_ID") or env.get("SPACE_HOST"))


def resolve_provider(provider: LlmProviderName, environ: dict[str, str] | None = None) -> LlmProviderName:
    """Resolve auto provider selection to a concrete provider."""
    if provider is not LlmProviderName.AUTO:
        return provider
    if is_huggingface_space(environ):
        return LlmProviderName.ZEROGPU
    return LlmProviderName.LLAMA_CPP


def load_config(environ: dict[str, str] | None = None) -> LlamaCppConfig:
    """Load llama.cpp settings from environment variables."""
    env = dict(os.environ) if environ is None else environ
    requested_provider = LlmProviderName(env.get("WME_LLM_PROVIDER", LlmProviderName.AUTO))
    model_path = env.get("WME_MODEL_PATH")
    return LlamaCppConfig(
        provider=resolve_provider(requested_provider, env),
        model_path=Path(model_path).expanduser() if model_path else None,
        model_repo_id=env.get("WME_MODEL_REPO_ID"),
        model_filename=env.get("WME_MODEL_FILENAME"),
        chat_format=env.get("WME_CHAT_FORMAT"),
        context_tokens=int(env.get("WME_CONTEXT_TOKENS", DEFAULT_CONTEXT_TOKENS)),
        max_tokens=int(env.get("WME_MAX_TOKENS", DEFAULT_MAX_TOKENS)),
        temperature=_optional_float(env, "WME_TEMPERATURE"),
        top_p=_optional_float(env, "WME_TOP_P"),
        top_k=_optional_int(env, "WME_TOP_K"),
        gpu_layers=int(env.get("WME_GPU_LAYERS", DEFAULT_GPU_LAYERS)),
        zerogpu_duration=int(env.get("WME_ZEROGPU_DURATION", DEFAULT_ZEROGPU_DURATION)),
    )


def _optional_float(env: dict[str, str], key: str) -> float | None:
    value = env.get(key)
    return float(value) if value is not None else None


def _optional_int(env: dict[str, str], key: str) -> int | None:
    value = env.get(key)
    return int(value) if value is not None else None
