import importlib
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import ClassVar

import pytest
from pydantic import BaseModel

from watch_my_escape.llm import client as llm_client
from watch_my_escape.llm.client import (
    EmbeddedLlamaCppProvider,
    LlmConfigurationError,
    ZeroGpuLlamaCppProvider,
    create_provider,
)
from watch_my_escape.llm.config import DEFAULT_SEED, LlamaCppConfig, LlmProviderName
from watch_my_escape.llm.models import ChatMessage, InferenceRequest, StructuredOutputSpec, ToolSpec


class StructuredProbe(BaseModel):
    """Simple structured output model for provider tests."""

    value: str


def _config(provider: LlmProviderName, model_path: str = "model.gguf") -> LlamaCppConfig:
    return LlamaCppConfig(
        provider=provider,
        model_preset=None,
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


def test_zerogpu_provider_imports_torch_before_llama_cpp(monkeypatch, tmp_path):
    def gpu_decorator(duration: int):
        assert duration == 60
        return lambda function: function

    class FakeLlama:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def create_chat_completion(self, **_kwargs):
            return {"choices": [{"message": {"content": "ok"}}]}

    fake_spaces = ModuleType("spaces")
    fake_spaces.__dict__["GPU"] = gpu_decorator
    fake_torch = ModuleType("torch")
    fake_llama_cpp = ModuleType("llama_cpp")
    fake_llama_cpp.__dict__["Llama"] = FakeLlama
    monkeypatch.setitem(sys.modules, "spaces", fake_spaces)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_llama_cpp)

    seen_imports = []
    real_import_module = importlib.import_module

    def tracking_import_module(name: str):
        if name in {"torch", "llama_cpp"}:
            seen_imports.append(name)
        return real_import_module(name)

    monkeypatch.setattr(llm_client, "import_module", tracking_import_module)
    model_path = tmp_path / "model.gguf"
    model_path.write_text("not gguf", encoding="utf-8")

    provider = ZeroGpuLlamaCppProvider(_config(LlmProviderName.ZEROGPU, str(model_path)))
    provider.complete(InferenceRequest(messages=(ChatMessage(role="user", content="Think."),)))

    assert seen_imports.index("torch") < seen_imports.index("llama_cpp")


def test_create_provider_rejects_unresolved_auto_provider():
    with pytest.raises(LlmConfigurationError, match="auto-selection"):
        create_provider(_config(LlmProviderName.AUTO))


def test_embedded_provider_does_not_import_llama_cpp_until_completion(monkeypatch):
    monkeypatch.setitem(sys.modules, "llama_cpp", None)

    provider = create_provider(_config(LlmProviderName.LLAMA_CPP))

    assert isinstance(provider, EmbeddedLlamaCppProvider)


def test_embedded_provider_does_not_require_torch(monkeypatch, tmp_path):
    class FakeLlama:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def create_chat_completion(self, **_kwargs):
            return {"choices": [{"message": {"content": "ok"}}]}

    fake_llama_cpp = ModuleType("llama_cpp")
    fake_llama_cpp.__dict__["Llama"] = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_llama_cpp)
    monkeypatch.setitem(sys.modules, "torch", None)
    model_path = tmp_path / "model.gguf"
    model_path.write_text("not gguf", encoding="utf-8")

    provider = EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))
    response = provider.complete(InferenceRequest(messages=(ChatMessage(role="user", content="Think."),)))

    assert response.content == "ok"


def test_embedded_provider_uses_fixed_seed_for_model_and_completion(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("not gguf", encoding="utf-8")

    class FakeLlama:
        init_kwargs: ClassVar[dict[str, object]] = {}
        completion_kwargs: ClassVar[dict[str, object]] = {}

        def __init__(self, **kwargs):
            type(self).init_kwargs = kwargs

        def create_chat_completion(self, **kwargs):
            type(self).completion_kwargs = kwargs
            return {"choices": [{"message": {"content": "ok"}}]}

    fake_llama_cpp = ModuleType("llama_cpp")
    fake_llama_cpp.__dict__["Llama"] = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_llama_cpp)

    provider = EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))
    provider.complete(InferenceRequest(messages=(ChatMessage(role="user", content="Think."),)))

    assert FakeLlama.init_kwargs["seed"] == DEFAULT_SEED == 1
    assert FakeLlama.completion_kwargs["seed"] == DEFAULT_SEED == 1


