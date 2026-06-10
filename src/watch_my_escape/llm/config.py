"""Environment-driven llama.cpp configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from enum import StrEnum
from importlib import import_module
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
LANGFUSE_REQUIRED_KEYS: Final = ("LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_BASE_URL")


@dataclass(frozen=True, slots=True)
class ModelPreset:
    """Known Hub GGUF model source and presentation metadata."""

    display_name: str
    company: str
    brand_color: str
    agent_icon: str
    parameter_size_b: float
    repo_id: str
    filename: str
    active_parameter_size_b: float | None = None


@dataclass(frozen=True, slots=True)
class LangfuseConfig:
    """Resolved Langfuse tracing configuration."""

    tracing_enabled: bool = False


MODEL_PRESETS: Final[Mapping[str, ModelPreset]] = MappingProxyType(
    {
        "gemma-4-12b-it": ModelPreset(
            display_name="Gemma 4 12B",
            company="Google",
            brand_color="#4285F4",
            agent_icon="🤓",
            parameter_size_b=12,
            repo_id="ggml-org/gemma-4-12B-it-GGUF",
            filename="gemma-4-12B-it-Q4_K_M.gguf",
        ),
        "nvidia-nemotron-3-nano-4b": ModelPreset(
            display_name="Nemotron 3 Nano 4B",
            company="NVIDIA",
            brand_color="#76B900",
            agent_icon="🤠",
            parameter_size_b=4,
            repo_id="nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF",
            filename="NVIDIA-Nemotron3-Nano-4B-Q4_K_M.gguf",
        ),
        "minicpm5-1b": ModelPreset(
            display_name="MiniCPM5 1B",
            company="OpenBMB",
            brand_color="#2563EB",
            agent_icon="🫡",
            parameter_size_b=1,
            repo_id="openbmb/MiniCPM5-1B-GGUF",
            filename="MiniCPM5-1B-Q4_K_M.gguf",
        ),
        "tiny-aya-global": ModelPreset(
            display_name="Tiny Aya",
            company="Cohere",
            brand_color="#639C87",
            agent_icon="🥰",
            parameter_size_b=3.35,
            repo_id="CohereLabs/tiny-aya-global-GGUF",
            filename="tiny-aya-global-q4_k_m.gguf",
        ),
        "mellum2-12b-a2.5b-thinking": ModelPreset(
            display_name="Mellum2 12B",
            company="JetBrains",
            brand_color="#A855F7",
            agent_icon="🤔",
            parameter_size_b=12,
            repo_id="JetBrains/Mellum2-12B-A2.5B-Thinking-GGUF-Q4_K_M",
            filename="Mellum2-12B-A2.5B-Thinking-Q4_K_M.gguf",
            active_parameter_size_b=2.5,
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
    langfuse: LangfuseConfig = field(default_factory=LangfuseConfig)

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
    if environ is None:
        load_dotenv_if_available()
    env = dict(os.environ) if environ is None else environ
    requested_provider = LlmProviderName(env.get("WME_LLM_PROVIDER", LlmProviderName.AUTO))
    model_path = env.get("WME_MODEL_PATH")
    model_repo_id = env.get("WME_MODEL_REPO_ID")
    model_filename = env.get("WME_MODEL_FILENAME")
    return LlamaCppConfig(
        provider=resolve_provider(requested_provider, env),
        model_preset=None,
        model_path=Path(model_path).expanduser() if model_path else None,
        model_repo_id=model_repo_id,
        model_filename=model_filename,
        chat_format=env.get("WME_CHAT_FORMAT"),
        context_tokens=int(env.get("WME_CONTEXT_TOKENS", DEFAULT_CONTEXT_TOKENS)),
        max_tokens=int(env.get("WME_MAX_TOKENS", DEFAULT_MAX_TOKENS)),
        temperature=_optional_float(env, "WME_TEMPERATURE"),
        top_p=_optional_float(env, "WME_TOP_P"),
        top_k=_optional_int(env, "WME_TOP_K"),
        gpu_layers=int(env.get("WME_GPU_LAYERS", DEFAULT_GPU_LAYERS)),
        zerogpu_duration=int(env.get("WME_ZEROGPU_DURATION", DEFAULT_ZEROGPU_DURATION)),
        flash_attn=_optional_bool(env, "WME_FLASH_ATTN"),
        langfuse=_load_langfuse_config(env),
    )


def config_for_model_preset(preset_name: str, base_config: LlamaCppConfig | None = None) -> LlamaCppConfig:
    """Return a runtime config that uses one explicit model preset."""
    try:
        preset = MODEL_PRESETS[preset_name]
    except KeyError as exc:
        available = ", ".join(MODEL_PRESETS)
        msg = f"Unknown model preset {preset_name!r}. Available presets: {available}."
        raise ModelPresetError(msg) from exc

    config = load_config() if base_config is None else base_config
    return replace(
        config,
        model_preset=preset_name,
        model_path=None,
        model_repo_id=preset.repo_id,
        model_filename=preset.filename,
    )


def load_dotenv_if_available() -> None:
    """Load local .env variables when python-dotenv is installed."""
    try:
        dotenv_module = import_module("dotenv")
    except ImportError:
        return

    load_dotenv = getattr(dotenv_module, "load_dotenv", None)
    if callable(load_dotenv):
        load_dotenv()


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


def _load_langfuse_config(env: dict[str, str]) -> LangfuseConfig:
    requested = _optional_bool(env, "LANGFUSE_TRACING_ENABLED")
    tracing_enabled = requested is True and all(_has_value(env, key) for key in LANGFUSE_REQUIRED_KEYS)
    return LangfuseConfig(tracing_enabled=tracing_enabled)


def _has_value(env: dict[str, str], key: str) -> bool:
    return bool(env.get(key, "").strip())
