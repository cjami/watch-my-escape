"""Structured output parsing helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel


class StructuredOutputError(ValueError):
    """Raised when a response cannot be parsed as structured output."""


def parse_json_object(content: str) -> dict[str, Any]:
    """Parse the first JSON object from model output after removing thinking text."""
    stripped = strip_thinking_sections(content)
    if not stripped:
        msg = "Response was empty"
        raise StructuredOutputError(msg)

    candidates = [stripped, *_json_code_blocks(stripped), *_json_object_substrings(stripped)]
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    msg = "Response did not contain a valid JSON object"
    raise StructuredOutputError(msg)


def validate_structured_output(model: type[BaseModel], content: str) -> BaseModel:
    """Parse and validate model output against a Pydantic model."""
    return model.model_validate(parse_json_object(content))


def strip_thinking_sections(content: str) -> str:
    """Remove common visible thinking wrappers from model output."""
    stripped = re.sub(r"<think\b[^>]*>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r"^.*?</think>", "", stripped, count=1, flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r"<think\b[^>]*>.*$", "", stripped, count=1, flags=re.DOTALL | re.IGNORECASE)
    return stripped.strip()


def _json_code_blocks(content: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)]


def _json_object_substrings(content: str) -> list[str]:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return []
    return [content[start : end + 1]]
