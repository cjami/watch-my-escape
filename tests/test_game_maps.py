import pytest
from pydantic import ValidationError

from watch_my_escape.game.maps import (
    Direction,
    GameMap,
    GameSessionState,
    MoveBlockedError,
    render_agent_view,
    render_user_map_view,
    visible_coordinates,
)
from watch_my_escape.game.models import Coordinate


def test_map_json_round_trip_uses_placed_entities():
    game_map = GameMap.model_validate(_map_payload())

    restored = GameMap.model_validate_json(game_map.model_dump_json())

    assert restored == game_map
    assert restored.entities[0].entity.id == "brass-key"
    assert restored.entities[0].position == Coordinate(x=1, y=2)


def test_map_rejects_duplicate_entity_ids():
    payload = _map_payload()
    payload["entities"][1]["entity"]["id"] = "brass-key"

    with pytest.raises(ValidationError):
        GameMap.model_validate(payload)


def test_map_rejects_duplicate_entity_positions():
    payload = _map_payload()
    payload["entities"][1]["position"] = {"x": 1, "y": 2}

    with pytest.raises(ValidationError, match="one entity"):
        GameMap.model_validate(payload)


def test_map_rejects_unknown_behavior_references():
    payload = _map_payload()
    payload["entities"][0]["entity"]["behaviors"] = [
        {
            "trigger": {"action": "pull"},
            "effects": [{"type": "set_entity_active", "entity_id": "missing-door", "active": True}],
        }
    ]

    with pytest.raises(ValidationError):
        GameMap.model_validate(payload)


def test_map_rejects_unknown_inventory_entity_references():
    payload = _map_payload()
    payload["entities"][0]["entity"]["behaviors"] = [
        {
            "trigger": {"action": "pick_up"},
            "effects": [{"type": "add_inventory", "entity_id": "missing-key"}],
        }
    ]

    with pytest.raises(ValidationError):
        GameMap.model_validate(payload)


def test_agent_view_uses_visibility_from_passable_cells_and_blockers():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))

    view = render_agent_view(session)

    assert "Position: (1, 1)" in view
    assert "- brass-key: Brass key." in view
    assert "- locked-door: Locked door." in view
    assert "target brass-key" not in view
    assert "secret-note" not in view
    assert "remote-hatch" not in view
    assert Coordinate(x=3, y=1) not in visible_coordinates(session)


def test_agent_view_excludes_non_notable_entities_from_visible_entity_list():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))

    view = render_agent_view(session)
    visible_entity_list = view.split("Visible entities:", maxsplit=1)[1]

    assert "y\\x" not in view
    assert "locked-door" in visible_entity_list
    assert "brass-key" in visible_entity_list
    assert "wall-0" not in visible_entity_list
    assert "wall-2" not in visible_entity_list


def test_user_map_view_shows_full_grid_with_visible_icons():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))

    view = render_user_map_view(session)

    assert len(view) == 16
    assert all(len(row) == 16 for row in view)
    assert view[1][1] == "🙂"
    assert view[1][2] == "🚪"
    assert view[2][1] == "🔑"
    assert "📝" not in {cell for row in view for cell in row}


def test_user_map_view_uses_agent_icon():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))

    view = render_user_map_view(session, agent_icon="\U0001f914")

    assert view[1][1] == "\U0001f914"


def test_movement_is_blocked_by_closed_door_until_cross_map_effect_opens_it():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))

    with pytest.raises(MoveBlockedError):
        session.move(Direction.EAST)

    result = session.evaluate_entity_action("brass-key", "pull")
    updated = session.apply_behavior_result(result)

    assert updated.map.entities_by_id()["locked-door"].passable is True
    assert updated.move(Direction.EAST).agent_position == Coordinate(x=2, y=1)
    assert Coordinate(x=3, y=1) in visible_coordinates(updated)


def test_escape_map_effect_marks_session_escaped():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))

    result = session.evaluate_entity_action("remote-hatch", "open")
    updated = session.apply_behavior_result(result)

    assert result.escaped is True
    assert updated.escaped is True


def _map_payload():
    return {
        "id": "training-map",
        "name": "Training Map",
        "agent_start": {"x": 1, "y": 1},
        "entities": [
            {
                "position": {"x": 1, "y": 2},
                "entity": {
                    "id": "brass-key",
                    "name": "Brass key",
                    "icon": "🔑",
                    "description": "A tarnished brass key.",
                    "passable": True,
                    "behaviors": [
                        {
                            "trigger": {"action": "pull"},
                            "effects": [
                                {
                                    "type": "set_entity_passable",
                                    "entity_id": "locked-door",
                                    "passable": True,
                                }
                            ],
                        }
                    ],
                },
            },
            *[
                {
                    "position": {"x": 2, "y": y},
                    "entity": {
                        "id": f"wall-{y}",
                        "name": "Wall",
                        "icon": "🧱",
                        "description": "A solid wall.",
                        "passable": False,
                        "notable": False,
                    },
                }
                for y in [0, *range(2, 16)]
            ],
            {
                "position": {"x": 1, "y": 3},
                "entity": {
                    "id": "secret-note",
                    "name": "Secret note",
                    "icon": "📝",
                    "description": "A hidden note.",
                    "passable": True,
                    "active": False,
                },
            },
            {
                "position": {"x": 2, "y": 1},
                "entity": {
                    "id": "locked-door",
                    "name": "Locked door",
                    "icon": "🚪",
                    "description": "A heavy door.",
                    "passable": False,
                },
            },
            {
                "position": {"x": 3, "y": 1},
                "entity": {
                    "id": "remote-hatch",
                    "name": "Remote hatch",
                    "icon": "🕳️",
                    "description": "A hatch out of the facility.",
                    "passable": True,
                    "behaviors": [
                        {
                            "trigger": {"action": "open"},
                            "effects": [{"type": "escape_map"}],
                        }
                    ],
                },
            },
        ],
    }
