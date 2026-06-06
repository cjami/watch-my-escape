"""Prompt payload construction for agent turns."""

from __future__ import annotations

from pydantic import BaseModel

from watch_my_escape.llm.models import ChatMessage


def build_deliberation_messages(
    *, room_state: str, objective: str, history: tuple[str, ...] = ()
) -> tuple[ChatMessage, ...]:
    """Build the unconstrained thinking prompt for one turn."""
    return (
        ChatMessage(
            role="system",
            content=(
                "You are an escape-room agent. Think carefully before acting. Explore assumptions, possible puzzle "
                "mechanics, and risks before choosing what to do next."
            ),
        ),
        ChatMessage(
            role="user",
            content=_turn_context(room_state=room_state, objective=objective, history=history),
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
                f"Action schema name: {action_model.__name__}"
            ),
        ),
    )


def _turn_context(*, room_state: str, objective: str, history: tuple[str, ...]) -> str:
    history_text = "\n".join(f"- {entry}" for entry in history) if history else "- No previous turns."
    return f"Objective:\n{objective.strip()}\n\nRoom state:\n{room_state.strip()}\n\nHistory:\n{history_text}"
