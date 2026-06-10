"""Grid map models and visibility-filtered render helpers."""

from __future__ import annotations

from collections import deque
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from pydantic import Field, ValidationError, model_validator

from watch_my_escape.game.models import (
    ActionName,
    AddInventoryEffect,
    BehaviorContext,
    BehaviorEffect,
    BehaviorResult,
    Coordinate,
    Entity,
    EntityUpdate,
    RemoveInventoryEffect,
    SetEntityActiveEffect,
    SetEntityPassableEffect,
    SetEntityStateEffect,
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


class PathNotFoundError(ValueError):
    """Raised when no active reachable path exists for a requested destination."""


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

        positions = [placed.position for placed in self.entities]
        if len(set(positions)) != len(positions):
            msg = "only one entity may be placed on each map tile"
            raise ValueError(msg)

        self._validate_behavior_references(self.entities_by_id())
        return self

    def entities_by_id(self) -> dict[str, Entity]:
        """Return all entities keyed by global id."""
        return {placed.entity.id: placed.entity for placed in self.entities}

    def entities_at(self, position: Coordinate) -> tuple[PlacedEntity, ...]:
        """Return placed entities at one coordinate."""
        return tuple(placed for placed in self.entities if placed.position == position)

    def active_entities(self) -> tuple[PlacedEntity, ...]:
        """Return all active placed entities across the map."""
        return tuple(placed for placed in self.entities if placed.entity.active)

    def _validate_behavior_references(self, entities: dict[str, Entity]) -> None:
        entity_ids = set(entities)
        for entity in entities.values():
            for behavior in entity.behaviors:
                if behavior.trigger.item is not None and behavior.trigger.item not in entity_ids:
                    msg = f"entity {entity.id!r} references unknown inventory entity {behavior.trigger.item!r}"
                    raise ValueError(msg)
                for condition in behavior.conditions:
                    if condition.entity_id is not None and condition.entity_id not in entity_ids:
                        msg = f"entity {entity.id!r} references unknown entity {condition.entity_id!r}"
                        raise ValueError(msg)
                for effect in behavior.effects:
                    if (
                        isinstance(effect, AddInventoryEffect | RemoveInventoryEffect)
                        and effect.entity_id not in entity_ids
                    ):
                        msg = f"entity {entity.id!r} references unknown inventory entity {effect.entity_id!r}"
                        raise ValueError(msg)
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

        blockers = [
            placed.entity
            for placed in self.map.entities_at(destination)
            if placed.entity.active and not placed.entity.passable
        ]
        if blockers:
            blocker_names = ", ".join(blocker.name for blocker in blockers)
            msg = f"cannot move {direction}: blocked by {blocker_names}"
            raise MoveBlockedError(msg)

        return self.model_copy(update={"agent_position": destination})

    def apply_behavior_result(self, result: BehaviorResult) -> GameSessionState:
        """Return a new session state with behavior side effects applied."""
        updated_map = _apply_entity_updates(self.map, result.entity_updates)
        inventory = tuple(item for item in self.inventory if item not in set(result.remove_inventory))
        inventory = tuple(dict.fromkeys((*inventory, *result.add_inventory)))
        return self.model_copy(
            update={
                "map": updated_map,
                "inventory": inventory,
                "escaped": self.escaped or result.escaped,
            }
        )

    def evaluate_entity_action(
        self, entity_id: str, action: str, *, item: str | None = None, text: str | None = None
    ) -> BehaviorResult:
        """Evaluate an action against any entity using global entity context."""
        entity = self.map.entities_by_id()[entity_id]
        return evaluate_entity_behavior(
            entity,
            action=cast("ActionName", action),
            context=BehaviorContext(entities=self.map.entities_by_id(), inventory=self.inventory),
            item=item,
            text=text,
        )


def render_agent_view(session: GameSessionState) -> str:
    """Render active notable entities as compact Markdown for the agent."""
    visible_entities = visible_notable_entities(session)

    lines = [
        "Surrounding objects:",
    ]
    lines.extend(_render_visible_entity_lines(visible_entities))
    return "\n".join(lines)


def render_agent_room_view(session: GameSessionState) -> str:
    """Backward-compatible alias for the agent-visible map view."""
    return render_agent_view(session)


def render_user_map_view(session: GameSessionState, *, agent_icon: str = "\U0001f642") -> tuple[tuple[str, ...], ...]:
    """Render the full active 16x16 map as emoji cells for the user."""
    cells = [["." for _ in range(session.map.width)] for _ in range(session.map.height)]
    for placed in session.map.active_entities():
        cells[placed.position.y][placed.position.x] = placed.entity.icon

    position = session.current_position
    cells[position.y][position.x] = agent_icon
    return tuple(tuple(row) for row in cells)


def render_visibility_view(session: GameSessionState) -> tuple[tuple[bool, ...], ...]:
    """Render which full-map cells are currently visible to the agent."""
    return _render_coordinate_mask(session, visible_coordinates(session))


def render_user_visibility_view(session: GameSessionState) -> tuple[tuple[bool, ...], ...]:
    """Render the visibility mask used for the spectator map."""
    agent_visible_tiles = visible_coordinates(session)
    visible_tiles = set(agent_visible_tiles)
    visible_tiles.update(
        placed.position
        for placed in session.map.active_entities()
        if not placed.entity.notable and _completes_visible_corner(placed.position, agent_visible_tiles)
    )
    return _render_coordinate_mask(session, visible_tiles)


def _render_coordinate_mask(
    session: GameSessionState, coordinates: frozenset[Coordinate] | set[Coordinate]
) -> tuple[tuple[bool, ...], ...]:
    return tuple(
        tuple(Coordinate(x=x, y=y) in coordinates for x in range(session.map.width)) for y in range(session.map.height)
    )


def _completes_visible_corner(position: Coordinate, visible_tiles: frozenset[Coordinate]) -> bool:
    corner_pairs = (
        (Direction.NORTH, Direction.EAST),
        (Direction.EAST, Direction.SOUTH),
        (Direction.SOUTH, Direction.WEST),
        (Direction.WEST, Direction.NORTH),
    )
    for first_direction, second_direction in corner_pairs:
        first_neighbor = _optional_move_coordinate(position, first_direction)
        second_neighbor = _optional_move_coordinate(position, second_direction)
        if first_neighbor in visible_tiles and second_neighbor in visible_tiles:
            return True
    return False


def _optional_move_coordinate(position: Coordinate, direction: Direction) -> Coordinate | None:
    try:
        return _move_coordinate(position, direction)
    except ValidationError:
        return None


def visible_coordinates(session: GameSessionState) -> frozenset[Coordinate]:
    """Return coordinates active from the agent through passable cells."""
    reachable_tiles = reachable_coordinates(session)
    visible_tiles = set(reachable_tiles)

    for position in reachable_tiles:
        visible_tiles.update(_neighbor_coordinates(position))

    return frozenset(visible_tiles)


def reachable_coordinates(session: GameSessionState) -> frozenset[Coordinate]:
    """Return coordinates reachable from the agent through active passable entities."""
    seen: set[Coordinate] = {session.current_position}
    queue: deque[Coordinate] = deque([session.current_position])

    while queue:
        position = queue.popleft()
        for neighbor in _neighbor_coordinates(position):
            if neighbor in seen:
                continue
            if _is_passable(session.map.entities_at(neighbor)):
                seen.add(neighbor)
                queue.append(neighbor)

    return frozenset(seen)


def visible_notable_entities(session: GameSessionState) -> tuple[PlacedEntity, ...]:
    """Return active notable entities not sealed away from the agent."""
    visible_tiles = visible_coordinates(session)
    return tuple(
        placed
        for placed in session.map.entities
        if placed.entity.active and placed.entity.notable and placed.position in visible_tiles
    )


def path_to_visible_destination(session: GameSessionState, destination: Coordinate) -> tuple[Coordinate, ...]:
    """Return the shortest step path to a active notable destination or its edge."""
    visible_targets = tuple(placed for placed in visible_notable_entities(session) if placed.position == destination)
    if not visible_targets:
        msg = f"no active notable entity at ({destination.x}, {destination.y})"
        raise PathNotFoundError(msg)

    if _is_passable(session.map.entities_at(destination)):
        goals = (destination,)
    else:
        goals = tuple(
            neighbor
            for neighbor in _neighbor_coordinates(destination)
            if _is_passable(session.map.entities_at(neighbor))
        )

    path = _shortest_path(session, goals)
    if path is None:
        msg = f"no reachable path to ({destination.x}, {destination.y})"
        raise PathNotFoundError(msg)
    return path


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


def _is_passable(placed_entities: tuple[PlacedEntity, ...]) -> bool:
    return all(not placed.entity.active or placed.entity.passable for placed in placed_entities)


def _shortest_path(session: GameSessionState, goals: tuple[Coordinate, ...]) -> tuple[Coordinate, ...] | None:
    goal_set = set(goals)
    if session.current_position in goal_set:
        return ()

    seen: set[Coordinate] = {session.current_position}
    queue: deque[tuple[Coordinate, tuple[Coordinate, ...]]] = deque([(session.current_position, ())])

    while queue:
        position, path = queue.popleft()
        for neighbor in _neighbor_coordinates(position):
            if neighbor in seen or not _is_passable(session.map.entities_at(neighbor)):
                continue
            next_path = (*path, neighbor)
            if neighbor in goal_set:
                return next_path
            seen.add(neighbor)
            queue.append((neighbor, next_path))

    return None


def _render_visible_entity_lines(visible_entities: tuple[PlacedEntity, ...]) -> list[str]:
    notable_entities = tuple(placed for placed in visible_entities if placed.entity.notable)
    if not notable_entities:
        return ["- None."]
    return [
        f"- {placed.entity.id}: {placed.entity.name}. {_render_entity_description(placed.entity)}"
        for placed in sorted(notable_entities, key=lambda item: (item.position.y, item.position.x, item.entity.id))
    ]


def _render_entity_description(entity: Entity) -> str:
    return entity.description.replace("{state}", entity.state)


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
    data: dict[str, object] = {}
    if update.state is not None:
        data["state"] = update.state
    if update.passable is not None:
        data["passable"] = update.passable
    if update.active is not None:
        data["active"] = update.active
    return entity.model_copy(update=data)


def _effect_target_id(effect: BehaviorEffect) -> str | None:
    if isinstance(
        effect,
        SetEntityStateEffect | SetEntityPassableEffect | SetEntityActiveEffect,
    ):
        return effect.entity_id
    return None
