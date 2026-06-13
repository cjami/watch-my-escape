"""Runtime helpers for applying agent actions to a game session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from watch_my_escape.game.actions import (
    EscapeRoomAction,
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
from watch_my_escape.game.models import BehaviorResult, Coordinate, Entity, render_state_template

STARTING_SANITY = 100
DEFAULT_NO_EFFECT_MESSAGE = "Nothing happens."


@dataclass(frozen=True, slots=True)
class ActionEffectSummary:
    """User-facing summary of a non-message behavior effect."""

    kind: Literal[
        "add_inventory",
        "remove_inventory",
        "set_entity_active",
        "set_entity_passable",
        "set_entity_state",
        "escape",
    ]
    text: str
    entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class AppliedAction:
    """Result of one attempted model action."""

    session: GameSessionState
    sanity: int
    message: str
    movement_path: tuple[Coordinate, ...] = ()
    effects: tuple[ActionEffectSummary, ...] = ()


def apply_agent_action(session: GameSessionState, sanity: int, action: EscapeRoomAction) -> AppliedAction:
    """Apply one model action and reduce sanity for the attempt."""
    next_sanity = max(0, sanity - 1)
    root = action.root

    if isinstance(root, UseItemAction):
        return _apply_use_item_action(session, next_sanity, root)

    inventory_target = _resolve_inventory_target(session, root.target)
    if inventory_target is not None and root.action != "pick_up":
        text = root.text if isinstance(root, TalkToAction) else None
        behavior_result = session.evaluate_entity_action(inventory_target.id, root.action, text=text)
        return _applied_behavior_action(session, next_sanity, behavior_result)

    target = _resolve_visible_target(session, root.target)
    if target is None:
        return AppliedAction(
            session=session,
            sanity=next_sanity,
            message=f"Cannot {root.action} {root.target!r}: no active or inventory target matches.",
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
    return _applied_behavior_action(action_session, next_sanity, behavior_result, movement_path=movement_path)


def render_game_state_for_agent(session: GameSessionState, sanity: int) -> str:
    """Render the full state the model should see before choosing an action."""
    return "\n\n".join(
        [
            f"Sanity: {sanity}/100",
            render_agent_view(session),
            _render_inventory(session),
        ]
    )


def _render_inventory(session: GameSessionState) -> str:
    if not session.inventory:
        return "Inventory (items you are carrying):\n- Empty."
    entities = session.map.entities_by_id()
    return "Inventory (items you are carrying):\n" + "\n".join(
        _render_inventory_item(item, entities) for item in session.inventory
    )


def _render_inventory_item(item: str, entities: dict[str, Entity]) -> str:
    entity = entities.get(item)
    if entity is None:
        return f"- {item}"
    return f"- {item}: {_render_entity_description(entity)}"


def _render_entity_description(entity: Entity) -> str:
    return render_state_template(entity.description, entity.state)


def _session_after_path(session: GameSessionState, path: tuple[Coordinate, ...]) -> GameSessionState:
    if not path:
        return session
    return session.model_copy(update={"agent_position": path[-1]})


def _applied_behavior_action(
    session: GameSessionState,
    sanity: int,
    behavior_result: BehaviorResult,
    *,
    movement_path: tuple[Coordinate, ...] = (),
) -> AppliedAction:
    effects = _effect_summaries(behavior_result)
    return AppliedAction(
        session=session.apply_behavior_result(behavior_result),
        sanity=sanity,
        message=_behavior_message(behavior_result, effects),
        movement_path=movement_path,
        effects=effects,
    )


def _behavior_message(result: BehaviorResult, effects: tuple[ActionEffectSummary, ...]) -> str:
    if result.text:
        return result.text
    if effects:
        return ""
    return DEFAULT_NO_EFFECT_MESSAGE


def _effect_summaries(result: BehaviorResult) -> tuple[ActionEffectSummary, ...]:
    summaries: list[ActionEffectSummary] = []
    summaries.extend(
        ActionEffectSummary(
            kind="add_inventory",
            entity_id=entity_id,
            text=f"Added {entity_id} to inventory.",
        )
        for entity_id in result.add_inventory
    )
    summaries.extend(
        ActionEffectSummary(
            kind="remove_inventory",
            entity_id=entity_id,
            text=f"Removed {entity_id} from inventory.",
        )
        for entity_id in result.remove_inventory
    )
    for entity_id, update in result.entity_updates.items():
        if update.state is not None:
            summaries.append(
                ActionEffectSummary(
                    kind="set_entity_state",
                    entity_id=entity_id,
                    text=f"{entity_id} state changed to {update.state}.",
                )
            )
        if update.passable is not None:
            summaries.append(
                ActionEffectSummary(
                    kind="set_entity_passable",
                    entity_id=entity_id,
                    text=f"{entity_id} became {_passable_text(passable=update.passable)}.",
                )
            )
        if update.active is not None:
            summaries.append(
                ActionEffectSummary(
                    kind="set_entity_active",
                    entity_id=entity_id,
                    text=f"{entity_id} became {_active_text(active=update.active)}.",
                )
            )
    if result.escaped:
        summaries.append(ActionEffectSummary(kind="escape", entity_id=None, text="Escape triggered."))
    return tuple(summaries)


def _passable_text(*, passable: bool) -> str:
    return "passable" if passable else "impassable"


def _active_text(*, active: bool) -> str:
    return "active" if active else "inactive"


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
        return _applied_behavior_action(session, sanity, behavior_result)

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
    return _applied_behavior_action(action_session, sanity, behavior_result, movement_path=movement_path)


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
    return placed.entity.id.casefold() == target.casefold()


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
