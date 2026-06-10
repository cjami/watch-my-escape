import pytest
from pydantic import ValidationError

from watch_my_escape.game.maps import (
    Direction,
    GameMap,
    GameSessionState,
    MoveBlockedError,
    render_agent_view,
    render_user_map_view,
    render_user_visibility_view,
    render_visibility_view,
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


def test_map_rejects_duplicate_ids_across_placed_and_unplaced_entities():
    payload = _map_payload()
    payload["unplaced_entities"] = [
        {
            "id": "brass-key",
            "icon": "key",
            "description": "A duplicate key.",
            "passable": True,
        }
    ]

    with pytest.raises(ValidationError, match="entity ids"):
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
            "trigger": {"action": "take"},
            "effects": [{"type": "add_inventory", "entity_id": "missing-key"}],
        }
    ]

    with pytest.raises(ValidationError):
        GameMap.model_validate(payload)


def test_map_accepts_behavior_references_to_unplaced_entities():
    payload = _map_payload()
    payload["unplaced_entities"] = [
        {
            "id": "hidden-note",
            "icon": "note",
            "description": "A folded clue.",
            "passable": True,
            "state": "folded",
        }
    ]
    payload["entities"][0]["entity"]["behaviors"] = [
        {
            "trigger": {"action": "open"},
            "effects": [
                {"type": "add_inventory", "entity_id": "hidden-note"},
                {"type": "set_entity_state", "entity_id": "hidden-note", "state": "readable"},
            ],
        }
    ]

    game_map = GameMap.model_validate(payload)

    assert game_map.entities_by_id()["hidden-note"].state == "folded"


def test_map_json_round_trip_includes_unplaced_entities():
    payload = _map_payload()
    payload["unplaced_entities"] = [
        {
            "id": "hidden-note",
            "icon": "note",
            "description": "A folded clue.",
            "passable": True,
        }
    ]

    game_map = GameMap.model_validate(payload)
    restored = GameMap.model_validate_json(game_map.model_dump_json())

    assert restored.unplaced_entities[0].id == "hidden-note"


def test_agent_view_uses_visibility_from_passable_cells_and_blockers():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))

    view = render_agent_view(session)

    assert "Position:" not in view
    assert "(1, 1)" not in view
    assert "- brass-key: A tarnished brass key." in view
    assert "- locked-door: A heavy door." in view
    assert "target brass-key" not in view
    assert "secret-note" not in view
    assert "remote-hatch" not in view
    assert Coordinate(x=3, y=1) not in visible_coordinates(session)


def test_agent_view_excludes_non_notable_entities_from_visible_entity_list():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))

    view = render_agent_view(session)
    visible_entity_list = view.split("Surrounding objects:", maxsplit=1)[1]

    assert "y\\x" not in view
    assert "locked-door" in visible_entity_list
    assert "brass-key" in visible_entity_list
    assert "wall-0" not in visible_entity_list
    assert "wall-2" not in visible_entity_list


def test_agent_view_can_interpolate_entity_state_in_descriptions():
    payload = _map_payload()
    locked_door = next(placed["entity"] for placed in payload["entities"] if placed["entity"]["id"] == "locked-door")
    locked_door["description"] = "A heavy door. It is {state}."
    locked_door["state"] = "locked"
    session = GameSessionState(map=GameMap.model_validate(payload))

    view = render_agent_view(session)

    assert "- locked-door: A heavy door. It is locked." in view
    assert "{state}" not in view


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


def test_visibility_view_marks_cells_visible_to_agent():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))

    view = render_visibility_view(session)

    assert len(view) == 16
    assert all(len(row) == 16 for row in view)
    assert view[1][1] is True
    assert view[1][2] is True
    assert view[1][3] is False


def test_user_visibility_view_styles_non_notable_corner_entities_as_visible():
    payload = _interior_corner_payload()
    session = GameSessionState(map=GameMap.model_validate(payload))

    agent_view = render_visibility_view(session)
    user_view = render_user_visibility_view(session)

    assert agent_view[2][2] is False
    assert user_view[2][2] is True


def test_movement_is_blocked_by_closed_door_until_cross_map_effect_opens_it():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))

    with pytest.raises(MoveBlockedError):
        session.move(Direction.EAST)

    result = session.evaluate_entity_action("brass-key", "pull")
    updated = session.apply_behavior_result(result)

    assert updated.map.entities_by_id()["locked-door"].passable is True
    assert updated.move(Direction.EAST).agent_position == Coordinate(x=2, y=1)
    assert Coordinate(x=3, y=1) in visible_coordinates(updated)


def test_inactive_entities_do_not_block_movement_or_visibility():
    session = GameSessionState(map=GameMap.model_validate(_map_payload()))
    result = session.evaluate_entity_action("locked-door", "push")
    updated = session.apply_behavior_result(result)

    assert updated.map.entities_by_id()["locked-door"].active is False
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
                    "icon": "🚪",
                    "description": "A heavy door.",
                    "passable": False,
                    "behaviors": [
                        {
                            "trigger": {"action": "push"},
                            "effects": [{"type": "set_entity_active", "active": False}],
                        }
                    ],
                },
            },
            {
                "position": {"x": 3, "y": 1},
                "entity": {
                    "id": "remote-hatch",
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


def _interior_corner_payload():
    return {
        "id": "interior-corner",
        "name": "Interior Corner",
        "agent_start": {"x": 1, "y": 1},
        "entities": [
            {
                "position": {"x": x, "y": y},
                "entity": {
                    "id": entity_id,
                    "icon": "#",
                    "description": "A wall.",
                    "passable": False,
                    "notable": False,
                },
            }
            for entity_id, x, y in (
                ("west-wall", 0, 1),
                ("north-wall", 1, 0),
                ("east-wall", 2, 1),
                ("south-wall", 1, 2),
                ("interior-corner-wall", 2, 2),
            )
        ],
    }
