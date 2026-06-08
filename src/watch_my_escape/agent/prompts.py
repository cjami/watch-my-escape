"""Prompt payload construction for agent turns."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from watch_my_escape.llm.models import ChatMessage


def build_deliberation_messages(
    *, room_state: str, objective: str, action_model: type[BaseModel], history: tuple[str, ...] = ()
) -> tuple[ChatMessage, ...]:
    """Build the unconstrained thinking prompt for one turn."""
    return (
        ChatMessage(
            role="system",
            content=(
                "You are an escape-room agent. Think carefully before acting. Explore assumptions, possible puzzle "
                "mechanics, and risks before choosing a single action to perform next."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"{_turn_context(room_state=room_state, objective=objective, history=history)}\n\n"
                f"Available actions:\n{format_action_options(action_model)}"
            ),
        ),
    )


def build_action_messages(
    *,
    room_state: str,
    objective: str,
    deliberation: str,
    action_model: type[BaseModel],
    history: tuple[str, ...] = (),
) -> tuple[ChatMessage, ...]:
    """Build the constrained action prompt for one turn."""
    return (
        ChatMessage(
            role="system",
            content=(
                "You are choosing the next escape-room action. Use the prior deliberation, but do not continue "
                "reasoning. Return only one JSON object matching the provided schema."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"{_turn_context(room_state=room_state, objective=objective, history=history)}\n\n"
                f"Prior deliberation:\n{deliberation.strip()}\n\n"
                f"Available actions:\n{format_action_options(action_model)}"
            ),
        ),
    )


def _turn_context(*, room_state: str, objective: str, history: tuple[str, ...]) -> str:
    history_text = "\n".join(f"- {entry}" for entry in history) if history else "- No previous turns."
    return f"Objective:\n{objective.strip()}\n\nRoom state:\n{room_state.strip()}\n\nHistory:\n{history_text}"


def format_action_options(action_model: type[BaseModel]) -> str:
    """Format action choices and field constraints for prompts and transcripts."""
    schema = action_model.model_json_schema()
    actions = sorted(_collect_action_schemas(schema), key=_action_name)
    if not actions:
        return f"- {action_model.__name__}"
    return "\n".join(_format_action_schema(action_schema, schema) for action_schema in actions)


def _collect_action_schemas(schema_node: Any) -> list[dict[str, Any]]:
    if isinstance(schema_node, dict):
        action_schema = schema_node.get("properties", {}).get("action")
        if isinstance(action_schema, dict) and _action_name(schema_node):
            return [schema_node]

        actions: list[dict[str, Any]] = []
        for value in schema_node.values():
            actions.extend(_collect_action_schemas(value))
        return actions

    if isinstance(schema_node, list):
        actions: list[dict[str, Any]] = []
        for value in schema_node:
            actions.extend(_collect_action_schemas(value))
        return actions

    return []


def _format_action_schema(action_schema: dict[str, Any], root_schema: dict[str, Any]) -> str:
    action = _action_name(action_schema)
    description = action_schema.get("description")
    field_descriptions = _format_action_fields(action_schema, root_schema)
    parts = [f"- {action}"]
    if isinstance(description, str):
        parts.append(description)
    if field_descriptions:
        parts.append(f"Use with {field_descriptions}.")
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}: {' '.join(parts[1:])}"


def _format_action_fields(action_schema: dict[str, Any], root_schema: dict[str, Any]) -> str:
    properties = action_schema.get("properties")
    if not isinstance(properties, dict):
        return ""

    fields: list[str] = []
    for field_name, field_schema in properties.items():
        if field_name in {"action", "emotion"} or not isinstance(field_schema, dict):
            continue
        fields.append(f"{field_name}{_format_field_constraints(field_schema, root_schema)}")
    return "; ".join(fields)


def _format_field_constraints(field_schema: dict[str, Any], root_schema: dict[str, Any]) -> str:
    resolved = _resolve_schema(field_schema, root_schema)
    variants = resolved.get("anyOf")
    if isinstance(variants, list):
        formatted_variants = [
            _format_field_constraints(variant, root_schema) for variant in variants if isinstance(variant, dict)
        ]
        return " or ".join(variant for variant in formatted_variants if variant)

    values = _literal_values(resolved)
    description = resolved.get("description")
    if values:
        return f": one of {', '.join(values)}"
    if isinstance(description, str):
        return f": {_sentence_fragment(description)}"
    return ""


def _literal_values(schema_node: dict[str, Any]) -> list[str]:
    const = schema_node.get("const")
    if isinstance(const, str):
        return [const]

    enum = schema_node.get("enum")
    if isinstance(enum, list):
        return [value for value in enum if isinstance(value, str)]

    return []


def _action_name(schema_node: dict[str, Any]) -> str:
    action_schema = schema_node.get("properties", {}).get("action")
    if not isinstance(action_schema, dict):
        return ""
    values = _literal_values(action_schema)
    return values[0] if values else ""


def _resolve_schema(schema_node: dict[str, Any], root_schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema_node.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return schema_node

    defs = root_schema.get("$defs")
    if not isinstance(defs, dict):
        return schema_node

    resolved = defs.get(ref.removeprefix("#/$defs/"))
    return resolved if isinstance(resolved, dict) else schema_node


def _sentence_fragment(value: str) -> str:
    fragment = value.removesuffix(".")
    return f"{fragment[:1].lower()}{fragment[1:]}" if fragment else fragment
