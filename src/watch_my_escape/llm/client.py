"""llama-cpp-python inference providers."""

from __future__ import annotations

from functools import cached_property
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from watch_my_escape.llm.config import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    LlamaCppConfig,
    LlmProviderName,
    load_config,
)
from watch_my_escape.llm.gguf import GgufMetadataError, GgufSamplingMetadata, read_sampling_metadata
from watch_my_escape.llm.models import InferenceRequest, InferenceResponse
from watch_my_escape.llm.tool_calls import parse_tool_call
from watch_my_escape.llm.tracing import observe_if_enabled


class InferenceProvider(Protocol):
    """Protocol implemented by all inference providers."""

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Run one chat completion."""


class LlmConfigurationError(RuntimeError):
    """Raised when inference cannot be configured."""


def _zero_gpu_startup_probe() -> None:
    return None


def _decorate_zero_gpu_function(function: Any, *, duration: int) -> Any | None:
    try:
        gpu_decorator = import_module("spaces").__dict__["GPU"]
    except ImportError:
        return None
    return gpu_decorator(duration=duration)(function)


_ZERO_GPU_STARTUP_PROBE = _decorate_zero_gpu_function(_zero_gpu_startup_probe, duration=1)


class EmbeddedLlamaCppProvider:
    """Local llama-cpp-python provider."""

    def __init__(self, config: LlamaCppConfig) -> None:
        self._config = config

    @cached_property
    def _llama(self) -> Any:
        return self._load_llama()

    @cached_property
    def _model_path(self) -> Path:
        return Path(self._resolve_model_path())

    @cached_property
    def _sampling_metadata(self) -> GgufSamplingMetadata:
        try:
            return read_sampling_metadata(self._model_path)
        except GgufMetadataError:
            return GgufSamplingMetadata()

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Run one local llama.cpp chat completion."""
        traced_complete = observe_if_enabled(
            self._complete_with_loaded_model,
            name="llm.complete",
            as_type="generation",
            enabled=self._config.langfuse.tracing_enabled,
        )
        return traced_complete(request)

    def _complete_with_loaded_model(self, request: InferenceRequest) -> InferenceResponse:
        payload: dict[str, Any] = {
            "messages": [message.as_llama_message() for message in request.messages],
        }
        payload.update(self._sampling_payload(request))
        if request.tools:
            payload["tools"] = [tool.as_llama_tool() for tool in request.tools]
            payload["tool_choice"] = "auto"
        if request.structured_output is not None:
            try:
                llama_module = import_module("llama_cpp")
                payload["grammar"] = request.structured_output.as_llama_grammar(llama_module)
            except (ImportError, TypeError) as exc:
                msg = "Structured output requires llama-cpp-python with LlamaGrammar.from_json_schema."
                raise LlmConfigurationError(msg) from exc

        raw_response = self._create_chat_completion(payload, request)
        choice_message = raw_response["choices"][0]["message"]
        return InferenceResponse(
            content=choice_message.get("content") or "",
            tool_call=parse_tool_call(choice_message),
            raw=raw_response,
        )

    def _load_llama(self) -> Any:
        self._prepare_runtime_dependencies()
        try:
            llama_module = import_module("llama_cpp")
            llama_cls = llama_module.__dict__["Llama"]
        except (ImportError, RuntimeError) as exc:
            msg = (
                "llama-cpp-python could not be loaded. Run one setup profile, for example "
                "`uv run python -m watch_my_escape.setup_llm cpu`."
            )
            raise LlmConfigurationError(msg) from exc

        llama_kwargs: dict[str, Any] = {
            "model_path": str(self._model_path),
            "n_ctx": self._config.context_tokens,
            "n_gpu_layers": self._config.gpu_layers,
            "verbose": False,
        }
        llama_kwargs["flash_attn"] = self._resolve_flash_attn(llama_module)
        if self._config.chat_format:
            llama_kwargs["chat_format"] = self._config.chat_format
        return llama_cls(**llama_kwargs)

    def _prepare_runtime_dependencies(self) -> None:
        """Prepare optional runtime dependencies before importing llama.cpp."""

    def _resolve_flash_attn(self, llama_module: Any) -> bool:
        if self._config.flash_attn is not None:
            return self._config.flash_attn
        if self._config.gpu_layers == 0:
            return False

        supports_gpu_offload = getattr(llama_module, "llama_supports_gpu_offload", None)
        return bool(supports_gpu_offload and supports_gpu_offload())

    def _resolve_model_path(self) -> str:
        if self._config.model_path is not None:
            if not self._config.model_path.is_file():
                msg = f"Configured WME_MODEL_PATH does not exist: {self._config.model_path}"
                raise LlmConfigurationError(msg)
            return str(self._config.model_path)

        if self._config.model_repo_id and self._config.model_filename:
            try:
                hf_hub_download = import_module("huggingface_hub").hf_hub_download
            except (AttributeError, ImportError) as exc:
                msg = "huggingface-hub is required to download WME_MODEL_REPO_ID/WME_MODEL_FILENAME."
                raise LlmConfigurationError(msg) from exc
            return hf_hub_download(repo_id=self._config.model_repo_id, filename=self._config.model_filename)

        msg = "Configure WME_MODEL_PATH or WME_MODEL_REPO_ID plus WME_MODEL_FILENAME before running inference."
        raise LlmConfigurationError(msg)

    def _sampling_payload(self, request: InferenceRequest) -> dict[str, int | float]:
        max_tokens = request.settings.max_tokens if request.settings.max_tokens is not None else self._config.max_tokens
        return {
            "max_tokens": max_tokens,
            "temperature": _first_float(
                request.settings.temperature,
                self._config.temperature,
                self._sampling_metadata.temperature,
                DEFAULT_TEMPERATURE,
            ),
            "top_p": _first_float(
                request.settings.top_p,
                self._config.top_p,
                self._sampling_metadata.top_p,
                DEFAULT_TOP_P,
            ),
            "top_k": _first_int(
                request.settings.top_k,
                self._config.top_k,
                self._sampling_metadata.top_k,
                DEFAULT_TOP_K,
            ),
        }

    def _create_chat_completion(self, payload: dict[str, Any], request: InferenceRequest) -> dict[str, Any]:
        if request.enable_thinking is None or not self._template_supports_enable_thinking():
            return self._llama.create_chat_completion(**payload)

        handler = self._chat_completion_handler()
        if handler is None:
            return self._llama.create_chat_completion(**payload)

        return handler(
            llama=self._llama,
            **payload,
            enable_thinking=request.enable_thinking,
        )

    def _template_supports_enable_thinking(self) -> bool:
        metadata = getattr(self._llama, "metadata", {})
        if not isinstance(metadata, dict):
            return False
        template = metadata.get("tokenizer.chat_template")
        return isinstance(template, str) and "enable_thinking" in template

    def _chat_completion_handler(self) -> Any | None:
        llama = self._llama
        handler = getattr(llama, "chat_handler", None)
        if handler is not None:
            return handler

        chat_format = getattr(llama, "chat_format", None)
        chat_handlers = getattr(llama, "_chat_handlers", {})
        if isinstance(chat_handlers, dict) and chat_format in chat_handlers:
            return chat_handlers[chat_format]
        if chat_format is None:
            return None

        try:
            chat_format_module = import_module("llama_cpp.llama_chat_format")
            return chat_format_module.get_chat_completion_handler(chat_format)
        except (ImportError, KeyError, TypeError, ValueError):
            return None


