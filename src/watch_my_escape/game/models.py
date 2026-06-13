"""Escape-room game state models."""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

type ActionName = Literal["examine", "pick_up", "open", "close", "push", "pull", "talk_to", "operate", "use_item"]
type SimpleActionName = Literal["examine", "pick_up", "open", "close", "push", "pull", "operate"]
type HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
MAP_SIZE: Final = 15
MAX_COORDINATE: Final = MAP_SIZE - 1
STATE_PLACEHOLDER_PATTERN: Final = re.compile(r"\{state\}", re.IGNORECASE)


class StrictModel(BaseModel):
    """Base for room JSON models that should reject unknown fields."""

    model_config = ConfigDict(extra="forbid")


class Coordinate(StrictModel):
    """A location on the 15x15 map grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: Annotated[int, Field(ge=0, le=MAX_COORDINATE)]
    y: Annotated[int, Field(ge=0, le=MAX_COORDINATE)]


class BehaviorTrigger(StrictModel):
    """Agent action that can trigger an entity behavior."""

    action: ActionName
    actions: tuple[SimpleActionName, ...] = ()
    item: Annotated[str | None, Field(default=None, min_length=1)] = None
    phrase: Annotated[str | None, Field(default=None, min_length=1)] = None

    @model_validator(mode="after")
    def validate_trigger_shape(self) -> Self:
        """Ensure expanded action lists are only used by simple triggers."""
        if len(set(self.actions)) != len(self.actions):
            msg = "trigger actions must not contain duplicates"
            raise ValueError(msg)
        if self.actions:
            if self.action not in self.actions:
                msg = "trigger action must be included in trigger actions"
                raise ValueError(msg)
            if self.item is not None or self.phrase is not None:
                msg = "trigger actions cannot be combined with item or phrase matching"
                raise ValueError(msg)
        if self.item is not None and self.action != "use_item":
            msg = "trigger item can only be used with use_item"
            raise ValueError(msg)
        if self.phrase is not None and self.action != "talk_to":
            msg = "trigger phrase can only be used with talk_to"
            raise ValueError(msg)
        return self

    @property
    def action_names(self) -> tuple[ActionName, ...]:
        """Return every action name that can activate this trigger."""
        return self.actions or (self.action,)


class BehaviorCondition(StrictModel):
    """Required entity state for a behavior to run."""

    entity_id: Annotated[str | None, Field(default=None, min_length=1)] = None
    state: Annotated[str | None, Field(default=None, min_length=1)] = None


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
    icon: Annotated[str, Field(min_length=1)]
    color: HexColor | None = None
    description: Annotated[str, Field(min_length=1)]
    passable: bool
    active: bool = True
    notable: bool = True
    state: Annotated[str, Field(min_length=1)] = "default"
    behaviors: tuple[EntityBehavior, ...] = ()


class EntityUpdate(StrictModel):
    """Requested changes for one entity after behavior evaluation."""

    state: str | None = None
    passable: bool | None = None
    active: bool | None = None


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
    if action not in trigger.action_names:
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
    return condition.state is None or entity.state.casefold() == condition.state.casefold()


def _apply_effect(
    effect: BehaviorEffect,
    *,
    current_entity: Entity,
    accumulator: _BehaviorAccumulator,
) -> None:
    if isinstance(effect, MessageEffect):
        accumulator.messages.append(_render_message_text(effect.text, current_entity, accumulator))
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
    elif isinstance(effect, SetEntityPassableEffect):
        update.passable = effect.passable
    elif isinstance(effect, SetEntityActiveEffect):
        update.active = effect.active


def _effect_entity_id(
    effect: SetEntityStateEffect | SetEntityPassableEffect | SetEntityActiveEffect,
    current_entity: Entity,
) -> str:
    return effect.entity_id or current_entity.id


def _render_message_text(text: str, current_entity: Entity, accumulator: _BehaviorAccumulator) -> str:
    state = accumulator.entity_updates.get(current_entity.id, EntityUpdate()).state or current_entity.state
    return render_state_template(text, state)


def render_state_template(text: str, state: str) -> str:
    """Render state placeholders in authored entity text."""
    return STATE_PLACEHOLDER_PATTERN.sub(state, text)