def test_embedded_provider_reports_llama_cpp_load_error(monkeypatch, tmp_path):
    real_import_module = importlib.import_module

    def raising_import_module(name: str):
        if name == "llama_cpp":
            raise RuntimeError
        return real_import_module(name)

    monkeypatch.setattr(llm_client, "import_module", raising_import_module)
    model_path = tmp_path / "model.gguf"
    model_path.write_text("not gguf", encoding="utf-8")
    provider = EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))

    with pytest.raises(LlmConfigurationError, match="llama-cpp-python could not be loaded"):
        provider.complete(InferenceRequest(messages=(ChatMessage(role="user", content="Think."),)))


def test_embedded_provider_reports_missing_huggingface_hub_download(monkeypatch):
    fake_module = ModuleType("huggingface_hub")
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_module)
    config = _config(LlmProviderName.LLAMA_CPP, "")
    config = replace(config, model_repo_id="example/model", model_filename="model.gguf")

    provider = EmbeddedLlamaCppProvider(config)

    with pytest.raises(LlmConfigurationError, match="huggingface-hub is required"):
        provider._resolve_model_path()  # noqa: SLF001


def test_embedded_provider_enables_flash_attention_when_gpu_offload_is_supported(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("stub", encoding="utf-8")

    class FakeLlama:
        init_kwargs: ClassVar[dict[str, object]] = {}

        def __init__(self, **kwargs):
            type(self).init_kwargs = kwargs

    fake_module = ModuleType("llama_cpp")
    fake_module.__dict__["Llama"] = FakeLlama
    fake_module.__dict__["llama_supports_gpu_offload"] = lambda: True
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))._load_llama()  # noqa: SLF001

    assert FakeLlama.init_kwargs["flash_attn"] is True


def test_embedded_provider_disables_auto_flash_attention_without_gpu_offload(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("stub", encoding="utf-8")

    class FakeLlama:
        init_kwargs: ClassVar[dict[str, object]] = {}

        def __init__(self, **kwargs):
            type(self).init_kwargs = kwargs

    fake_module = ModuleType("llama_cpp")
    fake_module.__dict__["Llama"] = FakeLlama
    fake_module.__dict__["llama_supports_gpu_offload"] = lambda: False
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))._load_llama()  # noqa: SLF001

    assert FakeLlama.init_kwargs["flash_attn"] is False


def test_embedded_provider_honors_explicit_flash_attention_override(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("stub", encoding="utf-8")

    class FakeLlama:
        init_kwargs: ClassVar[dict[str, object]] = {}

        def __init__(self, **kwargs):
            type(self).init_kwargs = kwargs

    fake_module = ModuleType("llama_cpp")
    fake_module.__dict__["Llama"] = FakeLlama
    fake_module.__dict__["llama_supports_gpu_offload"] = lambda: True
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    config = replace(_config(LlmProviderName.LLAMA_CPP, str(model_path)), flash_attn=False)

    EmbeddedLlamaCppProvider(config)._load_llama()  # noqa: SLF001

    assert FakeLlama.init_kwargs["flash_attn"] is False


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
                                        "name": "inspect_panel",
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
            messages=(ChatMessage(role="user", content="Inspect."),),
            tools=(
                ToolSpec(
                    name="inspect_panel",
                    description="Inspect a panel.",
                    parameters={"type": "object", "properties": {"emotion": {"type": "string"}}},
                ),
            ),
        )
    )

    assert response.tool_call is not None
    assert response.tool_call.name == "inspect_panel"
    assert response.tool_call.arguments == {"emotion": "neutral"}


