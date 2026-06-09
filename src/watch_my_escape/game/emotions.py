"""Emotion vocabulary for agent actions."""

from __future__ import annotations

from typing import Literal, cast

type Emotion = Literal[
    "neutral",
    "happy",
    "curious",
    "focused",
    "surprised",
    "worried",
    "confused",
    "frustrated",
    "confident",
    "relieved",
]

EMOTION_TO_EMOJI: dict[Emotion, str] = {
    "neutral": "\U0001f642",
    "happy": "\U0001f604",
    "curious": "\U0001f914",
    "focused": "\U0001f9d0",
    "surprised": "\U0001f632",
    "worried": "\U0001f61f",
    "confused": "\U0001f615",
    "frustrated": "\U0001f616",
    "confident": "\U0001f60e",
    "relieved": "\U0001f60c",
}

DEFAULT_EMOTION: Emotion = "neutral"


def emotion_to_emoji(emotion: str) -> str:
    """Return the display emoji for a constrained emotion word."""
    if emotion in EMOTION_TO_EMOJI:
        return EMOTION_TO_EMOJI[cast("Emotion", emotion)]
    return EMOTION_TO_EMOJI[DEFAULT_EMOTION]
