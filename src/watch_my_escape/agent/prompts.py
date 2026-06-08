"""Prompt payload construction for agent turns."""

from __future__ import annotations

from importlib import resources
from typing import Any

from pydantic import BaseModel

from watch_my_escape.llm.models import ChatMessage

PROMPT_TEMPLATE_PACKAGE = "watch_my_escape.agent.prompt_templates"


def build_deliberation_messages(
    *, game_state: str, action_model: type[BaseModel], history: tuple[str, ...] = ()
) -> tuple[ChatMessage, ...]:
    """Build the unconstrained thinking prompt for one turn."""
    turn_context = _turn_context(game_state=game_state, history=history)
    action_options = format_action_options(action_model)
    return (
        ChatMessage(
            role="system",
            content=_load_prompt_template("deliberation-system.md"),
        ),
        ChatMessage(
            role="user",
            content=_load_prompt_template("deliberation-user.md").format(
                turn_context=turn_context,
                action_options=action_options,
            ),
        ),
    )


def build_action_messages(
    *,
    game_state: str,
    deliberation: str,
    action_model: type[BaseModel],
    history: tuple[str, ...] = (),
) -> tuple[ChatMessage, ...]:
    """Build the constrained action prompt for one turn."""
    turn_context = _turn_context(game_state=game_state, history=history)
    action_options = format_action_options(action_model)
    return (
        ChatMessage(
            role="system",
            content=_load_prompt_template("action-system.md"),
        ),
        ChatMessage(
            role="user",
            content=_load_prompt_template("action-user.md").format(
                turn_context=turn_context,
                deliberation=deliberation.strip(),
                action_options=action_options,
            ),
        ),
    )


def _load_prompt_template(file_name: str) -> str:
    return resources.files(PROMPT_TEMPLATE_PACKAGE).joinpath(file_name).read_text(encoding="utf-8").strip()


def _turn_context(*, game_state: str, history: tuple[str, ...]) -> str:
    history_text = "\n".join(f"- {entry}" for entry in history) if history else "- No recent actions."
    return f"Game state:\n{game_state.strip()}\n\nRecent actions:\n{history_text}"


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
    signature = _action_signature(action, action_schema)
    description = action_schema.get("description")
    if not isinstance(description, str) or not description:
        return f"- {signature}"
    return f"- {signature}: {description}"


def _action_signature(action: str, action_schema: dict[str, Any]) -> str:
    properties = action_schema.get("properties", {})
    required = action_schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        return action

    ordered_fields = ("item", "target", "text")
    fields = [field for field in ordered_fields if field in properties and field in required]
    if not fields:
        return action
    return f"{action}({', '.join(fields)})"


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