def test_embedded_provider_passes_structured_output_grammar(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("stub", encoding="utf-8")

    class FakeGrammar:
        schema: ClassVar[str] = ""

        @classmethod
        def from_json_schema(cls, schema: str) -> str:
            cls.schema = schema
            return "json-grammar"

    class FakeLlama:
        completion_kwargs: ClassVar[dict[str, object]] = {}

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def create_chat_completion(self, **kwargs):
            type(self).completion_kwargs = kwargs
            return {"choices": [{"message": {"content": '{"value":"ok"}'}}]}

    fake_module = ModuleType("llama_cpp")
    fake_module.__dict__["Llama"] = FakeLlama
    fake_module.__dict__["LlamaGrammar"] = FakeGrammar
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    provider = EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))
    provider.complete(
        InferenceRequest(
            messages=(ChatMessage(role="user", content="Return JSON."),),
            structured_output=StructuredOutputSpec.from_pydantic_model(StructuredProbe),
        )
    )

    assert FakeLlama.completion_kwargs["grammar"] == "json-grammar"
    assert "response_format" not in FakeLlama.completion_kwargs
    assert '"title": "StructuredProbe"' in FakeGrammar.schema


def test_embedded_provider_passes_enable_thinking_to_compatible_chat_template(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("stub", encoding="utf-8")

    class FakeLlama:
        handler_kwargs: ClassVar[dict[str, object]] = {}

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.metadata = {"tokenizer.chat_template": "{% if enable_thinking %}<|think|>{% endif %}"}
            self.chat_handler = None
            self.chat_format = "chat_template.default"
            self._chat_handlers = {"chat_template.default": self._handler}

        def _handler(self, **kwargs):
            type(self).handler_kwargs = kwargs
            return {"choices": [{"message": {"content": "thinking"}}]}

        def create_chat_completion(self, **_kwargs):
            pytest.fail("compatible templates should receive enable_thinking through the chat handler")

    fake_module = ModuleType("llama_cpp")
    fake_module.__dict__["Llama"] = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    provider = EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))
    response = provider.complete(
        InferenceRequest(
            messages=(ChatMessage(role="user", content="Think."),),
            enable_thinking=True,
        )
    )

    assert response.content == "thinking"
    assert FakeLlama.handler_kwargs["enable_thinking"] is True
    assert FakeLlama.handler_kwargs["llama"] is provider._llama  # noqa: SLF001


def test_embedded_provider_ignores_enable_thinking_for_unsupported_chat_template(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("stub", encoding="utf-8")

    class FakeLlama:
        completion_kwargs: ClassVar[dict[str, object]] = {}

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.metadata = {"tokenizer.chat_template": "{{ messages[0]['content'] }}"}

        def create_chat_completion(self, **kwargs):
            type(self).completion_kwargs = kwargs
            return {"choices": [{"message": {"content": "plain"}}]}

    fake_module = ModuleType("llama_cpp")
    fake_module.__dict__["Llama"] = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    provider = EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))
    response = provider.complete(
        InferenceRequest(
            messages=(ChatMessage(role="user", content="Think."),),
            enable_thinking=True,
        )
    )

    assert response.content == "plain"
    assert "enable_thinking" not in FakeLlama.completion_kwargs


def test_structured_output_spec_is_reused_for_matching_pydantic_model():
    assert StructuredOutputSpec.from_pydantic_model(StructuredProbe) is StructuredOutputSpec.from_pydantic_model(
        StructuredProbe
    )


def test_embedded_provider_reports_missing_structured_output_grammar(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("stub", encoding="utf-8")

    class FakeLlama:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_module = ModuleType("llama_cpp")
    fake_module.__dict__["Llama"] = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    provider = EmbeddedLlamaCppProvider(_config(LlmProviderName.LLAMA_CPP, str(model_path)))

    with pytest.raises(LlmConfigurationError, match=r"LlamaGrammar\.from_json_schema"):
        provider.complete(
            InferenceRequest(
                messages=(ChatMessage(role="user", content="Return JSON."),),
                structured_output=StructuredOutputSpec.from_pydantic_model(StructuredProbe),
            )
        )


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

    assert "grammar" not in FakeLlama.completion_kwargs
    assert FakeLlama.completion_kwargs["temperature"] == 1.0
    assert FakeLlama.completion_kwargs["top_p"] == 0.95
    assert FakeLlama.completion_kwargs["top_k"] == 64
    assert FakeLlama.completion_kwargs["max_tokens"] == 256
