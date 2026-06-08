"""Runtime helpers for applying agent actions to a game session."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from watch_my_escape.game.actions import (
    EscapeRoomAction,
    TakeNoteAction,
    UseItemAction,
)
from watch_my_escape.game.maps import (
    GameSessionState,
    PathNotFoundError,
    PlacedEntity,
    path_to_visible_destination,
    render_agent_view,
    visible_notable_entities,
)
from watch_my_escape.game.models import Coordinate

STARTING_SANITY = 100


@dataclass(frozen=True, slots=True)
class AppliedAction:
    """Result of one attempted model action."""

    session: GameSessionState
    sanity: int
    message: str
    movement_path: tuple[Coordinate, ...] = ()


def apply_agent_action(session: GameSessionState, sanity: int, action: EscapeRoomAction) -> AppliedAction:
    """Apply one model action and reduce sanity for the attempt."""
    next_sanity = max(0, sanity - 1)
    root = action.root

    if isinstance(root, TakeNoteAction):
        updated_session = session.model_copy(update={"notes": (*session.notes, root.text)})
        return AppliedAction(session=updated_session, sanity=next_sanity, message=f"Journal updated: {root.text}")

    target = _resolve_visible_target(session, root.target)
    if target is None:
        return AppliedAction(
            session=session,
            sanity=next_sanity,
            message=f"Cannot {root.action} {root.target!r}: no visible target matches.",
        )

    try:
        movement_path = path_to_visible_destination(session, target.position)
    except (ValidationError, PathNotFoundError) as exc:
        return AppliedAction(session=session, sanity=next_sanity, message=str(exc))

    action_session = _session_after_path(session, movement_path)
    nearby_target = _resolve_nearby_target(action_session, root.target)
    if nearby_target is None:
        return AppliedAction(
            session=session,
            sanity=next_sanity,
            message=f"Cannot {root.action} {root.target!r}: no reachable nearby target matches.",
        )

    item = root.item if isinstance(root, UseItemAction) else None
    behavior_result = action_session.evaluate_entity_action(nearby_target.entity.id, root.action, item=item)
    updated_session = action_session.apply_behavior_result(behavior_result)
    fallback_message = f"You {root.action.replace('_', ' ')} the {nearby_target.entity.name}. Nothing happens."
    return AppliedAction(
        session=updated_session,
        sanity=next_sanity,
        message=behavior_result.text or fallback_message,
        movement_path=movement_path,
    )


def render_room_state_for_agent(session: GameSessionState, sanity: int) -> str:
    """Render the full state the model should see before choosing an action."""
    return "\n\n".join(
        [
            f"Sanity: {sanity}/100",
            _render_inventory(session),
            _render_journal(session),
            render_agent_view(session),
        ]
    )


def _render_inventory(session: GameSessionState) -> str:
    if not session.inventory:
        return "Inventory:\n- Empty."
    return "Inventory:\n" + "\n".join(f"- {item}" for item in session.inventory)


def _render_journal(session: GameSessionState) -> str:
    if not session.notes:
        return "Journal:\n- No notes recorded."
    return "Journal:\n" + "\n".join(f"- {note}" for note in session.notes)


def _session_after_path(session: GameSessionState, path: tuple[Coordinate, ...]) -> GameSessionState:
    if not path:
        return session
    return session.model_copy(update={"agent_position": path[-1]})


def _resolve_nearby_target(session: GameSessionState, target: str) -> PlacedEntity | None:
    for placed in nearby_visible_entities(session):
        if _target_matches(placed, target):
            return placed
    return None


def _resolve_visible_target(session: GameSessionState, target: str) -> PlacedEntity | None:
    for placed in visible_notable_entities(session):
        if _target_matches(placed, target):
            return placed
    return None


def _target_matches(placed: PlacedEntity, target: str) -> bool:
    normalized_target = target.casefold()
    return placed.entity.id.casefold() == normalized_target or placed.entity.name.casefold() == normalized_target


def nearby_visible_entities(session: GameSessionState) -> tuple[PlacedEntity, ...]:
    """Return visible entities on the agent tile or one cardinal step away."""
    position = session.current_position
    nearby_positions = {
        position,
        Coordinate(x=position.x, y=max(0, position.y - 1)),
        Coordinate(x=min(session.map.width - 1, position.x + 1), y=position.y),
        Coordinate(x=position.x, y=min(session.map.height - 1, position.y + 1)),
        Coordinate(x=max(0, position.x - 1), y=position.y),
    }
    return tuple(
        placed for placed in session.map.entities if placed.entity.visible and placed.position in nearby_positions
    )
