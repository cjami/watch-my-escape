"""Run a model through an escape-room game map."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

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
from watch_my_escape.game.runtime import (
    STARTING_SANITY,
    ActionEffectSummary,
    AppliedAction,
    apply_agent_action,
    render_game_state_for_agent,
)
from watch_my_escape.llm.client import InferenceProvider, create_provider
from watch_my_escape.llm.models import InferenceRequest, StructuredOutputSpec
from watch_my_escape.llm.structured import StructuredOutputError, strip_thinking_sections, validate_structured_output

if TYPE_CHECKING:
    from collections.abc import Iterator

    from watch_my_escape.game.maps import GameMap
    from watch_my_escape.game.models import Entity

DEFAULT_MAP_ID = "key-door-room"
ACTION_EMOJIS = {
    "close": "↩️",
    "examine": "🔍",
    "invalid": "⚠️",
    "none": "·",
    "open": "🚪",
    "operate": "⚙️",
    "pick_up": "🖐️",
    "pull": "⬇️",
    "push": "⬆️",
    "talk_to": "💬",
    "use_item": "🧰",
}


@dataclass(frozen=True, slots=True)
class EntityDisplay:
    """Browser-facing display metadata for one visible or carried entity."""

    id: str
    icon: str
    description: str
    color: str | None = None


@dataclass(frozen=True, slots=True)
class TranscriptIntroEvent:
    """Initial room context shown before the first turn."""

    visible_entities: tuple[EntityDisplay, ...]
    message: str = ""
    kind: Literal["intro"] = "intro"


@dataclass(frozen=True, slots=True)
class TranscriptTurnEvent:
    """Browser-facing transcript details for one model turn."""

    turn_number: int
    sanity_before: int
    sanity_after: int
    deliberation: str
    action_type: str
    action_emoji: str
    action_text: str
    result: str
    effects: tuple[ActionEffectSummary, ...] = ()
    spoken_text: str | None = None
    kind: Literal["turn"] = "turn"


type TranscriptEvent = TranscriptIntroEvent | TranscriptTurnEvent


@dataclass(frozen=True, slots=True)
class TranscriptLog:
    """Accumulated legacy and structured transcript output."""

    entries: list[str]
    events: list[TranscriptEvent]


@dataclass(frozen=True, slots=True)
class TranscriptTurnContext:
    """Shared turn metadata for transcript output."""

    turn_number: int
    sanity_before: int
    sanity_after: int


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
    transcript_events: tuple[TranscriptEvent, ...] = ()


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
    transcript_events: tuple[TranscriptEvent, ...] = ()


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
        transcript_events=final_frame.transcript_events,
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
    selected_map = _selected_escape_map(game_map)
    session = GameSessionState(map=selected_map)
    sanity = starting_sanity
    history: list[str] = []
    transcript = TranscriptLog(entries=[], events=[_intro_event(session)])

    yield _frame(
        session,
        sanity,
        transcript,
        "Model run started.",
        presentation=FramePresentation(delay_ms=startup_delay_ms),
    )

    while sanity > 0 and not session.escaped:
        turn_number = len(transcript.entries) + 1
        game_state = render_game_state_for_agent(session, sanity)
        action_model = build_available_action_model(session)
        if action_model is None:
            status = "No available actions remain before the model escaped."
            turn_context = TranscriptTurnContext(turn_number, sanity, sanity)
            _record_no_action_turn(transcript, turn_context, status=status)
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
            turn_context = TranscriptTurnContext(turn_number, sanity, next_sanity)
            _record_invalid_action_turn(
                transcript,
                turn_context,
                deliberation=exc.deliberation,
                message=message,
            )
            history.append(f"Invalid action -> {message}")
            sanity = next_sanity
            yield _frame(
                session,
                sanity,
                transcript,
                _status(escaped=session.escaped, sanity=sanity),
            )
            continue
        action = EscapeRoomAction.model_validate(result.action.model_dump(mode="json"))
        applied = apply_agent_action(session, sanity, action)
        action_emotion = emotion_to_emoji(action.root.emotion)
        action_label = _action_label(action)
        turn_context = TranscriptTurnContext(turn_number, sanity, applied.sanity)
        _record_action_turn(
            transcript,
            turn_context,
            action=action,
            deliberation=result.deliberation,
            applied=applied,
        )
        history.append(f"{_history_action_text(action)} -> {_history_result_text(applied)}")
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

    if not transcript.entries:
        yield _frame(session, sanity, transcript, _status(escaped=session.escaped, sanity=sanity))


def _selected_escape_map(game_map: GameMap | None) -> GameMap:
    if game_map is not None:
        return game_map
    return get_premade_map(DEFAULT_MAP_ID).map


def _frame(
    session: GameSessionState,
    sanity: int,
    transcript: TranscriptLog,
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
        transcript="\n\n".join(transcript.entries),
        transcript_events=tuple(transcript.events),
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


def _record_no_action_turn(transcript: TranscriptLog, context: TranscriptTurnContext, *, status: str) -> None:
    transcript.entries.append(
        "\n".join(
            [
                _turn_header(context),
                "Action: none",
                f"Result: {status}",
            ]
        )
    )
    transcript.events.append(
        TranscriptTurnEvent(
            turn_number=context.turn_number,
            sanity_before=context.sanity_before,
            sanity_after=context.sanity_after,
            deliberation="",
            action_type="none",
            action_emoji=ACTION_EMOJIS["none"],
            action_text="No action available",
            result=status,
        )
    )


def _record_invalid_action_turn(
    transcript: TranscriptLog,
    context: TranscriptTurnContext,
    *,
    deliberation: str,
    message: str,
) -> None:
    transcript.entries.append(
        "\n".join(
            [
                _turn_header(context),
                *_deliberation_lines(deliberation),
                "Action: invalid",
                f"Result: {message}",
            ]
        )
    )
    transcript.events.append(
        TranscriptTurnEvent(
            turn_number=context.turn_number,
            sanity_before=context.sanity_before,
            sanity_after=context.sanity_after,
            deliberation=_deliberation_text(deliberation),
            action_type="invalid",
            action_emoji=ACTION_EMOJIS["invalid"],
            action_text="Invalid action",
            result=message,
        )
    )


def _record_action_turn(
    transcript: TranscriptLog,
    context: TranscriptTurnContext,
    *,
    action: EscapeRoomAction,
    deliberation: str,
    applied: AppliedAction,
) -> None:
    action_text = _action_text(action)
    transcript.entries.append(
        "\n".join(
            [
                _turn_header(context),
                *_deliberation_lines(deliberation),
                f"Action: {action_text}",
                *_result_lines(applied),
            ]
        )
    )
    transcript.events.append(
        TranscriptTurnEvent(
            turn_number=context.turn_number,
            sanity_before=context.sanity_before,
            sanity_after=context.sanity_after,
            deliberation=_deliberation_text(deliberation),
            action_type=action.root.action,
            action_emoji=_action_emoji(action.root.action),
            action_text=action_text,
            result=applied.message,
            effects=applied.effects,
            spoken_text=getattr(action.root, "text", None),
        )
    )


def _result_lines(applied: AppliedAction) -> tuple[str, ...]:
    lines: list[str] = []
    if applied.message:
        lines.append(f"Result: {applied.message}")
    lines.extend(f"Effect: {effect.text}" for effect in applied.effects)
    return tuple(lines)


def _turn_header(context: TranscriptTurnContext) -> str:
    return f"Turn {context.turn_number} - sanity {context.sanity_before} -> {context.sanity_after}"


def _deliberation_lines(deliberation: str) -> tuple[str, ...]:
    stripped = _deliberation_text(deliberation)
    if not stripped:
        return ()
    return (f"Deliberation: {stripped}",)


def _deliberation_text(deliberation: str) -> str:
    return strip_thinking_sections(deliberation).strip()


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


def _intro_event(session: GameSessionState) -> TranscriptIntroEvent:
    return TranscriptIntroEvent(visible_entities=_visible_entity_details(session))


def _entity_description(entity: Entity) -> str:
    return render_state_template(entity.description, entity.state)


def _action_text(action: EscapeRoomAction) -> str:
    root = action.root
    if root.action == "talk_to":
        return f"Talk to {root.target}"
    if root.action == "use_item":
        return f"Use {root.item} on {root.target}"
    action_phrases = {
        "close": "Close",
        "examine": "Examine",
        "open": "Open",
        "operate": "Operate",
        "pick_up": "Pick up",
        "pull": "Pull",
        "push": "Push",
    }
    return f"{action_phrases[root.action]} {root.target}"


def _action_emoji(action_type: str) -> str:
    return ACTION_EMOJIS.get(action_type, ACTION_EMOJIS["invalid"])


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


def _history_result_text(applied: AppliedAction) -> str:
    parts = [applied.message, *(effect.text for effect in applied.effects)]
    return " ".join(part for part in parts if part)


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
