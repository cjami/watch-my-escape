from pathlib import Path

import pytest

from watch_my_escape.llm.config import (
    MODEL_PRESETS,
    LangfuseConfig,
    LlamaCppConfig,
    LlmProviderName,
    config_for_model_preset,
    is_huggingface_space,
    load_config,
    resolve_provider,
)


def test_huggingface_space_detection_uses_space_environment():
    assert is_huggingface_space({"SPACE_ID": "user/watch-my-escape"})
    assert is_huggingface_space({"SPACE_HOST": "example.hf.space"})
    assert not is_huggingface_space({})


def test_auto_provider_selects_zerogpu_on_huggingface():
    provider = resolve_provider(LlmProviderName.AUTO, {"SPACE_ID": "user/watch-my-escape"})

    assert provider is LlmProviderName.ZEROGPU


def test_auto_provider_selects_llama_cpp_locally():
    provider = resolve_provider(LlmProviderName.AUTO, {})

    assert provider is LlmProviderName.LLAMA_CPP


def test_explicit_provider_wins_over_environment():
    provider = resolve_provider(LlmProviderName.LLAMA_CPP, {"SPACE_ID": "user/watch-my-escape"})

    assert provider is LlmProviderName.LLAMA_CPP


def test_load_config_reads_model_path_and_generation_settings():
    config = load_config(
        {
            "WME_LLM_PROVIDER": "llama-cpp",
            "WME_MODEL_PATH": "~/models/escape.gguf",
            "WME_CONTEXT_TOKENS": "8192",
            "WME_MAX_TOKENS": "128",
            "WME_TEMPERATURE": "0.1",
            "WME_TOP_P": "0.8",
            "WME_TOP_K": "20",
            "WME_GPU_LAYERS": "42",
            "WME_ZEROGPU_DURATION": "90",
            "WME_FLASH_ATTN": "true",
        }
    )

    assert config == LlamaCppConfig(
        provider=LlmProviderName.LLAMA_CPP,
        model_preset=None,
        model_path=Path("~/models/escape.gguf").expanduser(),
        model_repo_id=None,
        model_filename=None,
        chat_format=None,
        context_tokens=8192,
        max_tokens=128,
        temperature=0.1,
        top_p=0.8,
        top_k=20,
        gpu_layers=42,
        zerogpu_duration=90,
        flash_attn=True,
        langfuse=LangfuseConfig(),
    )


def test_load_config_rejects_invalid_flash_attention_value():
    with pytest.raises(ValueError, match="WME_FLASH_ATTN"):
        load_config({"WME_FLASH_ATTN": "sometimes"})


def test_load_config_disables_langfuse_when_tracing_env_is_missing():
    config = load_config(
        {
            "LANGFUSE_SECRET_KEY": "secret",
            "LANGFUSE_PUBLIC_KEY": "public",
            "LANGFUSE_BASE_URL": "https://langfuse.example",
        }
    )

    assert not config.langfuse.tracing_enabled


def test_load_config_disables_langfuse_when_credentials_are_incomplete():
    config = load_config(
        {
            "LANGFUSE_TRACING_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "public",
            "LANGFUSE_BASE_URL": "https://langfuse.example",
        }
    )

    assert not config.langfuse.tracing_enabled


def test_load_config_enables_langfuse_when_requested_and_complete():
    config = load_config(
        {
            "LANGFUSE_TRACING_ENABLED": "true",
            "LANGFUSE_SECRET_KEY": "secret",
            "LANGFUSE_PUBLIC_KEY": "public",
            "LANGFUSE_BASE_URL": "https://langfuse.example",
        }
    )

    assert config.langfuse.tracing_enabled


def test_load_config_rejects_invalid_langfuse_tracing_value():
    with pytest.raises(ValueError, match="LANGFUSE_TRACING_ENABLED"):
        load_config({"LANGFUSE_TRACING_ENABLED": "sometimes"})


def test_explicit_model_source_is_read_from_environment():
    config = load_config(
        {
            "WME_MODEL_REPO_ID": "custom/repo",
            "WME_MODEL_FILENAME": "custom.gguf",
        }
    )

    assert config.model_preset is None
    assert config.model_repo_id == "custom/repo"
    assert config.model_filename == "custom.gguf"


def test_config_for_model_preset_resolves_preset_to_hub_source():
    preset_name, preset = next(iter(MODEL_PRESETS.items()))
    base_config = load_config({"WME_MODEL_PATH": "~/models/custom.gguf"})

    config = config_for_model_preset(preset_name, base_config)

    assert config.model_preset == preset_name
    assert config.model_path is None
    assert config.model_repo_id == preset.repo_id
    assert config.model_filename == preset.filename
