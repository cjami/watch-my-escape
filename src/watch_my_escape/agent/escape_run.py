"""Run a model through an escape-room game map."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from watch_my_escape.agent.emotions import emotion_to_emoji
from watch_my_escape.agent.prompts import build_action_messages, build_deliberation_messages
from watch_my_escape.agent.runner import ThinkActResult, ThinkActSettings
from watch_my_escape.game.action_options import build_available_action_model
from watch_my_escape.game.actions import EscapeRoomAction
from watch_my_escape.game.maps import (
    GameSessionState,
    PlacedEntity,
    render_user_map_color_view,
    render_user_map_view,
    render_user_visibility_view,
    visible_notable_entities,
)
from watch_my_escape.game.models import render_state_template
from watch_my_escape.game.premade_maps import get_premade_map
from watch_my_escape.game.runtime import STARTING_SANITY, apply_agent_action, render_game_state_for_agent
from watch_my_escape.llm.client import InferenceProvider, create_provider
from watch_my_escape.llm.models import InferenceRequest, StructuredOutputSpec
from watch_my_escape.llm.structured import StructuredOutputError, strip_thinking_sections, validate_structured_output

if TYPE_CHECKING:
    from collections.abc import Iterator

    from watch_my_escape.game.maps import GameMap
    from watch_my_escape.game.models import Entity

DEFAULT_MAP_ID = "key-door-room"


@dataclass(frozen=True, slots=True)
class EntityDisplay:
    """Browser-facing display metadata for one visible or carried entity."""

    id: str
    icon: str
    description: str
    color: str | None = None


@dataclass(frozen=True, slots=True)
class EscapeRunFrame:
    """Visible state after one moment in the model escape attempt."""

    escaped: bool
    sanity: int
    position: str
    visible_entities: tuple[str, ...]
    inventory: tuple[str, ...]
    map_view: tuple[tuple[str, ...], ...]
    map_color_view: tuple[tuple[str, ...], ...]
    transcript: str
    status: str
    delay_ms: int = 0
    action_label: str = ""
    visibility_view: tuple[tuple[bool, ...], ...] = ()
    visible_entity_details: tuple[EntityDisplay, ...] = ()
    inventory_details: tuple[EntityDisplay, ...] = ()


@dataclass(frozen=True, slots=True)
class EscapeRunResult:
    """Complete result for one model escape attempt."""

    escaped: bool
    sanity: int
    visible_entities: tuple[str, ...]
    inventory: tuple[str, ...]
    map_view: tuple[tuple[str, ...], ...]
    map_color_view: tuple[tuple[str, ...], ...]
    transcript: str
    status: str
    frames: tuple[EscapeRunFrame, ...] = ()
    visibility_view: tuple[tuple[bool, ...], ...] = ()
    visible_entity_details: tuple[EntityDisplay, ...] = ()
    inventory_details: tuple[EntityDisplay, ...] = ()


@dataclass(frozen=True, slots=True)
class FramePresentation:
    """Visual presentation options for one emitted frame."""

    delay_ms: int = 0
    agent_icon: str = "\U0001f642"
    action_label: str = ""


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
    settings: ThinkActSettings | None = None,
) -> EscapeRunResult:
    """Run the configured model through an escape-room map."""
    frames = tuple(
        run_model_escape_steps(
            provider=provider,
            game_map=game_map,
            starting_sanity=starting_sanity,
            settings=settings,
        )
    )
    final_frame = frames[-1]
    return EscapeRunResult(
        escaped=final_frame.escaped,
        sanity=final_frame.sanity,
        visible_entities=final_frame.visible_entities,
        inventory=final_frame.inventory,
        map_view=final_frame.map_view,
        map_color_view=final_frame.map_color_view,
        transcript=final_frame.transcript,
        status=final_frame.status,
        frames=frames,
        visibility_view=final_frame.visibility_view,
        visible_entity_details=final_frame.visible_entity_details,
        inventory_details=final_frame.inventory_details,
    )


def run_model_escape_steps(
    *,
    provider: InferenceProvider | None = None,
    game_map: GameMap | None = None,
    starting_sanity: int = STARTING_SANITY,
    startup_delay_ms: int = 0,
    settings: ThinkActSettings | None = None,
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

    yield _frame(
        session,
        sanity,
        transcript,
        "Model run started.",
        presentation=FramePresentation(delay_ms=startup_delay_ms),
    )

    while sanity > 0 and not session.escaped:
        turn_number = len(transcript) + 1
        game_state = render_game_state_for_agent(session, sanity)
        action_model = build_available_action_model(session)
        if action_model is None:
            status = "No available actions remain before the model escaped."
            transcript.append(
                "\n".join(
                    [
                        f"Turn {turn_number} - sanity {sanity} -> {sanity}",
                        "Action: none",
                        f"Result: {status}",
                        _position_line(session),
                    ]
                )
            )
            yield _frame(session, sanity, transcript, status)
            break
        try:
            result = _run_escape_turn(
                provider=resolved_provider,
                game_state=game_state,
                action_model=action_model,
                history=tuple(history),
                settings=settings,
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
        action_emotion = emotion_to_emoji(action.root.emotion)
        action_label = _action_label(action)
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
                    presentation=FramePresentation(
                        delay_ms=150,
                        agent_icon=action_emotion,
                        action_label=action_label if is_final_step else "",
                    ),
                )
            session = applied.session
            continue

        session = applied.session
        yield _frame(
            session,
            sanity,
            transcript,
            _status(escaped=session.escaped, sanity=sanity),
            presentation=FramePresentation(agent_icon=action_emotion, action_label=action_label),
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
        visible_entity_details=_visible_entity_details(session),
        inventory_details=_inventory_details(session),
        map_view=render_user_map_view(session, agent_icon=presentation.agent_icon),
        map_color_view=render_user_map_color_view(session),
        transcript="\n\n".join(transcript),
        status=status,
        delay_ms=presentation.delay_ms,
        action_label=presentation.action_label,
        visibility_view=render_user_visibility_view(session),
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
    return f"{placed.entity.id}: {_entity_description(placed.entity)}"


def _visible_entity_details(session: GameSessionState) -> tuple[EntityDisplay, ...]:
    return tuple(_placed_entity_detail(placed) for placed in visible_notable_entities(session))


def _placed_entity_detail(placed: PlacedEntity) -> EntityDisplay:
    return _entity_detail(placed.entity)


def _inventory_details(session: GameSessionState) -> tuple[EntityDisplay, ...]:
    entities = session.map.entities_by_id()
    return tuple(_inventory_detail(item, entities) for item in session.inventory)


def _inventory_detail(entity_id: str, entities: dict[str, Entity]) -> EntityDisplay:
    if entity_id not in entities:
        return _unknown_entity_detail(entity_id)
    return _entity_detail(entities[entity_id])


def _entity_detail(entity: Entity) -> EntityDisplay:
    return EntityDisplay(id=entity.id, icon=entity.icon, description=_entity_description(entity), color=entity.color)


def _unknown_entity_detail(entity_id: str) -> EntityDisplay:
    return EntityDisplay(id=entity_id, icon="?", description="")


def _entity_description(entity: Entity) -> str:
    return render_state_template(entity.description, entity.state)


def _history_action_text(action: EscapeRoomAction) -> str:
    root = action.root
    if root.action == "talk_to":
        return f'You said "{root.text}" to {root.target}'
    if root.action == "use_item":
        return f"You used {root.item} on {root.target}"
    past_tense_verbs = {
        "close": "closed",
        "examine": "examined",
        "open": "opened",
        "operate": "operated",
        "pull": "pulled",
        "push": "pushed",
        "pick_up": "picked up",
    }
    return f"You {past_tense_verbs[root.action]} {root.target}"


def _action_label(action: EscapeRoomAction) -> str:
    action_name = action.root.action
    labels = {
        "pick_up": "pick up",
        "talk_to": "talk",
        "use_item": "use item",
        "operate": "operate",
    }
    return labels.get(action_name, action_name.replace("_", " "))


def _run_escape_turn(
    *,
    provider: InferenceProvider,
    game_state: str,
    action_model: type[BaseModel],
    history: tuple[str, ...],
    settings: ThinkActSettings | None,
) -> ThinkActResult:
    resolved_settings = ThinkActSettings() if settings is None else settings
    deliberation_response = provider.complete(
        InferenceRequest(
            messages=build_deliberation_messages(
                game_state=game_state,
                action_model=action_model,
                history=history,
            ),
            phase="deliberation",
            settings=resolved_settings.deliberation,
            enable_thinking=resolved_settings.deliberation_enable_thinking,
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
            phase="action",
            structured_output=StructuredOutputSpec.from_pydantic_model(action_model),
            settings=resolved_settings.action,
            enable_thinking=False,
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
