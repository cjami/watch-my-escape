from pathlib import Path

import pytest

from watch_my_escape.llm.config import (
    MODEL_PRESETS,
    LlamaCppConfig,
    LlmProviderName,
    ModelPresetError,
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
    )


def test_model_presets_use_q4_k_m_filenames_where_available():
    assert MODEL_PRESETS["gemma-4-12b-it"].filename == "gemma-4-12B-it-Q4_K_M.gguf"
    assert MODEL_PRESETS["nvidia-nemotron-3-nano-4b"].filename == "NVIDIA-Nemotron3-Nano-4B-Q4_K_M.gguf"
    assert MODEL_PRESETS["minicpm5-1b"].filename == "MiniCPM5-1B-Q4_K_M.gguf"
    assert MODEL_PRESETS["tiny-aya-global"].filename == "tiny-aya-global-q4_k_m.gguf"
    assert MODEL_PRESETS["mellum2-12b-a2.5b-thinking"].filename == "Mellum2-12B-A2.5B-Thinking-Q4_K_M.gguf"


def test_load_config_resolves_model_preset_to_hub_source():
    config = load_config({"WME_MODEL_PRESET": "minicpm5-1b"})

    assert config.model_preset == "minicpm5-1b"
    assert config.model_repo_id == "openbmb/MiniCPM5-1B-GGUF"
    assert config.model_filename == "MiniCPM5-1B-Q4_K_M.gguf"


def test_load_config_resolves_mellum_preset_to_official_jetbrains_hub_source():
    config = load_config({"WME_MODEL_PRESET": "mellum2-12b-a2.5b-thinking"})

    assert config.model_preset == "mellum2-12b-a2.5b-thinking"
    assert config.model_repo_id == "JetBrains/Mellum2-12B-A2.5B-Thinking-GGUF-Q4_K_M"
    assert config.model_filename == "Mellum2-12B-A2.5B-Thinking-Q4_K_M.gguf"


def test_explicit_model_source_wins_over_model_preset():
    config = load_config(
        {
            "WME_MODEL_PRESET": "gemma-4-12b-it",
            "WME_MODEL_REPO_ID": "custom/repo",
            "WME_MODEL_FILENAME": "custom.gguf",
        }
    )

    assert config.model_preset == "gemma-4-12b-it"
    assert config.model_repo_id == "custom/repo"
    assert config.model_filename == "custom.gguf"


def test_unknown_model_preset_lists_available_options():
    with pytest.raises(ModelPresetError, match="Available presets"):
        load_config({"WME_MODEL_PRESET": "nope"})
