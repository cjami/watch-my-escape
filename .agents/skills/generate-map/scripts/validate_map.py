"""Validate WATCH MY ESCAPE premade map JSON files."""

from __future__ import annotations

# ruff: noqa: E402, I001

import argparse
import json
import re
import sys
from pathlib import Path


def _ensure_repo_src_on_path() -> None:
    for root in (Path.cwd(), *Path(__file__).resolve().parents):
        src = root / "src"
        if (src / "watch_my_escape").is_dir():
            sys.path.insert(0, str(src))
            return


_ensure_repo_src_on_path()

from pydantic import ValidationError

from watch_my_escape.game.maps import Coordinate, GameMap, GameSessionState, visible_notable_entities
from watch_my_escape.game.premade_maps import PremadeMapDocument


KEBAB_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def main() -> int:
    """Validate one or more map JSON files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Map JSON file(s) to validate.")
    args = parser.parse_args()

    exit_code = 0
    for path in args.paths:
        if not _validate_path(path):
            exit_code = 1
    return exit_code


def _validate_path(path: Path) -> bool:
    try:
        document = _load_document(path)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"{path}: invalid")
        print(f"  {exc}")
        return False

    issues, warnings = _semantic_findings(document)
    if issues:
        print(f"{path}: invalid")
        for issue in issues:
            print(f"  error: {issue}")
        for warning in warnings:
            print(f"  warning: {warning}")
        return False

    print(
        f"{path}: ok "
        f"({document.map.id}, {len(document.map.entities)} placed, "
        f"{len(document.map.unplaced_entities)} unplaced)"
    )
    for warning in warnings:
        print(f"  warning: {warning}")
    return True


def _load_document(path: Path) -> PremadeMapDocument:
    return PremadeMapDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _semantic_findings(document: PremadeMapDocument) -> tuple[list[str], list[str]]:
    game_map = document.map
    issues: list[str] = []
    warnings: list[str] = []

    if not KEBAB_ID_PATTERN.fullmatch(game_map.id):
        issues.append(f"map id {game_map.id!r} should be lowercase kebab case")

    issues.extend(
        f"entity id {entity.id!r} should be lowercase kebab case"
        for entity in game_map.all_entities()
        if not KEBAB_ID_PATTERN.fullmatch(entity.id)
    )

    issues.extend(_agent_start_issues(game_map))
    issues.extend(_perimeter_issues(game_map))

    if not _has_escape_effect(game_map):
        issues.append("at least one behavior must include an escape_map effect")

    session = GameSessionState(map=game_map)
    if not visible_notable_entities(session):
        warnings.append("no active notable entity is visible from agent_start")

    return issues, warnings


def _agent_start_issues(game_map: GameMap) -> list[str]:
    start = game_map.agent_start
    issues: list[str] = []

    if start.x in (0, game_map.width - 1) or start.y in (0, game_map.height - 1):
        issues.append("agent_start should be inside the sealed perimeter")

    blockers = [
        placed.entity.id
        for placed in game_map.entities_at(start)
        if placed.entity.active and not placed.entity.passable
    ]
    if blockers:
        issues.append(f"agent_start is blocked by active impassable entity ids: {', '.join(blockers)}")

    return issues


def _perimeter_issues(game_map: GameMap) -> list[str]:
    issues: list[str] = []
    for coordinate in _perimeter_coordinates(game_map):
        blockers = [
            placed.entity.id
            for placed in game_map.entities_at(coordinate)
            if placed.entity.active and not placed.entity.passable
        ]
        if not blockers:
            issues.append(f"perimeter coordinate ({coordinate.x}, {coordinate.y}) is not initially sealed")
    return issues


def _perimeter_coordinates(game_map: GameMap) -> tuple[Coordinate, ...]:
    coordinates: list[Coordinate] = []
    for x in range(game_map.width):
        coordinates.append(Coordinate(x=x, y=0))
        coordinates.append(Coordinate(x=x, y=game_map.height - 1))
    for y in range(1, game_map.height - 1):
        coordinates.append(Coordinate(x=0, y=y))
        coordinates.append(Coordinate(x=game_map.width - 1, y=y))
    return tuple(coordinates)


def _has_escape_effect(game_map: GameMap) -> bool:
    return any(
        effect.type == "escape_map"
        for entity in game_map.all_entities()
        for behavior in entity.behaviors
        for effect in behavior.effects
    )


if __name__ == "__main__":
    raise SystemExit(main())
