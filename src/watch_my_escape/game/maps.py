"""Grid map models and visibility-filtered render helpers."""

from __future__ import annotations

from collections import deque
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from pydantic import Field, ValidationError, model_validator

from watch_my_escape.game.models import (
    ActionName,
    BehaviorContext,
    BehaviorEffect,
    BehaviorResult,
    Coordinate,
    Entity,
    EntityUpdate,
    SetEntityPassableEffect,
    SetEntityPropertyEffect,
    SetEntityStateEffect,
    SetEntityVisibleEffect,
    StrictModel,
    evaluate_entity_behavior,
)

MAP_SIZE = 16


class Direction(StrEnum):
    """Cardinal movement directions."""

    NORTH = "North"
    EAST = "East"
    SOUTH = "South"
    WEST = "West"


class MoveBlockedError(ValueError):
    """Raised when movement cannot enter the requested grid cell."""


class PlacedEntity(StrictModel):
    """An entity placed at one coordinate on the map."""

    entity: Entity
    position: Coordinate


class GameMap(StrictModel):
    """A fixed-size escape-room map made from placed entities."""

    id: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    entities: tuple[PlacedEntity, ...] = ()
    agent_start: Coordinate
    width: Literal[16] = MAP_SIZE
    height: Literal[16] = MAP_SIZE

    @model_validator(mode="after")
    def validate_map(self) -> Self:
        """Validate global ids and behavior references."""
        entity_ids = [placed.entity.id for placed in self.entities]
        if len(set(entity_ids)) != len(entity_ids):
            msg = "entity ids must be unique across the map"
            raise ValueError(msg)

        self._validate_behavior_references(self.entities_by_id())
        return self

    def entities_by_id(self) -> dict[str, Entity]:
        """Return all entities keyed by global id."""
        return {placed.entity.id: placed.entity for placed in self.entities}

    def entities_at(self, position: Coordinate) -> tuple[PlacedEntity, ...]:
        """Return placed entities at one coordinate."""
        return tuple(placed for placed in self.entities if placed.position == position)

    def visible_entities(self) -> tuple[PlacedEntity, ...]:
        """Return all visible placed entities across the map."""
        return tuple(placed for placed in self.entities if placed.entity.visible)

    def _validate_behavior_references(self, entities: dict[str, Entity]) -> None:
        entity_ids = set(entities)
        for entity in entities.values():
            for behavior in entity.behaviors:
                for condition in behavior.conditions:
                    if condition.entity_id is not None and condition.entity_id not in entity_ids:
                        msg = f"entity {entity.id!r} references unknown entity {condition.entity_id!r}"
                        raise ValueError(msg)
                for effect in behavior.effects:
                    effect_entity_id = _effect_target_id(effect)
                    if effect_entity_id is not None and effect_entity_id not in entity_ids:
                        msg = f"entity {entity.id!r} references unknown entity {effect_entity_id!r}"
                        raise ValueError(msg)


class GameSessionState(StrictModel):
    """Mutable runtime state for one agent playing a map."""

    map: GameMap
    agent_position: Coordinate | None = None
    inventory: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    escaped: bool = False

    @model_validator(mode="before")
    @classmethod
    def default_agent_position(cls, data: object) -> object:
        """Default new sessions to the authored start coordinate."""
        if isinstance(data, dict):
            values = cast("dict[str, object]", data)
            game_map = values.get("map")
            if values.get("agent_position") is not None or not isinstance(game_map, GameMap):
                return data
            return {**values, "agent_position": game_map.agent_start}
        return data

    @property
    def current_position(self) -> Coordinate:
        """Return the initialized agent position."""
        if self.agent_position is None:
            msg = "agent position has not been initialized"
            raise ValueError(msg)
        return self.agent_position

    def move(self, direction: Direction) -> GameSessionState:
        """Return a new session state after moving in one direction."""
        try:
            destination = _move_coordinate(self.current_position, direction)
        except ValidationError as exc:
            msg = f"cannot move {direction}: destination is outside the map"
            raise MoveBlockedError(msg) from exc

        blockers = [placed.entity for placed in self.map.entities_at(destination) if not placed.entity.passable]
        if blockers:
            blocker_names = ", ".join(blocker.name for blocker in blockers)
            msg = f"cannot move {direction}: blocked by {blocker_names}"
            raise MoveBlockedError(msg)

        return self.model_copy(update={"agent_position": destination})

    def apply_behavior_result(self, result: BehaviorResult) -> GameSessionState:
        """Return a new session state with behavior side effects applied."""
        updated_map = _apply_entity_updates(self.map, result.entity_updates)
        inventory = tuple(item for item in self.inventory if item not in set(result.remove_inventory))
        inventory = (*inventory, *result.add_inventory)
        return self.model_copy(
            update={
                "map": updated_map,
                "inventory": inventory,
                "escaped": self.escaped or result.escaped,
            }
        )

    def evaluate_entity_action(self, entity_id: str, action: str, *, item: str | None = None) -> BehaviorResult:
        """Evaluate an action against any entity using global entity context."""
        entity = self.map.entities_by_id()[entity_id]
        return evaluate_entity_behavior(
            entity,
            action=cast("ActionName", action),
            context=BehaviorContext(entities=self.map.entities_by_id(), inventory=self.inventory),
            item=item,
        )


def render_agent_view(session: GameSessionState) -> str:
    """Render visible map cells as compact Markdown for the agent."""
    visible_tiles = visible_coordinates(session)
    visible_entities = _visible_entities_for_tiles(session, visible_tiles)
    min_x, max_x, min_y, max_y = _bounds_for(visible_tiles)
    position = session.current_position

    lines = [
        f"Position: ({position.x}, {position.y})",
        "",
        _render_visible_grid(
            session,
            visible_tiles,
            visible_entities,
            bounds=(min_x, max_x, min_y, max_y),
        ),
        "",
        "Visible entities:",
    ]
    lines.extend(_render_visible_entity_lines(visible_entities))
    return "\n".join(lines)


