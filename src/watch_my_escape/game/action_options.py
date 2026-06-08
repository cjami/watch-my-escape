"""Build per-turn action schemas constrained to the current session."""

from __future__ import annotations

from functools import reduce
from operator import or_
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from pydantic import BaseModel, Field, RootModel, create_model

from watch_my_escape.game.actions import ActionBase, NoteText
from watch_my_escape.game.maps import visible_notable_entities

if TYPE_CHECKING:
    from watch_my_escape.game.maps import GameSessionState

ENTITY_ACTIONS = ("examine", "pick_up", "open", "close", "push", "pull", "talk_to", "use")
type ActionFilter = frozenset[str] | None


def build_available_action_model(
    session: GameSessionState,
    *,
    actions: ActionFilter = None,
) -> type[BaseModel]:
    """Return an action model constrained to currently possible actions."""
    models: list[type[BaseModel]] = []
    models.extend(_entity_action_models(session, actions=actions))
    if _allows(actions, "use_item"):
        models.extend(_use_item_models(session))
    if _allows(actions, "take_note"):
        models.append(_take_note_model())

    if not models:
        models.append(_take_note_model())

    if len(models) == 1:
        return models[0]

    union: Any = reduce(or_, models)
    annotated_union: Any = Annotated[union, Field(discriminator="action")]
    return cast("type[BaseModel]", RootModel[annotated_union])


def _entity_action_models(session: GameSessionState, *, actions: ActionFilter) -> list[type[BaseModel]]:
    models: list[type[BaseModel]] = []
    for action in ENTITY_ACTIONS:
        if not _allows(actions, action):
            continue
        targets = _targets_for_action(session, action)
        if targets:
            models.append(
                create_model(
                    f"Available{_model_name(action)}Action",
                    __base__=ActionBase,
                    action=(_literal((action,)), action),
                    target=(_literal(targets), ...),
                )
            )
    return models


def _use_item_models(session: GameSessionState) -> list[type[BaseModel]]:
    options = _use_item_options(session)
    if not options:
        return []

    items = tuple(dict.fromkeys(item for item, _target in options))
    targets = tuple(dict.fromkeys(target for _item, target in options))
    return [
        create_model(
            "AvailableUseItemAction",
            __base__=ActionBase,
            action=(Literal["use_item"], "use_item"),
            item=(_literal(items), ...),
            target=(_literal(targets), ...),
        )
    ]


def _take_note_model() -> type[BaseModel]:
    return create_model(
        "AvailableTakeNoteAction",
        __base__=ActionBase,
        action=(Literal["take_note"], "take_note"),
        text=(NoteText, ...),
    )


def _targets_for_action(session: GameSessionState, action: str) -> tuple[str, ...]:
    return tuple(
        placed.entity.name.lower()
        for placed in visible_notable_entities(session)
        if any(behavior.trigger.action == action for behavior in placed.entity.behaviors)
    )


def _use_item_options(session: GameSessionState) -> tuple[tuple[str, str], ...]:
    options: list[tuple[str, str]] = []
    inventory = set(session.inventory)
    for placed in visible_notable_entities(session):
        options.extend(
            (behavior.trigger.item, placed.entity.name.lower())
            for behavior in placed.entity.behaviors
            if behavior.trigger.action == "use_item" and behavior.trigger.item in inventory
        )
    return tuple(options)


def _model_name(action: str) -> str:
    return "".join(part.title() for part in action.split("_"))


def _allows(values: frozenset[str] | None, value: str) -> bool:
    return values is None or value in values


def _literal(values: tuple[str, ...]) -> Any:
    return Literal.__getitem__(values)
