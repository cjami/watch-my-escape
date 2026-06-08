import pytest
from pydantic import ValidationError

from watch_my_escape.game.action_options import build_available_action_model
from watch_my_escape.game.actions import EscapeRoomAction
from watch_my_escape.game.maps import Direction, GameMap, GameSessionState, MoveBlockedError
from watch_my_escape.game.models import Coordinate
from watch_my_escape.game.premade_maps import create_key_door_map
from watch_my_escape.game.runtime import STARTING_SANITY, apply_agent_action, render_room_state_for_agent

EMOTION = "\U0001f914"


def test_key_door_map_allows_key_pickup_and_hides_key():
    session = GameSessionState(map=create_key_door_map())

    result = apply_agent_action(session, STARTING_SANITY, _action("pick_up", target="brass-key"))

    assert result.sanity == 99
    assert result.session.agent_position == Coordinate(x=8, y=8)
    assert result.session.inventory == ("brass-key",)
    assert result.session.map.entities_by_id()["brass-key"].visible is False
    assert result.movement_path == (Coordinate(x=8, y=8),)
    assert result.message == "You pick up the brass key."


def test_key_door_map_blocks_door_until_key_unlocks_escape():
    session = GameSessionState(map=create_key_door_map())

    for _ in range(7):
        session = session.move(Direction.EAST)

    with pytest.raises(MoveBlockedError) as exc_info:
        session.move(Direction.EAST)

    assert "Locked door" in str(exc_info.value)

    initial = GameSessionState(map=create_key_door_map())
    with_key = apply_agent_action(initial, STARTING_SANITY, _action("pick_up", target="brass-key")).session

    escaped = apply_agent_action(with_key, 99, _action("use_item", item="brass-key", target="locked-door"))

    assert escaped.sanity == 98
    assert escaped.session.escaped is True
    assert escaped.session.agent_position == Coordinate(x=14, y=8)
    assert escaped.movement_path == tuple(Coordinate(x=x, y=8) for x in range(9, 15))
    assert escaped.session.map.entities_by_id()["locked-door"].state == "open"
    assert escaped.session.map.entities_by_id()["locked-door"].passable is True
    assert escaped.session.move(Direction.EAST).agent_position == Coordinate(x=15, y=8)


def test_visible_action_auto_moves_to_passable_entity_coordinate():
    session = GameSessionState(map=create_key_door_map())

    result = apply_agent_action(session, STARTING_SANITY, _action("examine", target="brass-key"))

    assert result.sanity == 99
    assert result.session.agent_position == Coordinate(x=8, y=8)
    assert result.movement_path == (Coordinate(x=8, y=8),)
    assert result.message == "You examine the Brass key. Nothing happens."


def test_visible_action_auto_moves_adjacent_to_impassable_entity_and_costs_one_sanity():
    session = apply_agent_action(
        GameSessionState(map=create_key_door_map()),
        STARTING_SANITY,
        _action("pick_up", target="brass-key"),
    ).session

    result = apply_agent_action(session, 99, _action("use_item", item="brass-key", target="locked-door"))

    assert result.sanity == 98
    assert result.session.agent_position == Coordinate(x=14, y=8)
    assert result.movement_path == tuple(Coordinate(x=x, y=8) for x in range(9, 15))
    assert result.session.escaped is True


def test_action_on_sealed_entity_fails_and_costs_one_sanity():
    session = GameSessionState(map=GameMap.model_validate(_sealed_map_payload()))

    result = apply_agent_action(session, STARTING_SANITY, _action("examine", target="sealed-hatch"))

    assert result.sanity == 99
    assert result.session == session
    assert result.movement_path == ()
    assert "no visible target matches" in result.message


def test_failed_action_still_reduces_sanity():
    session = GameSessionState(map=create_key_door_map())

    result = apply_agent_action(session, STARTING_SANITY, _action("open", target="missing door"))

    assert result.sanity == 99
    assert result.session == session
    assert "no visible target matches" in result.message


def test_take_note_records_journal_and_renders_to_agent():
    session = GameSessionState(map=create_key_door_map())

    result = apply_agent_action(session, STARTING_SANITY, _action("take_note", text="The key should open the door."))

    assert result.sanity == 99
    assert result.session.notes == ("The key should open the door.",)
    assert "Journal:\n- The key should open the door." in render_room_state_for_agent(result.session, result.sanity)


