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
    """Use one inventory item on another item or visible entity."""

    action: Literal["use_item"]
    item: InventoryItem
    target: Target


class UseAction(ActionBase):
    """Use a visible entity."""

    action: Literal["use"]
    target: VisibleTarget


class PickUpAction(ActionBase):
    """Pick up a visible entity."""

    action: Literal["pick_up"]
    target: VisibleTarget


class OpenAction(ActionBase):
    """Open a visible entity."""

    action: Literal["open"]
    target: VisibleTarget


class CloseAction(ActionBase):
    """Close a visible entity."""

    action: Literal["close"]
    target: VisibleTarget


class ExamineAction(ActionBase):
    """Examine a visible entity."""

    action: Literal["examine"]
    target: VisibleTarget


class PushAction(ActionBase):
    """Push a visible entity."""

    action: Literal["push"]
    target: VisibleTarget


class PullAction(ActionBase):
    """Pull a visible entity."""

    action: Literal["pull"]
    target: VisibleTarget


class TalkToAction(ActionBase):
    """Talk to a visible entity."""

    action: Literal["talk_to"]
    target: VisibleTarget


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
