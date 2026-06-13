"""Structured agent action schemas."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from watch_my_escape.game.emotions import Emotion  # noqa: TC001

type InventoryItem = Annotated[str, Field(min_length=1, description="An item currently in inventory.")]
type SpokenText = Annotated[str, Field(min_length=1, description="Words to say to the target.")]
type Target = Annotated[
    str,
    Field(min_length=1, description="An object from your surroundings or an item in your inventory."),
]


class ActionBase(BaseModel):
    """Common configuration for all agent actions."""

    model_config = ConfigDict(extra="forbid")


class UseItemAction(ActionBase):
    """Use your inventory item on another object."""

    action: Literal["use_item"]
    item: InventoryItem
    target: Target
    emotion: Emotion


class OperateAction(ActionBase):
    """Operate a device, mechanism, or control."""

    action: Literal["operate"]
    target: Target
    emotion: Emotion


class PickUpAction(ActionBase):
    """Pick up an item and add it to your inventory."""

    action: Literal["pick_up"]
    target: Target
    emotion: Emotion


class OpenAction(ActionBase):
    """Open an object."""

    action: Literal["open"]
    target: Target
    emotion: Emotion


class CloseAction(ActionBase):
    """Close an object."""

    action: Literal["close"]
    target: Target
    emotion: Emotion


class ExamineAction(ActionBase):
    """Look closely at an object."""

    action: Literal["examine"]
    target: Target
    emotion: Emotion


class PushAction(ActionBase):
    """Push an object."""

    action: Literal["push"]
    target: Target
    emotion: Emotion


class PullAction(ActionBase):
    """Pull an object."""

    action: Literal["pull"]
    target: Target
    emotion: Emotion


class TalkToAction(ActionBase):
    """Say something to an object or character."""

    action: Literal["talk_to"]
    target: Target
    text: SpokenText
    emotion: Emotion


class EscapeRoomAction(
    RootModel[
        Annotated[
            UseItemAction
            | OperateAction
            | PickUpAction
            | OpenAction
            | CloseAction
            | ExamineAction
            | PushAction
            | PullAction
            | TalkToAction,
            Field(discriminator="action"),
        ]
    ]
):
    """Any allowed escape-room action."""
