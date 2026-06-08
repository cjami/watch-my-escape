"""Build per-turn action schemas constrained to the current session."""

from __future__ import annotations

from functools import cache, reduce
from operator import or_
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from pydantic import BaseModel, Field, RootModel, create_model

from watch_my_escape.game.actions import ActionBase, NoteText, SpokenText, VisibleTarget
from watch_my_escape.game.maps import visible_notable_entities

if TYPE_CHECKING:
    from watch_my_escape.game.maps import GameSessionState

ENTITY_ACTIONS = ("examine", "pick_up", "open", "close", "push", "pull", "talk_to", "use")
ACTION_DESCRIPTIONS = {
    "close": "Close an object.",
    "examine": "Look closely at an object.",
    "open": "Open an object.",
    "pick_up": "Pick up an object and add it to inventory.",
    "pull": "Pull an object.",
    "push": "Push an object.",
    "take_note": "Record a note for yourself.",
    "talk_to": "Say something to an object or character.",
    "use": "Use an object directly.",
    "use_item": "Use an inventory item on a target.",
}
type ActionFilter = frozenset[str] | None
type CachedActionFilter = tuple[str, ...] | None


def build_available_action_model(
    session: GameSessionState,
    *,
    actions: ActionFilter = None,
) -> type[BaseModel]:
    """Return an action model constrained to currently possible actions."""
    visible_targets = tuple(placed.entity.id for placed in visible_notable_entities(session))
    items = tuple(dict.fromkeys(session.inventory))
    action_key = tuple(sorted(actions)) if actions is not None else None
    return _build_available_action_model(
        has_visible_targets=bool(visible_targets),
        items=items,
        visible_targets=visible_targets,
        actions=action_key,
    )


@cache
def _build_available_action_model(
    *,
    has_visible_targets: bool,
    items: tuple[str, ...],
    visible_targets: tuple[str, ...],
    actions: CachedActionFilter,
) -> type[BaseModel]:
    models: list[type[BaseModel]] = []
    models.extend(_entity_action_models(has_visible_targets=has_visible_targets, actions=actions))
    if _allows(actions, "use_item"):
        models.extend(_use_item_models(items=items, visible_targets=visible_targets))
    if _allows(actions, "take_note"):
        models.append(_take_note_model())

    if not models:
        models.append(_take_note_model())

    if len(models) == 1:
        return models[0]

    union: Any = reduce(or_, models)
    annotated_union: Any = Annotated[union, Field(discriminator="action")]
    return cast("type[BaseModel]", RootModel[annotated_union])


def _entity_action_models(
    *,
    has_visible_targets: bool,
    actions: CachedActionFilter,
) -> list[type[BaseModel]]:
    if not has_visible_targets:
        return []

    models: list[type[BaseModel]] = []
    for action in ENTITY_ACTIONS:
        if not _allows(actions, action):
            continue
        if action == "talk_to":
            models.append(
                create_model(
                    "AvailableTalkToAction",
                    __base__=ActionBase,
                    __doc__=ACTION_DESCRIPTIONS[action],
                    action=(_literal((action,)), ...),
                    target=(VisibleTarget, ...),
                    text=(SpokenText, ...),
                )
            )
            continue
        models.append(
            create_model(
                f"Available{_model_name(action)}Action",
                __base__=ActionBase,
                __doc__=ACTION_DESCRIPTIONS[action],
                action=(_literal((action,)), ...),
                target=(VisibleTarget, ...),
            )
        )
    return models


def _use_item_models(*, items: tuple[str, ...], visible_targets: tuple[str, ...]) -> list[type[BaseModel]]:
    if not items:
        return []
    targets = _use_item_targets(visible_targets=visible_targets, items=items)
    if not targets:
        return []

    return [
        create_model(
            "AvailableUseItemAction",
            __base__=ActionBase,
            __doc__=ACTION_DESCRIPTIONS["use_item"],
            action=(Literal["use_item"], ...),
            item=(_literal(items), ...),
            target=(_literal(targets), ...),
        )
    ]


def _use_item_targets(*, visible_targets: tuple[str, ...], items: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*visible_targets, *items)))


def _take_note_model() -> type[BaseModel]:
    return create_model(
        "AvailableTakeNoteAction",
        __base__=ActionBase,
        __doc__=ACTION_DESCRIPTIONS["take_note"],
        action=(Literal["take_note"], ...),
        text=(NoteText, ...),
    )


def _model_name(action: str) -> str:
    return "".join(part.title() for part in action.split("_"))


def _allows(values: ActionFilter | CachedActionFilter, value: str) -> bool:
    return values is None or value in values


def _literal(values: tuple[str, ...]) -> Any:
    return Literal.__getitem__(values)