def render_agent_room_view(session: GameSessionState) -> str:
    """Backward-compatible alias for the agent-visible map view."""
    return render_agent_view(session)


def render_user_map_view(session: GameSessionState) -> tuple[tuple[str, ...], ...]:
    """Render the full visible 16x16 map as emoji cells for the user."""
    cells = [["." for _ in range(session.map.width)] for _ in range(session.map.height)]
    for placed in session.map.visible_entities():
        cells[placed.position.y][placed.position.x] = placed.entity.icon

    position = session.current_position
    cells[position.y][position.x] = "🙂"
    return tuple(tuple(row) for row in cells)


def visible_coordinates(session: GameSessionState) -> frozenset[Coordinate]:
    """Return coordinates visible from the agent through passable cells."""
    seen: set[Coordinate] = {session.current_position}
    queue: deque[Coordinate] = deque([session.current_position])

    while queue:
        position = queue.popleft()
        for neighbor in _neighbor_coordinates(position):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            if _can_see_through(session.map.entities_at(neighbor)):
                queue.append(neighbor)

    return frozenset(seen)


def _move_coordinate(position: Coordinate, direction: Direction) -> Coordinate:
    deltas = {
        Direction.NORTH: (0, -1),
        Direction.EAST: (1, 0),
        Direction.SOUTH: (0, 1),
        Direction.WEST: (-1, 0),
    }
    delta_x, delta_y = deltas[direction]
    return Coordinate(x=position.x + delta_x, y=position.y + delta_y)


def _neighbor_coordinates(position: Coordinate) -> tuple[Coordinate, ...]:
    neighbors: list[Coordinate] = []
    for direction in Direction:
        try:
            neighbors.append(_move_coordinate(position, direction))
        except ValidationError:
            continue
    return tuple(neighbors)


def _can_see_through(placed_entities: tuple[PlacedEntity, ...]) -> bool:
    return all(not placed.entity.visible or placed.entity.passable for placed in placed_entities)


def _visible_entities_for_tiles(
    session: GameSessionState,
    visible_tiles: frozenset[Coordinate],
) -> tuple[PlacedEntity, ...]:
    return tuple(
        placed for placed in session.map.entities if placed.entity.visible and placed.position in visible_tiles
    )


def _bounds_for(tiles: frozenset[Coordinate]) -> tuple[int, int, int, int]:
    return (
        min(tile.x for tile in tiles),
        max(tile.x for tile in tiles),
        min(tile.y for tile in tiles),
        max(tile.y for tile in tiles),
    )


def _render_visible_grid(
    session: GameSessionState,
    visible_tiles: frozenset[Coordinate],
    visible_entities: tuple[PlacedEntity, ...],
    *,
    bounds: tuple[int, int, int, int],
) -> str:
    min_x, max_x, min_y, max_y = bounds
    headers = [str(x) for x in range(min_x, max_x + 1)]
    lines = [f"| y\\x | {' | '.join(headers)} |", f"| --- | {' | '.join('---' for _ in headers)} |"]
    for y in range(min_y, max_y + 1):
        row = [
            _agent_grid_cell(session, visible_tiles, visible_entities, Coordinate(x=x, y=y))
            for x in range(min_x, max_x + 1)
        ]
        lines.append(f"| {y} | {' | '.join(row)} |")
    return "\n".join(lines)


def _agent_grid_cell(
    session: GameSessionState,
    visible_tiles: frozenset[Coordinate],
    visible_entities: tuple[PlacedEntity, ...],
    position: Coordinate,
) -> str:
    if position == session.current_position:
        return "you"
    if position not in visible_tiles:
        return "?"

    placed_entities = [placed for placed in visible_entities if placed.position == position]
    if not placed_entities:
        return "."
    if len(placed_entities) == 1:
        return placed_entities[0].entity.id
    return f"{len(placed_entities)} items"


def _render_visible_entity_lines(visible_entities: tuple[PlacedEntity, ...]) -> list[str]:
    if not visible_entities:
        return ["- None."]
    return [
        f"- ({placed.position.x}, {placed.position.y}) {placed.entity.id}: "
        f"{placed.entity.name}. {placed.entity.description}"
        for placed in sorted(visible_entities, key=lambda item: (item.position.y, item.position.x, item.entity.id))
    ]


def _apply_entity_updates(game_map: GameMap, updates: dict[str, EntityUpdate]) -> GameMap:
    if not updates:
        return game_map

    return game_map.model_copy(
        update={
            "entities": tuple(
                _updated_placed_entity(placed, updates.get(placed.entity.id)) for placed in game_map.entities
            )
        }
    )


def _updated_placed_entity(placed: PlacedEntity, update: EntityUpdate | None) -> PlacedEntity:
    if update is None:
        return placed
    return placed.model_copy(update={"entity": _updated_entity(placed.entity, update)})


def _updated_entity(entity: Entity, update: EntityUpdate) -> Entity:
    properties = {**entity.properties, **update.properties}
    data: dict[str, object] = {"properties": properties}
    if update.state is not None:
        data["state"] = update.state
    if update.passable is not None:
        data["passable"] = update.passable
    if update.visible is not None:
        data["visible"] = update.visible
    return entity.model_copy(update=data)


def _effect_target_id(effect: BehaviorEffect) -> str | None:
    if isinstance(
        effect,
        SetEntityStateEffect | SetEntityPropertyEffect | SetEntityPassableEffect | SetEntityVisibleEffect,
    ):
        return effect.entity_id
    return None
