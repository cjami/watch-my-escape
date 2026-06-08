"""Structured agent action schemas."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

type Emotion = Literal[
    "😀",
    "😃",
    "😄",
    "😁",
    "😆",
    "😅",
    "😂",
    "🙂",
    "🙃",
    "😉",
    "😊",
    "😇",
    "🥰",
    "😍",
    "🤩",
    "😘",
    "😗",
    "☺️",
    "😚",
    "😙",
    "🥲",
    "😋",
    "😛",
    "😜",
    "🤪",
    "😝",
    "🤑",
    "🤗",
    "🤭",
    "🫢",
    "🫣",
    "🤫",
    "🤔",
    "🫡",
    "🤐",
    "🤨",
    "😐",
    "😑",
    "😶",
    "🫥",
    "😶‍🌫️",
    "😏",
    "😒",
    "🙄",
    "😬",
    "😮‍💨",
    "🤥",
    "😌",
    "😔",
    "😪",
    "🤤",
    "😴",
    "😷",
    "🤒",
    "🤕",
    "🤢",
    "🤮",
    "🤧",
    "🥵",
    "🥶",
    "🥴",
    "😵",
    "😵‍💫",
    "🤯",
    "🤠",
    "🥳",
    "🥸",
    "😎",
    "🤓",
    "🧐",
    "😕",
    "🫤",
    "😟",
    "🙁",
    "☹️",
    "😮",
    "😯",
    "😲",
    "😳",
    "🥺",
    "🥹",
    "😦",
    "😧",
    "😨",
    "😰",
    "😥",
    "😢",
    "😭",
    "😱",
    "😖",
    "😣",
    "😞",
    "😓",
    "😩",
    "😫",
    "🥱",
    "😤",
    "😡",
    "😠",
    "🤬",
]
type InventoryItem = Annotated[str, Field(min_length=1, description="An item currently in inventory.")]
type SpokenText = Annotated[str, Field(min_length=1, description="Words to say to the target.")]
type VisibleTarget = Annotated[str, Field(min_length=1, description="A visible object.")]
type Target = Annotated[
    str,
    Field(min_length=1, description="Another inventory item or a visible object."),
]
type NoteText = Annotated[str, Field(min_length=1, description="Text to record for later use.")]


class ActionBase(BaseModel):
    """Common configuration for all agent actions."""

    model_config = ConfigDict(extra="forbid")

    emotion: Emotion


class UseItemAction(ActionBase):
    """Use an inventory item on a target."""

    action: Literal["use_item"]
    item: InventoryItem
    target: Target


class UseAction(ActionBase):
    """Use an object directly."""

    action: Literal["use"]
    target: VisibleTarget


class PickUpAction(ActionBase):
    """Pick up an object and add it to inventory."""

    action: Literal["pick_up"]
    target: VisibleTarget


class OpenAction(ActionBase):
    """Open an object."""

    action: Literal["open"]
    target: VisibleTarget


class CloseAction(ActionBase):
    """Close an object."""

    action: Literal["close"]
    target: VisibleTarget


class ExamineAction(ActionBase):
    """Look closely at an object."""

    action: Literal["examine"]
    target: VisibleTarget


class PushAction(ActionBase):
    """Push an object."""

    action: Literal["push"]
    target: VisibleTarget


class PullAction(ActionBase):
    """Pull an object."""

    action: Literal["pull"]
    target: VisibleTarget


class TalkToAction(ActionBase):
    """Say something to an object or character."""

    action: Literal["talk_to"]
    target: VisibleTarget
    text: SpokenText


class TakeNoteAction(ActionBase):
    """Record a note for yourself."""

    action: Literal["take_note"]
    text: NoteText


class EscapeRoomAction(
    RootModel[
        Annotated[
            UseItemAction
            | UseAction
            | PickUpAction
            | OpenAction
            | CloseAction
            | ExamineAction
            | PushAction
            | PullAction
            | TalkToAction
            | TakeNoteAction,
            Field(discriminator="action"),
        ]
    ]
):
    """Any allowed escape-room action."""