def test_empty_journal_is_rendered_to_agent():
    session = GameSessionState(map=create_key_door_map())

    assert "Journal:\n- No notes recorded." in render_room_state_for_agent(session, STARTING_SANITY)


def test_key_door_map_has_edge_walls_and_emoji_icons():
    game_map = create_key_door_map()
    entities = game_map.entities_by_id()

    assert game_map.agent_start == Coordinate(x=7, y=8)
    assert game_map.entities_at(Coordinate(x=0, y=0))[0].entity.name == "Wall"
    assert game_map.entities_at(Coordinate(x=0, y=0))[0].entity.notable is False
    assert entities["locked-door"].icon == "\U0001f6aa"
    assert entities["brass-key"].icon == "\U0001f511"
    assert game_map.entities_at(Coordinate(x=15, y=8))[0].entity.id == "locked-door"


def test_available_action_model_constrains_targets_to_current_possibilities():
    session = GameSessionState(map=create_key_door_map())
    action_model = build_available_action_model(session)

    assert action_model.model_validate({"action": "pick_up", "target": "brass-key", "emotion": EMOTION})
    assert action_model.model_validate({"action": "take_note", "text": "The key is on the floor.", "emotion": EMOTION})
    with pytest.raises(ValidationError, match="use_item"):
        action_model.model_validate(
            {"action": "use_item", "item": "brass-key", "target": "locked-door", "emotion": EMOTION}
        )

    with_key = apply_agent_action(session, STARTING_SANITY, _action("pick_up", target="brass-key")).session
    door_action_model = build_available_action_model(with_key)

    assert door_action_model.model_validate(
        {"action": "use_item", "item": "brass-key", "target": "locked-door", "emotion": EMOTION}
    )
    with pytest.raises(ValidationError, match="pick_up"):
        door_action_model.model_validate({"action": "pick_up", "target": "brass-key", "emotion": EMOTION})


def test_available_action_model_schema_requires_action_discriminator():
    session = GameSessionState(map=create_key_door_map())
    schema = build_available_action_model(session).model_json_schema()

    assert "action" in schema["$defs"]["AvailablePickUpAction"]["required"]
    assert "action" in schema["$defs"]["AvailableTakeNoteAction"]["required"]


def test_available_action_model_uses_entity_ids_for_duplicate_names():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    action_model = build_available_action_model(session)

    assert action_model.model_validate({"action": "examine", "target": "left-statue", "emotion": EMOTION})
    assert action_model.model_validate({"action": "examine", "target": "right-statue", "emotion": EMOTION})
    with pytest.raises(ValidationError, match="target"):
        action_model.model_validate({"action": "examine", "target": "statue", "emotion": EMOTION})


def _action(action: str, **values: object) -> EscapeRoomAction:
    return EscapeRoomAction.model_validate({"action": action, "emotion": EMOTION, **values})


def _sealed_map_payload():
    return {
        "id": "sealed-map",
        "name": "Sealed Map",
        "agent_start": {"x": 1, "y": 1},
        "entities": [
            *[
                {
                    "position": {"x": 2, "y": y},
                    "entity": {
                        "id": f"wall-{y}",
                        "name": "Wall",
                        "icon": "\U0001f9f1",
                        "description": "A solid wall.",
                        "passable": False,
                        "notable": False,
                    },
                }
                for y in range(16)
            ],
            {
                "position": {"x": 3, "y": 1},
                "entity": {
                    "id": "sealed-hatch",
                    "name": "Sealed hatch",
                    "icon": "\U0001f573\ufe0f",
                    "description": "A hatch sealed beyond the wall.",
                    "passable": True,
                },
            },
        ],
    }


def _duplicate_name_map_payload():
    return {
        "id": "duplicate-name-map",
        "name": "Duplicate Name Map",
        "agent_start": {"x": 1, "y": 1},
        "entities": [
            {
                "position": {"x": 2, "y": 1},
                "entity": {
                    "id": "left-statue",
                    "name": "Statue",
                    "icon": "\U0001f5ff",
                    "description": "A statue to the west.",
                    "passable": True,
                    "behaviors": [{"trigger": {"action": "examine"}}],
                },
            },
            {
                "position": {"x": 3, "y": 1},
                "entity": {
                    "id": "right-statue",
                    "name": "Statue",
                    "icon": "\U0001f5ff",
                    "description": "A statue to the east.",
                    "passable": True,
                    "behaviors": [{"trigger": {"action": "examine"}}],
                },
            },
        ],
    }
