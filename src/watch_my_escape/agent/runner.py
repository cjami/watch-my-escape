"""Agent turn execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel

from watch_my_escape.agent.prompts import build_action_messages, build_deliberation_messages
from watch_my_escape.llm.models import InferenceRequest, InferenceSettings, StructuredOutputSpec
from watch_my_escape.llm.structured import strip_thinking_sections, validate_structured_output
from watch_my_escape.llm.tracing import observe_if_enabled

if TYPE_CHECKING:
    from watch_my_escape.llm.client import InferenceProvider


@dataclass(frozen=True, slots=True)
class ThinkActSettings:
    """Generation settings for the two phases of an agent turn."""

    deliberation: InferenceSettings = field(
        default_factory=lambda: InferenceSettings(max_tokens=4096, temperature=1.0, top_p=0.95)
    )
    action: InferenceSettings = field(default_factory=lambda: InferenceSettings(max_tokens=256, temperature=0.0))


@dataclass(frozen=True, slots=True)
class ThinkActTurn:
    """Input for one think-then-act agent turn."""

    game_state: str
    action_model: type[BaseModel]
    history: tuple[str, ...] = ()
    settings: ThinkActSettings = field(default_factory=ThinkActSettings)


@dataclass(frozen=True, slots=True)
class ThinkActResult:
    """Result of one think-then-act agent turn."""

    deliberation: str
    action: BaseModel


def run_think_act_turn(provider: InferenceProvider, turn: ThinkActTurn) -> ThinkActResult:
    """Run one unconstrained deliberation call followed by one constrained action call."""
    traced_turn = observe_if_enabled(
        _run_think_act_turn,
        name="agent.think_act_turn",
        as_type="agent",
    )
    return traced_turn(provider, turn)


def _run_think_act_turn(provider: InferenceProvider, turn: ThinkActTurn) -> ThinkActResult:
    """Run one unconstrained deliberation call followed by one constrained action call."""
    deliberation_response = provider.complete(
        InferenceRequest(
            messages=build_deliberation_messages(
                game_state=turn.game_state,
                action_model=turn.action_model,
                history=turn.history,
            ),
            settings=turn.settings.deliberation,
        )
    )
    deliberation = deliberation_response.content.strip()
    action_deliberation = strip_thinking_sections(deliberation)

    action_response = provider.complete(
        InferenceRequest(
            messages=build_action_messages(
                game_state=turn.game_state,
                deliberation=action_deliberation,
                action_model=turn.action_model,
                history=turn.history,
            ),
            structured_output=StructuredOutputSpec.from_pydantic_model(turn.action_model),
            settings=turn.settings.action,
        )
    )

    return ThinkActResult(
        deliberation=deliberation,
        action=validate_structured_output(turn.action_model, action_response.content),
    )
