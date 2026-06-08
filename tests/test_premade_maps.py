from watch_my_escape.game.models import Coordinate
from watch_my_escape.game.premade_maps import create_key_door_map, get_premade_map, list_premade_maps


def test_premade_map_registry_loads_key_door_room_json():
    premade_map = get_premade_map("key-door-room")

    assert premade_map.id == "key-door-room"
    assert premade_map.name == "Key Door Room"
    assert "brass key" in premade_map.description
    assert "Escape the room" in premade_map.objective
    assert premade_map.map.agent_start == Coordinate(x=7, y=8)


def test_list_premade_maps_exposes_selection_metadata():
    options = [premade_map.as_selection_option() for premade_map in list_premade_maps()]

    assert options == [
        {
            "id": "key-door-room",
            "name": "Key Door Room",
            "description": "A compact training room with a brass key, a locked door, and one clear escape route.",
            "objective": "Escape the room by picking up the key and using it to unlock the door.",
        }
    ]


def test_key_door_room_helper_uses_bundled_json_map():
    game_map = create_key_door_map()

    assert game_map == get_premade_map("key-door-room").map
    assert game_map.entities_by_id()["brass-key"].icon == "\U0001f511"
    assert game_map.entities_by_id()["locked-door"].icon == "\U0001f6aa"
