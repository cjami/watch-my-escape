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
type InventoryItem = Annotated[str, Field(min_length=1, description="An item currently in the agent's inventory.")]
type SpokenText = Annotated[str, Field(min_length=1, description="Words to say to the visible entity.")]
type VisibleTarget = Annotated[str, Field(min_length=1, description="A visible entity.")]
type Target = Annotated[
    str,
    Field(min_length=1, description="Another inventory item or a visible entity."),
]
type NoteText = Annotated[str, Field(min_length=1, description="Text to record for later use.")]


class ActionBase(BaseModel):
    """Common configuration for all agent actions."""

    model_config = ConfigDict(extra="forbid")

    emotion: Emotion


class UseItemAction(ActionBase):
    """Use one inventory item on another item or entity."""

    action: Literal["use_item"]
    item: InventoryItem
    target: Target


class UseAction(ActionBase):
    """Use an entity."""

    action: Literal["use"]
    target: VisibleTarget


class PickUpAction(ActionBase):
    """Pick up an entity."""

    action: Literal["pick_up"]
    target: VisibleTarget


class OpenAction(ActionBase):
    """Open an entity."""

    action: Literal["open"]
    target: VisibleTarget


class CloseAction(ActionBase):
    """Close an entity."""

    action: Literal["close"]
    target: VisibleTarget


class ExamineAction(ActionBase):
    """Examine an entity."""

    action: Literal["examine"]
    target: VisibleTarget


class PushAction(ActionBase):
    """Push an entity."""

    action: Literal["push"]
    target: VisibleTarget


class PullAction(ActionBase):
    """Pull an entity."""

    action: Literal["pull"]
    target: VisibleTarget


class TalkToAction(ActionBase):
    """Talk to an entity."""

    action: Literal["talk_to"]
    target: VisibleTarget
    text: SpokenText


class TakeNoteAction(ActionBase):
    """Record a note."""

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
