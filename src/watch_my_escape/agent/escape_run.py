"""Run a model through an escape-room game map."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import ValidationError

from watch_my_escape.agent.prompts import build_action_messages, build_deliberation_messages
from watch_my_escape.agent.runner import ThinkActResult, ThinkActSettings
from watch_my_escape.game.action_options import build_available_action_model
from watch_my_escape.game.actions import EscapeRoomAction
from watch_my_escape.game.maps import GameSessionState, PlacedEntity, render_user_map_view, visible_notable_entities
from watch_my_escape.game.premade_maps import get_premade_map
from watch_my_escape.game.runtime import STARTING_SANITY, apply_agent_action, render_game_state_for_agent
from watch_my_escape.llm.client import InferenceProvider, create_provider
from watch_my_escape.llm.models import InferenceRequest, StructuredOutputSpec
from watch_my_escape.llm.structured import StructuredOutputError, strip_thinking_sections, validate_structured_output

if TYPE_CHECKING:
    from collections.abc import Iterator

    from watch_my_escape.game.maps import GameMap

DEFAULT_MAP_ID = "key-door-room"


@dataclass(frozen=True, slots=True)
class EscapeRunFrame:
    """Visible state after one moment in the model escape attempt."""

    escaped: bool
    sanity: int
    position: str
    visible_entities: tuple[str, ...]
    inventory: tuple[str, ...]
    journal: tuple[str, ...]
    map_view: tuple[tuple[str, ...], ...]
    transcript: str
    status: str
    delay_ms: int = 0


@dataclass(frozen=True, slots=True)
class EscapeRunResult:
    """Complete result for one model escape attempt."""

    escaped: bool
    sanity: int
    visible_entities: tuple[str, ...]
    inventory: tuple[str, ...]
    journal: tuple[str, ...]
    map_view: tuple[tuple[str, ...], ...]
    transcript: str
    frames: tuple[EscapeRunFrame, ...] = ()

    @property
    def status(self) -> str:
        """Return a concise user-facing final status."""
        if self.escaped:
            return f"Escaped with {self.sanity} sanity remaining."
        return "Sanity reached 0 before the model escaped."


@dataclass(frozen=True, slots=True)
class FramePresentation:
    """Visual presentation options for one emitted frame."""

    delay_ms: int = 0
    agent_icon: str = "\U0001f642"


DEFAULT_FRAME_PRESENTATION = FramePresentation()


class EscapeTurnActionError(ValueError):
    """Raised when the action phase returns output outside the current schema."""

    def __init__(self, message: str, *, deliberation: str) -> None:
        super().__init__(message)
        self.deliberation = deliberation


def run_model_escape(
    *,
    provider: InferenceProvider | None = None,
    game_map: GameMap | None = None,
    starting_sanity: int = STARTING_SANITY,
) -> EscapeRunResult:
    """Run the configured model through an escape-room map."""
    frames = tuple(
        run_model_escape_steps(
            provider=provider,
            game_map=game_map,
            starting_sanity=starting_sanity,
        )
    )
    final_frame = frames[-1]
    return EscapeRunResult(
        escaped=final_frame.escaped,
        sanity=final_frame.sanity,
        visible_entities=final_frame.visible_entities,
        inventory=final_frame.inventory,
        journal=final_frame.journal,
        map_view=final_frame.map_view,
        transcript=final_frame.transcript,
        frames=frames,
    )


def run_model_escape_steps(
    *,
    provider: InferenceProvider | None = None,
    game_map: GameMap | None = None,
    starting_sanity: int = STARTING_SANITY,
) -> Iterator[EscapeRunFrame]:
    """Yield visible state after each model turn in an escape-room map."""
    resolved_provider = create_provider() if provider is None else provider
    premade_map = get_premade_map(DEFAULT_MAP_ID) if game_map is None else None
    selected_map = premade_map.map if premade_map else game_map
    if selected_map is None:
        msg = "a game map is required"
        raise ValueError(msg)
    session = GameSessionState(map=selected_map)
    sanity = starting_sanity
    history: list[str] = []
    transcript: list[str] = []

    yield _frame(session, sanity, transcript, "Model run started.")

    while sanity > 0 and not session.escaped:
        turn_number = len(transcript) + 1
        game_state = render_game_state_for_agent(session, sanity)
        try:
            result = _run_escape_turn(
                provider=resolved_provider,
                session=session,
                game_state=game_state,
                history=tuple(history),
            )
        except EscapeTurnActionError as exc:
            next_sanity = max(0, sanity - 1)
            message = f"Model returned an action outside the current grammar: {exc}"
            transcript.append(
                "\n".join(
                    [
                        f"Turn {turn_number} - sanity {sanity} -> {next_sanity}",
                        *_deliberation_lines(exc.deliberation),
                        "Action: invalid",
                        f"Result: {message}",
                        _position_line(session),
                    ]
                )
            )
            history.append(f"Invalid action -> {message}")
            sanity = next_sanity
            yield _frame(session, sanity, transcript, _status(escaped=session.escaped, sanity=sanity))
            continue
        action = EscapeRoomAction.model_validate(result.action.model_dump(mode="json"))
        applied = apply_agent_action(session, sanity, action)
        action_emotion = action.root.emotion
        action_text = action.model_dump_json()
        transcript.append(
            "\n".join(
                [
                    f"Turn {turn_number} - sanity {sanity} -> {applied.sanity}",
                    *_deliberation_lines(result.deliberation),
                    f"Action: {action_text}",
                    f"Result: {applied.message}",
                    _position_line(applied.session),
                ]
            )
        )
        history.append(f"{_history_action_text(action)} -> {applied.message}")
        sanity = applied.sanity
        if applied.movement_path:
            for index, step in enumerate(applied.movement_path):
                is_final_step = index == len(applied.movement_path) - 1
                session = applied.session if is_final_step else session.model_copy(update={"agent_position": step})
                yield _frame(
                    session,
                    sanity,
                    transcript,
                    _status(escaped=applied.session.escaped, sanity=sanity),
                    presentation=FramePresentation(delay_ms=150, agent_icon=action_emotion),
                )
            session = applied.session
            continue

        session = applied.session
        yield _frame(
            session,
            sanity,
            transcript,
            _status(escaped=session.escaped, sanity=sanity),
            presentation=FramePresentation(agent_icon=action_emotion),
        )

    if not transcript:
        yield _frame(session, sanity, transcript, _status(escaped=session.escaped, sanity=sanity))


def _frame(
    session: GameSessionState,
    sanity: int,
    transcript: list[str],
    status: str,
    *,
    presentation: FramePresentation = DEFAULT_FRAME_PRESENTATION,
) -> EscapeRunFrame:
    return EscapeRunFrame(
        escaped=session.escaped,
        sanity=sanity,
        position=_position_text(session),
        visible_entities=_visible_entity_text(session),
        inventory=session.inventory,
        journal=session.notes,
        map_view=render_user_map_view(session, agent_icon=presentation.agent_icon),
        transcript="\n\n".join(transcript),
        status=status,
        delay_ms=presentation.delay_ms,
    )


def _status(*, escaped: bool, sanity: int) -> str:
    if escaped:
        return f"Escaped with {sanity} sanity remaining."
    if sanity == 0:
        return "Sanity reached 0 before the model escaped."
    return f"Still searching with {sanity} sanity remaining."


def _position_line(session: GameSessionState) -> str:
    return f"Position: {_position_text(session)}"


def _deliberation_lines(deliberation: str) -> tuple[str, ...]:
    stripped = strip_thinking_sections(deliberation).strip()
    if not stripped:
        return ()
    return (f"Deliberation: {stripped}",)


def _position_text(session: GameSessionState) -> str:
    position = session.current_position
    return f"({position.x}, {position.y})"


def _visible_entity_text(session: GameSessionState) -> tuple[str, ...]:
    return tuple(_placed_entity_text(placed) for placed in visible_notable_entities(session))


def _placed_entity_text(placed: PlacedEntity) -> str:
    return f"{placed.entity.id}: {placed.entity.name}. {placed.entity.description}"


def _history_action_text(action: EscapeRoomAction) -> str:
    root = action.root
    if root.action == "take_note":
        return f"take_note: {root.text}"
    if root.action == "talk_to":
        return f"talk_to {root.target}: {root.text}"
    if root.action == "use_item":
        return f"use_item {root.item} on {root.target}"
    return f"{root.action} {root.target}"


def _run_escape_turn(
    *,
    provider: InferenceProvider,
    session: GameSessionState,
    game_state: str,
    history: tuple[str, ...],
) -> ThinkActResult:
    settings = ThinkActSettings()
    action_model = build_available_action_model(session)
    deliberation_response = provider.complete(
        InferenceRequest(
            messages=build_deliberation_messages(
                game_state=game_state,
                action_model=action_model,
                history=history,
            ),
            settings=settings.deliberation,
        )
    )
    deliberation = deliberation_response.content.strip()
    action_deliberation = strip_thinking_sections(deliberation)
    action_response = provider.complete(
        InferenceRequest(
            messages=build_action_messages(
                game_state=game_state,
                deliberation=action_deliberation,
                action_model=action_model,
                history=history,
            ),
            structured_output=StructuredOutputSpec.from_pydantic_model(action_model),
            settings=settings.action,
        )
    )
    try:
        action = validate_structured_output(action_model, action_response.content)
    except (StructuredOutputError, ValidationError) as exc:
        raise EscapeTurnActionError(
            str(exc),
            deliberation=deliberation,
        ) from exc
    return ThinkActResult(deliberation=deliberation, action=action)
