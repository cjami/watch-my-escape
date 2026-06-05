"""Agent emotion validation placeholders."""

from typing import Literal

type Emotion = Literal["neutral", "pondering", "realization", "frustrated", "escaped"]
ALLOWED_EMOTIONS: frozenset[Emotion] = frozenset(
    {
        "neutral",
        "pondering",
        "realization",
        "frustrated",
        "escaped",
    },
)
