"""Runtime helpers for applying agent actions to a game session."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from watch_my_escape.game.actions import (
    EscapeRoomAction,
    TakeNoteAction,
    TalkToAction,
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
from watch_my_escape.game.models import Coordinate, Entity

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

    if isinstance(root, UseItemAction):
        return _apply_use_item_action(session, next_sanity, root)

    target = _resolve_visible_target(session, root.target)
    if target is None:
        return AppliedAction(
            session=session,
            sanity=next_sanity,
            message=f"Cannot {root.action} {root.target!r}: no active target matches.",
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

    text = root.text if isinstance(root, TalkToAction) else None
    behavior_result = action_session.evaluate_entity_action(nearby_target.entity.id, root.action, text=text)
    updated_session = action_session.apply_behavior_result(behavior_result)
    fallback_message = f"You {root.action.replace('_', ' ')} the {nearby_target.entity.name}. Nothing happens."
    return AppliedAction(
        session=updated_session,
        sanity=next_sanity,
        message=behavior_result.text or fallback_message,
        movement_path=movement_path,
    )


def render_game_state_for_agent(session: GameSessionState, sanity: int) -> str:
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
        return "Inventory (items you are carrying):\n- Empty."
    entities = session.map.entities_by_id()
    return "Inventory (items you are carrying):\n" + "\n".join(
        f"- {_inventory_item_text(item, entities)}" for item in session.inventory
    )


def _inventory_item_text(item: str, entities: dict[str, Entity]) -> str:
    entity = entities.get(item)
    if entity is None:
        return item
    return f"{item}: {entity.name}"


def _render_journal(session: GameSessionState) -> str:
    if not session.notes:
        return "Your notes:\n- You have not recorded any notes."
    return "Your notes:\n" + "\n".join(f"- {note}" for note in session.notes)


def _session_after_path(session: GameSessionState, path: tuple[Coordinate, ...]) -> GameSessionState:
    if not path:
        return session
    return session.model_copy(update={"agent_position": path[-1]})


def _apply_use_item_action(session: GameSessionState, sanity: int, action: UseItemAction) -> AppliedAction:
    if action.item not in session.inventory:
        return AppliedAction(
            session=session,
            sanity=sanity,
            message=f"Cannot use {action.item!r}: it is not in inventory.",
        )

    inventory_target = _resolve_inventory_target(session, action.target)
    if inventory_target is not None:
        behavior_result = session.evaluate_entity_action(inventory_target.id, action.action, item=action.item)
        updated_session = session.apply_behavior_result(behavior_result)
        fallback_message = f"You use the {action.item} on the {inventory_target.name}. Nothing happens."
        return AppliedAction(session=updated_session, sanity=sanity, message=behavior_result.text or fallback_message)

    target = _resolve_visible_target(session, action.target)
    if target is None:
        return AppliedAction(
            session=session,
            sanity=sanity,
            message=f"Cannot use {action.item!r} on {action.target!r}: no active or inventory target matches.",
        )

    try:
        movement_path = path_to_visible_destination(session, target.position)
    except (ValidationError, PathNotFoundError) as exc:
        return AppliedAction(session=session, sanity=sanity, message=str(exc))

    action_session = _session_after_path(session, movement_path)
    nearby_target = _resolve_nearby_target(action_session, action.target)
    if nearby_target is None:
        return AppliedAction(
            session=session,
            sanity=sanity,
            message=f"Cannot use {action.item!r} on {action.target!r}: no reachable nearby target matches.",
        )

    behavior_result = action_session.evaluate_entity_action(nearby_target.entity.id, action.action, item=action.item)
    updated_session = action_session.apply_behavior_result(behavior_result)
    fallback_message = f"You use the {action.item} on the {nearby_target.entity.name}. Nothing happens."
    return AppliedAction(
        session=updated_session,
        sanity=sanity,
        message=behavior_result.text or fallback_message,
        movement_path=movement_path,
    )


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


def _resolve_inventory_target(session: GameSessionState, target: str) -> Entity | None:
    if target not in session.inventory:
        return None
    return session.map.entities_by_id().get(target)


def _target_matches(placed: PlacedEntity, target: str) -> bool:
    normalized_target = target.casefold()
    return placed.entity.id.casefold() == normalized_target or placed.entity.name.casefold() == normalized_target


def nearby_visible_entities(session: GameSessionState) -> tuple[PlacedEntity, ...]:
    """Return active entities on the agent tile or one cardinal step away."""
    position = session.current_position
    nearby_positions = {
        position,
        Coordinate(x=position.x, y=max(0, position.y - 1)),
        Coordinate(x=min(session.map.width - 1, position.x + 1), y=position.y),
        Coordinate(x=position.x, y=min(session.map.height - 1, position.y + 1)),
        Coordinate(x=max(0, position.x - 1), y=position.y),
    }
    return tuple(
        placed for placed in session.map.entities if placed.entity.active and placed.position in nearby_positions
    )
