"""Escape-room game state models."""

from __future__ import annotations

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

type JsonScalar = str | int | float | bool | None
type ActionName = Literal["examine", "pick_up", "open", "close", "push", "pull", "talk_to", "use", "use_item"]
type EntityPropertyUpdates = dict[str, JsonScalar]


class StrictModel(BaseModel):
    """Base for room JSON models that should reject unknown fields."""

    model_config = ConfigDict(extra="forbid")


class Coordinate(StrictModel):
    """A location on the 16x16 map grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: Annotated[int, Field(ge=0, le=15)]
    y: Annotated[int, Field(ge=0, le=15)]


class BehaviorTrigger(StrictModel):
    """Agent action that can trigger an entity behavior."""

    action: ActionName
    item: Annotated[str | None, Field(default=None, min_length=1)] = None
    phrase: Annotated[str | None, Field(default=None, min_length=1)] = None


class BehaviorCondition(StrictModel):
    """Required entity state or property value for a behavior to run."""

    entity_id: Annotated[str | None, Field(default=None, min_length=1)] = None
    state: Annotated[str | None, Field(default=None, min_length=1)] = None
    property: Annotated[str | None, Field(default=None, min_length=1)] = None
    equals: JsonScalar = None


class MessageEffect(StrictModel):
    """Append response text to the behavior result."""

    type: Literal["message"]
    text: Annotated[str, Field(min_length=1)]


class AddInventoryEffect(StrictModel):
    """Request that an item be added to the agent inventory."""

    type: Literal["add_inventory"]
    entity_id: Annotated[str, Field(min_length=1)]


class RemoveInventoryEffect(StrictModel):
    """Request that an item be removed from the agent inventory."""

    type: Literal["remove_inventory"]
    entity_id: Annotated[str, Field(min_length=1)]


class SetEntityStateEffect(StrictModel):
    """Request that an entity state be changed."""

    type: Literal["set_entity_state"]
    state: Annotated[str, Field(min_length=1)]
    entity_id: Annotated[str | None, Field(default=None, min_length=1)] = None


class SetEntityPropertyEffect(StrictModel):
    """Request that an entity property be changed."""

    type: Literal["set_entity_property"]
    property: Annotated[str, Field(min_length=1)]
    value: JsonScalar
    entity_id: Annotated[str | None, Field(default=None, min_length=1)] = None


class SetEntityPassableEffect(StrictModel):
    """Request that an entity passability flag be changed."""

    type: Literal["set_entity_passable"]
    passable: bool
    entity_id: Annotated[str | None, Field(default=None, min_length=1)] = None


class SetEntityActiveEffect(StrictModel):
    """Request that an entity active flag be changed."""

    type: Literal["set_entity_active"]
    active: bool
    entity_id: Annotated[str | None, Field(default=None, min_length=1)] = None


class EscapeMapEffect(StrictModel):
    """Request that the active session is marked as escaped."""

    type: Literal["escape_map"]


type BehaviorEffect = Annotated[
    MessageEffect
    | AddInventoryEffect
    | RemoveInventoryEffect
    | SetEntityStateEffect
    | SetEntityPropertyEffect
    | SetEntityPassableEffect
    | SetEntityActiveEffect
    | EscapeMapEffect,
    Field(discriminator="type"),
]


class EntityBehavior(StrictModel):
    """Declarative reaction to an agent action."""

    trigger: BehaviorTrigger
    conditions: tuple[BehaviorCondition, ...] = ()
    effects: tuple[BehaviorEffect, ...] = ()


class Entity(StrictModel):
    """A room object that can occupy a map spot and react to actions."""

    id: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    icon: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    passable: bool
    active: bool = True
    notable: bool = True
    state: Annotated[str, Field(min_length=1)] = "default"
    properties: dict[str, JsonScalar] = Field(default_factory=dict)
    behaviors: tuple[EntityBehavior, ...] = ()


class EntityUpdate(StrictModel):
    """Requested changes for one entity after behavior evaluation."""

    state: str | None = None
    passable: bool | None = None
    active: bool | None = None
    properties: EntityPropertyUpdates = Field(default_factory=dict)


class BehaviorResult(StrictModel):
    """Outcome of evaluating entity behavior."""

    messages: tuple[str, ...] = ()
    add_inventory: tuple[str, ...] = ()
    remove_inventory: tuple[str, ...] = ()
    entity_updates: dict[str, EntityUpdate] = Field(default_factory=dict)
    escaped: bool = False

    @property
    def text(self) -> str:
        """Return response messages as a single paragraph."""
        return " ".join(self.messages)


class BehaviorContext(StrictModel):
    """State available while evaluating an entity behavior."""

    entities: dict[str, Entity]
    inventory: tuple[str, ...] = ()


class BehaviorHandler(Protocol):
    """Extension point for Python-backed behavior handlers."""

    def evaluate(
        self,
        *,
        entity: Entity,
        action: ActionName,
        context: BehaviorContext,
        item: str | None = None,
    ) -> BehaviorResult:
        """Evaluate behavior for one entity and action."""


class _BehaviorAccumulator:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.add_inventory: list[str] = []
        self.remove_inventory: list[str] = []
        self.entity_updates: dict[str, EntityUpdate] = {}
        self.escaped = False

    def to_result(self) -> BehaviorResult:
        return BehaviorResult(
            messages=tuple(self.messages),
            add_inventory=tuple(self.add_inventory),
            remove_inventory=tuple(self.remove_inventory),
            entity_updates=self.entity_updates,
            escaped=self.escaped,
        )


def evaluate_entity_behavior(
    entity: Entity,
    *,
    action: ActionName,
    context: BehaviorContext,
    item: str | None = None,
    text: str | None = None,
) -> BehaviorResult:
    """Evaluate declarative behaviors for one entity and action."""
    accumulator = _BehaviorAccumulator()

    for behavior in entity.behaviors:
        if not _trigger_matches(behavior.trigger, action=action, item=item, text=text):
            continue
        if not all(
            _condition_matches(condition, current_entity=entity, entities=context.entities)
            for condition in behavior.conditions
        ):
            continue

        for effect in behavior.effects:
            _apply_effect(effect, current_entity=entity, accumulator=accumulator)

    return accumulator.to_result()


def _trigger_matches(trigger: BehaviorTrigger, *, action: ActionName, item: str | None, text: str | None) -> bool:
    if trigger.action != action:
        return False
    if trigger.item is not None and trigger.item != item:
        return False
    return trigger.phrase is None or _normalized_phrase(trigger.phrase) in _normalized_phrase(text or "")


def _normalized_phrase(value: str) -> str:
    return "".join(value.casefold().strip().split())


def _condition_matches(
    condition: BehaviorCondition,
    *,
    current_entity: Entity,
    entities: dict[str, Entity],
) -> bool:
    entity = current_entity if condition.entity_id is None else entities.get(condition.entity_id)
    if entity is None:
        return False
    if condition.state is not None and entity.state != condition.state:
        return False
    return condition.property is None or entity.properties.get(condition.property) == condition.equals


def _apply_effect(
    effect: BehaviorEffect,
    *,
    current_entity: Entity,
    accumulator: _BehaviorAccumulator,
) -> None:
    if isinstance(effect, MessageEffect):
        accumulator.messages.append(effect.text)
        return
    if isinstance(effect, AddInventoryEffect):
        accumulator.add_inventory.append(effect.entity_id)
        return
    if isinstance(effect, RemoveInventoryEffect):
        accumulator.remove_inventory.append(effect.entity_id)
        return
    if isinstance(effect, EscapeMapEffect):
        accumulator.escaped = True
        return

    update = accumulator.entity_updates.setdefault(_effect_entity_id(effect, current_entity), EntityUpdate())
    if isinstance(effect, SetEntityStateEffect):
        update.state = effect.state
    elif isinstance(effect, SetEntityPropertyEffect):
        update.properties[effect.property] = effect.value
    elif isinstance(effect, SetEntityPassableEffect):
        update.passable = effect.passable
    elif isinstance(effect, SetEntityActiveEffect):
        update.active = effect.active


def _effect_entity_id(
    effect: SetEntityStateEffect | SetEntityPropertyEffect | SetEntityPassableEffect | SetEntityActiveEffect,
    current_entity: Entity,
) -> str:
    return effect.entity_id or current_entity.id