class ZeroGpuLlamaCppProvider(EmbeddedLlamaCppProvider):
    """Hugging Face ZeroGPU provider using the same embedded llama.cpp backend."""

    def __init__(self, config: LlamaCppConfig) -> None:
        super().__init__(config)
        self._complete_on_gpu = self._build_gpu_completion()

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Run one ZeroGPU-backed chat completion."""
        return self._complete_on_gpu(request)

    def _build_gpu_completion(self) -> Any:
        complete_on_gpu = _decorate_zero_gpu_function(
            self._complete_with_loaded_model,
            duration=self._config.zerogpu_duration,
        )
        if complete_on_gpu is None:
            msg = "The `spaces` package is required for WME_LLM_PROVIDER=zerogpu."
            raise LlmConfigurationError(msg)
        return complete_on_gpu

    def _prepare_runtime_dependencies(self) -> None:
        try:
            import_module("torch")
        except ImportError as exc:
            msg = "ZeroGPU llama.cpp inference requires torch. Install the hf-zerogpu setup profile."
            raise LlmConfigurationError(msg) from exc


def create_provider(config: LlamaCppConfig | None = None) -> InferenceProvider:
    """Create the configured inference provider."""
    resolved_config = load_config() if config is None else config
    match resolved_config.provider:
        case LlmProviderName.LLAMA_CPP:
            return EmbeddedLlamaCppProvider(resolved_config)
        case LlmProviderName.ZEROGPU:
            return ZeroGpuLlamaCppProvider(resolved_config)
        case LlmProviderName.AUTO:
            msg = "Provider auto-selection should be resolved before provider creation."
            raise LlmConfigurationError(msg)


def _first_float(*values: float | None) -> float:
    for value in values:
        if value is not None:
            return value
    msg = "At least one float fallback is required."
    raise AssertionError(msg)


def _first_int(*values: int | None) -> int:
    for value in values:
        if value is not None:
            return value
    msg = "At least one integer fallback is required."
    raise AssertionError(msg)
