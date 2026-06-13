"""Prompt payload construction for agent turns."""

from __future__ import annotations

from importlib import resources

from pydantic import BaseModel

from watch_my_escape.game.action_options import ACTION_DESCRIPTIONS
from watch_my_escape.llm.models import ChatMessage

PROMPT_TEMPLATE_PACKAGE = "watch_my_escape.agent.prompt_templates"
RECENT_ACTION_LIMIT = 10
PROMPT_ACTION_SIGNATURES = {
    "close": "close(target)",
    "examine": "examine(target)",
    "operate": "operate(target)",
    "open": "open(target)",
    "pick_up": "pick_up(target)",
    "pull": "pull(target)",
    "push": "push(target)",
    "talk_to": "talk_to(target, text)",
    "use_item": "use_item(item, target)",
}


def build_deliberation_messages(
    *, game_state: str, action_model: type[BaseModel], history: tuple[str, ...] = ()
) -> tuple[ChatMessage, ...]:
    """Build the unconstrained thinking prompt for one turn."""
    turn_context = _turn_context(game_state=game_state, history=history)
    action_options = format_action_options(action_model)
    return (
        ChatMessage(
            role="system",
            content=_load_prompt_template("deliberation-system.md").format(action_options=action_options),
        ),
        ChatMessage(
            role="user",
            content=_load_prompt_template("deliberation-user.md").format(
                turn_context=turn_context,
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
    recent_history = history[-RECENT_ACTION_LIMIT:]
    history_text = "\n".join(f"- {entry}" for entry in recent_history) if recent_history else "- No recent actions."
    return f"Game state:\n{game_state.strip()}\n\nRecent actions, oldest to newest:\n{history_text}"


def format_action_options(_action_model: type[BaseModel]) -> str:
    """Format the general action vocabulary for prompts and transcripts."""
    return "\n".join(
        f"- {signature}: {ACTION_DESCRIPTIONS[action]}" for action, signature in PROMPT_ACTION_SIGNATURES.items()
    )
