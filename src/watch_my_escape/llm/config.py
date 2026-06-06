"""Environment-driven llama.cpp configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

DEFAULT_CONTEXT_TOKENS: Final = 8192
DEFAULT_MAX_TOKENS: Final = 256
DEFAULT_TEMPERATURE: Final = 1.0
DEFAULT_TOP_P: Final = 0.95
DEFAULT_TOP_K: Final = 64
DEFAULT_GPU_LAYERS: Final = -1
DEFAULT_ZEROGPU_DURATION: Final = 60
BOOLEAN_TRUE_VALUES: Final = frozenset({"1", "true", "yes", "on"})
BOOLEAN_FALSE_VALUES: Final = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True, slots=True)
class ModelPreset:
    """Known Hub GGUF model source."""

    repo_id: str
    filename: str


MODEL_PRESETS: Final[Mapping[str, ModelPreset]] = MappingProxyType(
    {
        "gemma-4-12b-it": ModelPreset(
            repo_id="ggml-org/gemma-4-12B-it-GGUF",
            filename="gemma-4-12B-it-Q4_K_M.gguf",
        ),
        "nvidia-nemotron-3-nano-4b": ModelPreset(
            repo_id="nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF",
            filename="NVIDIA-Nemotron3-Nano-4B-Q4_K_M.gguf",
        ),
        "minicpm-v-4.6-thinking": ModelPreset(
            repo_id="openbmb/MiniCPM-V-4.6-Thinking-gguf",
            filename="MiniCPM-V-4_6-Thinking-Q4_K_M.gguf",
        ),
        "tiny-aya-global": ModelPreset(
            repo_id="CohereLabs/tiny-aya-global-GGUF",
            filename="tiny-aya-global-q4_k_m.gguf",
        ),
        "mellum2-12b-a2.5b-thinking": ModelPreset(
            repo_id="JetBrains/Mellum2-12B-A2.5B-Thinking-GGUF-Q4_K_M",
            filename="Mellum2-12B-A2.5B-Thinking-Q4_K_M.gguf",
        ),
    }
)


class ModelPresetError(ValueError):
    """Raised when a configured model preset is unknown."""


class LlmProviderName(StrEnum):
    """Supported inference provider modes."""

    AUTO = "auto"
    LLAMA_CPP = "llama-cpp"
    ZEROGPU = "zerogpu"


@dataclass(frozen=True, slots=True)
class LlamaCppConfig:
    """Resolved llama.cpp runtime configuration."""

    provider: LlmProviderName
    model_preset: str | None
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
    flash_attn: bool | None = None

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
    model_preset_name = _resolve_model_preset_name(env.get("WME_MODEL_PRESET"))
    model_preset = MODEL_PRESETS[model_preset_name] if model_preset_name else None
    model_repo_id = env.get("WME_MODEL_REPO_ID")
    model_filename = env.get("WME_MODEL_FILENAME")
    should_use_preset_source = model_path is None and model_repo_id is None and model_filename is None and model_preset
    return LlamaCppConfig(
        provider=resolve_provider(requested_provider, env),
        model_preset=model_preset_name,
        model_path=Path(model_path).expanduser() if model_path else None,
        model_repo_id=model_preset.repo_id if should_use_preset_source else model_repo_id,
        model_filename=model_preset.filename if should_use_preset_source else model_filename,
        chat_format=env.get("WME_CHAT_FORMAT"),
        context_tokens=int(env.get("WME_CONTEXT_TOKENS", DEFAULT_CONTEXT_TOKENS)),
        max_tokens=int(env.get("WME_MAX_TOKENS", DEFAULT_MAX_TOKENS)),
        temperature=_optional_float(env, "WME_TEMPERATURE"),
        top_p=_optional_float(env, "WME_TOP_P"),
        top_k=_optional_int(env, "WME_TOP_K"),
        gpu_layers=int(env.get("WME_GPU_LAYERS", DEFAULT_GPU_LAYERS)),
        zerogpu_duration=int(env.get("WME_ZEROGPU_DURATION", DEFAULT_ZEROGPU_DURATION)),
        flash_attn=_optional_bool(env, "WME_FLASH_ATTN"),
    )


def _optional_float(env: dict[str, str], key: str) -> float | None:
    value = env.get(key)
    return float(value) if value is not None else None


def _optional_int(env: dict[str, str], key: str) -> int | None:
    value = env.get(key)
    return int(value) if value is not None else None


def _optional_bool(env: dict[str, str], key: str) -> bool | None:
    value = env.get(key)
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized in BOOLEAN_TRUE_VALUES:
        return True
    if normalized in BOOLEAN_FALSE_VALUES:
        return False

    msg = f"{key} must be one of: 1, 0, true, false, yes, no, on, off."
    raise ValueError(msg)


def _resolve_model_preset_name(raw_name: str | None) -> str | None:
    if raw_name is None:
        return None
    name = raw_name.strip().lower()
    if name in MODEL_PRESETS:
        return name
    available = ", ".join(MODEL_PRESETS)
    msg = f"Unknown WME_MODEL_PRESET {raw_name!r}. Available presets: {available}."
    raise ModelPresetError(msg)
