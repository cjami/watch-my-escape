"""Build per-turn action schemas constrained to the current session."""

from __future__ import annotations

from functools import reduce
from operator import or_
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from pydantic import BaseModel, Field, RootModel, create_model

from watch_my_escape.game.actions import ActionBase, NoteText, SpokenText
from watch_my_escape.game.emotions import Emotion
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
    "talk_to": "Say something to an object or character.",
    "use": "Use an object directly.",
    "use_item": "Use an inventory item on a target.",
    "write_note": "Write a note for yourself.",
}
type ActionFilter = frozenset[str] | None
type ActionFilterKey = tuple[str, ...] | None


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
        items=items,
        visible_targets=visible_targets,
        actions=action_key,
    )


def _build_available_action_model(
    *,
    items: tuple[str, ...],
    visible_targets: tuple[str, ...],
    actions: ActionFilterKey,
) -> type[BaseModel]:
    models: list[type[BaseModel]] = []
    models.extend(_entity_action_models(visible_targets=visible_targets, actions=actions))
    if _allows(actions, "use_item"):
        models.extend(_use_item_models(items=items, visible_targets=visible_targets))
    if _allows(actions, "write_note"):
        models.append(_write_note_model())

    if not models:
        models.append(_write_note_model())

    if len(models) == 1:
        return models[0]

    union: Any = reduce(or_, models)
    annotated_union: Any = Annotated[union, Field(discriminator="action")]
    return cast("type[BaseModel]", RootModel[annotated_union])


def _entity_action_models(
    *,
    visible_targets: tuple[str, ...],
    actions: ActionFilterKey,
) -> list[type[BaseModel]]:
    if not visible_targets:
        return []

    target_type = _literal(visible_targets)
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
                    target=(target_type, ...),
                    text=(SpokenText, ...),
                    emotion=(Emotion, ...),
                )
            )
            continue
        models.append(
            create_model(
                f"Available{_model_name(action)}Action",
                __base__=ActionBase,
                __doc__=ACTION_DESCRIPTIONS[action],
                action=(_literal((action,)), ...),
                target=(target_type, ...),
                emotion=(Emotion, ...),
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
            emotion=(Emotion, ...),
        )
    ]


def _use_item_targets(*, visible_targets: tuple[str, ...], items: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*visible_targets, *items)))


def _write_note_model() -> type[BaseModel]:
    return create_model(
        "AvailableWriteNoteAction",
        __base__=ActionBase,
        __doc__=ACTION_DESCRIPTIONS["write_note"],
        action=(Literal["write_note"], ...),
        text=(NoteText, ...),
        emotion=(Emotion, ...),
    )


def _model_name(action: str) -> str:
    return "".join(part.title() for part in action.split("_"))


def _allows(values: ActionFilter | ActionFilterKey, value: str) -> bool:
    return values is None or value in values


def _literal(values: tuple[str, ...]) -> Any:
    return Literal.__getitem__(values)
