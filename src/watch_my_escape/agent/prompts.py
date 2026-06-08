"""Prompt payload construction for agent turns."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from watch_my_escape.llm.models import ChatMessage


def build_deliberation_messages(
    *, game_state: str, objective: str, action_model: type[BaseModel], history: tuple[str, ...] = ()
) -> tuple[ChatMessage, ...]:
    """Build the unconstrained thinking prompt for one turn."""
    return (
        ChatMessage(
            role="system",
            content=(
                "You are playing an escape room game. Consider what the next best action will be. "
                "Choose only ONE action. Provide a plain-text description of what you want to do."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"{_turn_context(game_state=game_state, objective=objective, history=history)}\n\n"
                f"Available actions:\n{format_action_options(action_model)}"
            ),
        ),
    )


def build_action_messages(
    *,
    game_state: str,
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
                f"{_turn_context(game_state=game_state, objective=objective, history=history)}\n\n"
                f"Prior deliberation:\n{deliberation.strip()}\n\n"
                f"Available actions:\n{format_action_options(action_model)}"
            ),
        ),
    )


def _turn_context(*, game_state: str, objective: str, history: tuple[str, ...]) -> str:
    history_text = "\n".join(f"- {entry}" for entry in history) if history else "- No previous turns."
    return f"Objective:\n{objective.strip()}\n\nGame state:\n{game_state.strip()}\n\nHistory:\n{history_text}"


def format_action_options(action_model: type[BaseModel]) -> str:
    """Format action choices for prompts and transcripts."""
    schema = action_model.model_json_schema()
    actions = sorted(_collect_action_schemas(schema), key=_action_name)
    if not actions:
        return f"- {action_model.__name__}"
    return "\n".join(_format_action_schema(action_schema) for action_schema in actions)


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


def _format_action_schema(action_schema: dict[str, Any]) -> str:
    action = _action_name(action_schema)
    description = action_schema.get("description")
    if isinstance(description, str):
        return f"- {action}: {description}"
    return f"- {action}"


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
