"""Built-in escape-room maps loaded from bundled JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from watch_my_escape.game.maps import GameMap  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Mapping

MAP_DATA_PACKAGE: Final = "watch_my_escape.game.map_data"


@dataclass(frozen=True, slots=True)
class PremadeMap:
    """A bundled playable map and its selection metadata."""

    id: str
    name: str
    description: str
    objective: str
    map: GameMap

    def as_selection_option(self) -> dict[str, str]:
        """Return the JSON-safe shape used by the frontend selector."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "objective": self.objective,
        }


class PremadeMapDocument(BaseModel):
    """JSON file shape for one bundled premade map."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    map: GameMap

    def to_premade_map(self) -> PremadeMap:
        """Return the runtime map definition."""
        return PremadeMap(
            id=self.map.id,
            name=self.map.name,
            description=self.description,
            objective=self.objective,
            map=self.map,
        )


class PremadeMapError(ValueError):
    """Raised when a requested premade map is not available."""


def list_premade_maps() -> tuple[PremadeMap, ...]:
    """Load every bundled premade map."""
    return tuple(sorted(_load_premade_maps().values(), key=lambda item: item.name))


def get_premade_map(map_id: str) -> PremadeMap:
    """Return one bundled premade map by id."""
    maps = _load_premade_maps()
    try:
        return maps[map_id]
    except KeyError as exc:
        available = ", ".join(sorted(maps))
        msg = f"Unknown map {map_id!r}. Available maps: {available}."
        raise PremadeMapError(msg) from exc


def create_key_door_map() -> GameMap:
    """Return the bundled key-door room map."""
    return get_premade_map("key-door-room").map


def _load_premade_maps() -> Mapping[str, PremadeMap]:
    data_root = files(MAP_DATA_PACKAGE)
    loaded = {}
    for path in data_root.iterdir():
        if not path.name.endswith(".json"):
            continue
        document = PremadeMapDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))
        premade_map = document.to_premade_map()
        loaded[premade_map.id] = premade_map
    return loaded
