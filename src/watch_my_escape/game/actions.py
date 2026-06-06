"""Structured agent action schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InspectObjectAction(BaseModel):
    """Inspect one object in the room."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["inspect_object"]
    object_name: str
    detail_level: Literal[1, 2, 3]


class CombineItemsAction(BaseModel):
    """Combine two inventory items for a purpose."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["combine_items"]
    items: tuple[str, str] = Field(min_length=2, max_length=2)
    purpose: str


class MoveAction(BaseModel):
    """Move in one cardinal direction."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["move"]
    direction: Literal["north", "east", "south", "west"]
    emotion: str


class ClueRecord(BaseModel):
    """Record a clue found while evaluating structured output."""

    model_config = ConfigDict(extra="forbid")

    clue_id: str
    code: str
    useful: bool
