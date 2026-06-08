"""Built-in maps for early escape-room demos."""

from __future__ import annotations

from watch_my_escape.game.maps import GameMap

KEY_ICON = "\U0001f511"
DOOR_ICON = "\U0001f6aa"
WALL_ICON = "\U0001f9f1"


def create_key_door_map() -> GameMap:
    """Return a tiny map with one key and one locked escape door."""
    wall_positions = [
        {"x": x, "y": y} for x in range(16) for y in range(16) if (x in {0, 15} or y in {0, 15}) and (x, y) != (15, 8)
    ]
    return GameMap.model_validate(
        {
            "id": "key-door-room",
            "name": "Key Door Room",
            "agent_start": {"x": 7, "y": 8},
            "entities": [
                *[
                    {
                        "position": position,
                        "entity": {
                            "id": f"wall-{position['x']}-{position['y']}",
                            "name": "Wall",
                            "icon": WALL_ICON,
                            "description": "A solid wall around the room.",
                            "passable": False,
                            "notable": False,
                        },
                    }
                    for position in wall_positions
                ],
                {
                    "position": {"x": 8, "y": 8},
                    "entity": {
                        "id": "brass-key",
                        "name": "Brass key",
                        "icon": KEY_ICON,
                        "description": "A brass key lies on the floor.",
                        "passable": True,
                        "behaviors": [
                            {
                                "trigger": {"action": "pick_up"},
                                "effects": [
                                    {"type": "message", "text": "You pick up the brass key."},
                                    {"type": "add_inventory", "item": "brass key"},
                                    {"type": "set_entity_visible", "visible": False},
                                ],
                            }
                        ],
                    },
                },
                {
                    "position": {"x": 15, "y": 8},
                    "entity": {
                        "id": "locked-door",
                        "name": "Locked door",
                        "icon": DOOR_ICON,
                        "description": "A locked door bars the exit.",
                        "passable": False,
                        "state": "locked",
                        "behaviors": [
                            {
                                "trigger": {"action": "use_item", "item": "brass key"},
                                "conditions": [{"state": "locked"}],
                                "effects": [
                                    {
                                        "type": "message",
                                        "text": "The brass key turns. The locked door opens, and you escape.",
                                    },
                                    {"type": "set_entity_state", "state": "open"},
                                    {"type": "set_entity_passable", "passable": True},
                                    {"type": "escape_map"},
                                ],
                            }
                        ],
                    },
                },
            ],
        }
    )
