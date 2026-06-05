import sys
from pathlib import Path
from types import ModuleType
from typing import ClassVar

import pytest

from watch_my_escape.llm.client import (
    EmbeddedLlamaCppProvider,
    LlmConfigurationError,
    ZeroGpuLlamaCppProvider,
    create_provider,
)
from watch_my_escape.llm.config import LlamaCppConfig, LlmProviderName
from watch_my_escape.llm.models import ChatMessage, InferenceRequest, ToolSpec


def _config(provider: LlmProviderName, model_path: str = "model.gguf") -> LlamaCppConfig:
    return LlamaCppConfig(
        provider=provider,
        model_path=None if model_path == "" else Path(model_path),
        model_repo_id=None,
        model_filename=None,
        chat_format=None,
        context_tokens=4096,
        max_tokens=256,
        temperature=None,
        top_p=None,
        top_k=None,
        gpu_layers=-1,
        zerogpu_duration=60,
    )


def test_create_provider_returns_embedded_provider_for_llama_cpp():
    provider = create_provider(_config(LlmProviderName.LLAMA_CPP))

    assert isinstance(provider, EmbeddedLlamaCppProvider)


def test_create_provider_returns_zerogpu_provider_when_configured(monkeypatch):
    def gpu_decorator(duration: int):
        assert duration == 60
        return lambda function: function

    fake_spaces = ModuleType("spaces")
    fake_spaces.__dict__["GPU"] = gpu_decorator
    monkeypatch.setitem(sys.modules, "spaces", fake_spaces)

    provider = create_provider(_config(LlmProviderName.ZEROGPU))

    assert isinstance(provider, ZeroGpuLlamaCppProvider)


def test_create_provider_rejects_unresolved_auto_provider():
    with pytest.raises(LlmConfigurationError, match="auto-selection"):
        create_provider(_config(LlmProviderName.AUTO))


def test_embedded_provider_does_not_import_llama_cpp_until_completion(monkeypatch):
    monkeypatch.setitem(sys.modules, "llama_cpp", None)

    provider = create_provider(_config(LlmProviderName.LLAMA_CPP))

    assert isinstance(provider, EmbeddedLlamaCppProvider)


def test_embedded_provider_parses_tool_call(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("stub", encoding="utf-8")

    class FakeLlama:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def create_chat_completion(self, **kwargs):
            self.completion_kwargs = kwargs
            return {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "move_north",
                                        "arguments": '{"emotion":"neutral"}',
                                    }
                                }
                            ],
                        }
                    }
                ]
            }

    fake_module = ModuleType("llama_cpp")
    fake_module.__dict__["Llama"] = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    provider = EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))
    response = provider.complete(
        InferenceRequest(
            messages=(ChatMessage(role="user", content="Move."),),
            tools=(
                ToolSpec(
                    name="move_north",
                    description="Move north.",
                    parameters={"type": "object", "properties": {"emotion": {"type": "string"}}},
                ),
            ),
        )
    )

    assert response.tool_call is not None
    assert response.tool_call.name == "move_north"
    assert response.tool_call.arguments == {"emotion": "neutral"}


def test_embedded_provider_uses_reasoning_fallback_sampling(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("not gguf", encoding="utf-8")

    class FakeLlama:
        completion_kwargs: ClassVar[dict[str, object]] = {}

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def create_chat_completion(self, **kwargs):
            type(self).completion_kwargs = kwargs
            return {"choices": [{"message": {"content": "done"}}]}

    fake_module = ModuleType("llama_cpp")
    fake_module.__dict__["Llama"] = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    provider = EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))
    provider.complete(InferenceRequest(messages=(ChatMessage(role="user", content="Think."),)))

    assert FakeLlama.completion_kwargs["temperature"] == 1.0
    assert FakeLlama.completion_kwargs["top_p"] == 0.95
    assert FakeLlama.completion_kwargs["top_k"] == 64
    assert FakeLlama.completion_kwargs["max_tokens"] == 256
