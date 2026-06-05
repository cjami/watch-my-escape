from pathlib import Path

from watch_my_escape.llm.config import (
    LlamaCppConfig,
    LlmProviderName,
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
