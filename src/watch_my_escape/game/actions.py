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
type Direction = Literal["North", "East", "South", "West"]
type InventoryItem = Annotated[str, Field(min_length=1, description="An item currently in the agent's inventory.")]
type AdjacentTarget = Annotated[str, Field(min_length=1, description="An entity adjacent to the agent.")]
type Target = Annotated[
    str,
    Field(min_length=1, description="Another inventory item or an entity adjacent to the agent."),
]
type NoteText = Annotated[str, Field(min_length=1, description="Text to record for later use.")]


class ActionBase(BaseModel):
    """Common configuration for all agent actions."""

    model_config = ConfigDict(extra="forbid")

    emotion: Emotion


class UseItemAction(ActionBase):
    """Use one inventory item on another item or adjacent entity."""

    action: Literal["use_item"]
    item: InventoryItem
    target: Target


class UseAction(ActionBase):
    """Use an adjacent entity."""

    action: Literal["use"]
    target: AdjacentTarget


class PickUpAction(ActionBase):
    """Pick up an adjacent entity."""

    action: Literal["pick_up"]
    target: AdjacentTarget


class OpenAction(ActionBase):
    """Open an adjacent entity."""

    action: Literal["open"]
    target: AdjacentTarget


class CloseAction(ActionBase):
    """Close an adjacent entity."""

    action: Literal["close"]
    target: AdjacentTarget


class ExamineAction(ActionBase):
    """Examine an adjacent entity."""

    action: Literal["examine"]
    target: AdjacentTarget


class PushAction(ActionBase):
    """Push an adjacent entity."""

    action: Literal["push"]
    target: AdjacentTarget


class PullAction(ActionBase):
    """Pull an adjacent entity."""

    action: Literal["pull"]
    target: AdjacentTarget


class TalkToAction(ActionBase):
    """Talk to an adjacent entity."""

    action: Literal["talk_to"]
    target: AdjacentTarget


class TakeNoteAction(ActionBase):
    """Record a note."""

    action: Literal["take_note"]
    text: NoteText


class MoveAction(ActionBase):
    """Move in one cardinal direction."""

    action: Literal["move"]
    direction: Direction


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
            | TakeNoteAction
            | MoveAction,
            Field(discriminator="action"),
        ]
    ]
):
    """Any allowed escape-room action."""
