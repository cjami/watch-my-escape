"""llama-cpp-python inference providers."""

from __future__ import annotations

import os
import sys
from functools import cached_property
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

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


class ZeroGpuQuotaExceededError(RuntimeError):
    """Raised when Hugging Face ZeroGPU daily time is exhausted."""


def _zero_gpu_startup_probe() -> None:
    return None


ZERO_GPU_NON_THINKING_DURATION = 15
NVIDIA_CUDA_PACKAGES: Final = ("nvidia.cuda_runtime", "nvidia.cublas", "nvidia.cuda_nvrtc")
ZERO_GPU_QUOTA_EXHAUSTED_MESSAGE: Final = (
    "ZeroGPU time is exhausted for this Hugging Face account. "
    "Try again after your quota resets, or sign in with more quota."
)
_NVIDIA_CUDA_DLL_DIRECTORIES: set[str] = set()
_NVIDIA_CUDA_DLL_HANDLES: list[object] = []


def _decorate_zero_gpu_function(function: Any, *, duration: int | Callable[..., int]) -> Any | None:
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
            msg = _llama_cpp_load_error_message(exc)
            raise LlmConfigurationError(msg) from exc

        llama_kwargs: dict[str, Any] = {
            "model_path": str(self._model_path),
            "n_ctx": self._config.context_tokens,
            "n_gpu_layers": self._config.gpu_layers,
            "seed": self._config.seed,
            "verbose": False,
        }
        llama_kwargs["flash_attn"] = self._resolve_flash_attn(llama_module)
        if self._config.chat_format:
            llama_kwargs["chat_format"] = self._config.chat_format
        return llama_cls(**llama_kwargs)

    def _prepare_runtime_dependencies(self) -> None:
        """Prepare optional runtime dependencies before importing llama.cpp."""
        _add_nvidia_windows_dll_directories()

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
            "seed": self._config.seed,
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
        try:
            return self._complete_on_gpu(request)
        except Exception as exc:
            if _is_zero_gpu_quota_error(exc):
                raise ZeroGpuQuotaExceededError(ZERO_GPU_QUOTA_EXHAUSTED_MESSAGE) from exc
            raise

    def _build_gpu_completion(self) -> Any:
        complete_on_gpu = _decorate_zero_gpu_function(
            self._complete_with_loaded_model,
            duration=self._zero_gpu_duration,
        )
        if complete_on_gpu is None:
            msg = "The `spaces` package is required for WME_LLM_PROVIDER=zerogpu."
            raise LlmConfigurationError(msg)
        return complete_on_gpu

    def _zero_gpu_duration(self, request: InferenceRequest) -> int:
        if request.phase in {"warmup", "deliberation"} or request.enable_thinking is True:
            return self._config.zerogpu_duration
        return ZERO_GPU_NON_THINKING_DURATION

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


def _is_zero_gpu_quota_error(exc: BaseException) -> bool:
    for current in _exception_chain(exc):
        text = f"{type(current).__name__}: {current}".lower()
        compact_text = "".join(character for character in text if character.isalnum())
        if "zerogpu" in compact_text and ("quota" in text or "time" in text):
            return True
        if "gpu" in text and "quota" in text and any(word in text for word in ("exhaust", "exceed", "limit")):
            return True
    return False


def _llama_cpp_load_error_message(exc: BaseException) -> str:
    msg = (
        "llama-cpp-python could not be loaded. Run one setup profile, for example "
        "`uv run watch-my-escape --setup-only`."
    )
    if _is_windows_cuda_runtime_error(exc):
        return (
            f"{msg} The CUDA profile uses the CUDA 12.4 wheel on Windows, which needs the CUDA 12 runtime "
            "packages. Rerun `uv run watch-my-escape --force-setup --llm-profile cuda`."
        )
    return msg


def _add_nvidia_windows_dll_directories() -> None:
    if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return

    for package in NVIDIA_CUDA_PACKAGES:
        try:
            spec = find_spec(package)
        except ModuleNotFoundError:
            continue
        if spec is None or spec.submodule_search_locations is None:
            continue
        for package_dir in spec.submodule_search_locations:
            _add_dll_directories(Path(package_dir))


def _add_dll_directories(package_dir: Path) -> None:
    for directory_name in ("bin", "lib"):
        dll_dir = package_dir / directory_name
        resolved_dir = str(dll_dir.resolve())
        if resolved_dir in _NVIDIA_CUDA_DLL_DIRECTORIES or not dll_dir.is_dir():
            continue
        try:
            handle = os.add_dll_directory(resolved_dir)
        except OSError:
            continue
        _NVIDIA_CUDA_DLL_DIRECTORIES.add(resolved_dir)
        _NVIDIA_CUDA_DLL_HANDLES.append(handle)


def _is_windows_cuda_runtime_error(exc: BaseException) -> bool:
    for current in _exception_chain(exc):
        text = str(current).lower()
        if "llama.dll" in text and ("could not find module" in text or "failed to load shared library" in text):
            return True
        if any(dll_name in text for dll_name in ("cudart64_12.dll", "cublas64_12.dll")):
            return True
    return False


def _exception_chain(exc: BaseException) -> tuple[BaseException, ...]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    return tuple(chain)
