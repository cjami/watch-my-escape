"""Tool-call parsing for llama.cpp chat completions."""

from __future__ import annotations

import json
from typing import Any

from watch_my_escape.llm.models import ToolCall


class ToolCallParseError(ValueError):
    """Raised when a model response does not contain a valid tool call."""


def parse_tool_call(choice_message: dict[str, Any]) -> ToolCall | None:
    """Parse the first OpenAI-style tool call from a llama.cpp response message."""
    tool_calls = choice_message.get("tool_calls")
    if not tool_calls:
        return None

    first_call = tool_calls[0]
    function = first_call.get("function")
    if not isinstance(function, dict):
        msg = "Tool call is missing a function payload."
        raise ToolCallParseError(msg)

    name = function.get("name")
    if not isinstance(name, str) or not name:
        msg = "Tool call is missing a function name."
        raise ToolCallParseError(msg)

    arguments_payload = function.get("arguments", "{}")
    if isinstance(arguments_payload, str):
        try:
            arguments = json.loads(arguments_payload)
        except json.JSONDecodeError as exc:
            msg = f"Tool call arguments are not valid JSON: {exc.msg}."
            raise ToolCallParseError(msg) from exc
    elif isinstance(arguments_payload, dict):
        arguments = arguments_payload
    else:
        msg = "Tool call arguments must be a JSON string or object."
        raise ToolCallParseError(msg)

    if not isinstance(arguments, dict):
        msg = "Tool call arguments must decode to an object."
        raise ToolCallParseError(msg)

    return ToolCall(name=name, arguments=arguments)
