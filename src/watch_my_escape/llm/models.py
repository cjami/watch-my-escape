"""Shared inference request and response models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Literal

from pydantic import BaseModel

MessageRole = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A chat message passed to llama.cpp."""

    role: MessageRole
    content: str

    def as_llama_message(self) -> dict[str, str]:
        """Return the mapping shape expected by llama-cpp-python."""
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """JSON schema for one tool the model may call."""

    name: str
    description: str
    parameters: dict[str, Any]

    def as_llama_tool(self) -> dict[str, Any]:
        """Return an OpenAI-compatible tool descriptor."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True, slots=True)
class StructuredOutputSpec:
    """JSON schema used to constrain model text output."""

    name: str
    schema: dict[str, Any]

    @classmethod
    def from_pydantic_model(cls, model: type[BaseModel]) -> StructuredOutputSpec:
        """Build a structured output spec from a Pydantic model."""
        return _structured_output_spec_from_model(model)

    def as_llama_response_format(self) -> dict[str, Any]:
        """Return the response format expected by llama-cpp-python."""
        return {"type": "json_object", "schema": self.schema}

    def as_llama_grammar(self, llama_module: Any) -> Any:
        """Return a llama.cpp grammar generated from this JSON schema."""
        llama_grammar = getattr(llama_module, "LlamaGrammar", None)
        from_json_schema = getattr(llama_grammar, "from_json_schema", None)
        if not callable(from_json_schema):
            msg = "llama-cpp-python does not expose LlamaGrammar.from_json_schema."
            raise TypeError(msg)
        return from_json_schema(json.dumps(self.schema))


@dataclass(frozen=True, slots=True)
class InferenceSettings:
    """Generation settings for one inference call."""

    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """A chat completion request."""

    messages: tuple[ChatMessage, ...]
    tools: tuple[ToolSpec, ...] = ()
    structured_output: StructuredOutputSpec | None = None
    settings: InferenceSettings = field(default_factory=InferenceSettings)
    enable_thinking: bool | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A parsed tool call returned by the model."""

    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InferenceResponse:
    """A normalized model response."""

    content: str
    tool_call: ToolCall | None = None
    raw: dict[str, Any] | None = None


@cache
def _structured_output_spec_from_model(model: type[BaseModel]) -> StructuredOutputSpec:
    return StructuredOutputSpec(name=model.__name__, schema=model.model_json_schema())
