import pytest
from pydantic import BaseModel, ValidationError

from watch_my_escape.game.action_options import build_available_action_model
from watch_my_escape.game.actions import EscapeRoomAction
from watch_my_escape.game.maps import GameMap, GameSessionState
from watch_my_escape.game.runtime import STARTING_SANITY, apply_agent_action, render_game_state_for_agent

EMOTION = "curious"


def test_action_on_sealed_entity_fails_and_costs_one_sanity():
    session = GameSessionState(map=GameMap.model_validate(_sealed_map_payload()))

    result = apply_agent_action(session, STARTING_SANITY, _action("examine", target="sealed-hatch"))

    assert result.sanity == 99
    assert result.session == session
    assert result.movement_path == ()
    assert "no active or inventory target matches" in result.message


def test_failed_action_still_reduces_sanity():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    result = apply_agent_action(session, STARTING_SANITY, _action("open", target="missing door"))

    assert result.sanity == 99
    assert result.session == session
    assert "no active or inventory target matches" in result.message


def test_inventory_entities_can_be_used_with_each_other():
    session = GameSessionState(
        map=GameMap.model_validate(
            {
                "id": "item-combo-map",
                "name": "Item Combo Map",
                "agent_start": {"x": 1, "y": 1},
                "entities": [
                    {
                        "position": {"x": 2, "y": 1},
                        "entity": {
                            "id": "small-key",
                            "icon": "\U0001f511",
                            "description": "A small key.",
                            "passable": True,
                            "active": False,
                        },
                    },
                    {
                        "position": {"x": 1, "y": 1},
                        "entity": {
                            "id": "locked-box",
                            "icon": "\U0001f4e6",
                            "description": "A locked box.",
                            "passable": True,
                            "active": False,
                            "state": "locked",
                            "behaviors": [
                                {
                                    "trigger": {"action": "use_item", "item": "small-key"},
                                    "effects": [
                                        {"type": "message", "text": "The box clicks open."},
                                        {"type": "set_entity_state", "state": "open"},
                                    ],
                                }
                            ],
                        },
                    },
                ],
            }
        ),
        inventory=("small-key", "locked-box"),
    )
    action_model = _available_action_model(session)

    assert action_model.model_validate(
        {"action": "use_item", "item": "small-key", "target": "locked-box", "emotion": EMOTION}
    )
    result = apply_agent_action(session, STARTING_SANITY, _action("use_item", item="small-key", target="locked-box"))

    assert result.sanity == 99
    assert result.movement_path == ()
    assert result.message == "The box clicks open."
    assert result.session.map.entities_by_id()["locked-box"].state == "open"


def test_action_without_matching_behavior_reports_only_no_effect():
    session = GameSessionState(
        map=GameMap.model_validate(
            {
                "id": "default-message-map",
                "name": "Default Message Map",
                "agent_start": {"x": 1, "y": 1},
                "entities": [
                    {
                        "position": {"x": 1, "y": 1},
                        "entity": {
                            "id": "locked-door",
                            "icon": "\U0001f6aa",
                            "description": "A locked door.",
                            "passable": False,
                        },
                    }
                ],
            }
        )
    )

    result = apply_agent_action(session, STARTING_SANITY, _action("open", target="locked-door"))

    assert result.message == "Nothing happens."


def test_use_item_without_matching_behavior_reports_only_no_effect():
    session = GameSessionState(
        map=GameMap.model_validate(
            {
                "id": "default-use-item-message-map",
                "name": "Default Use Item Message Map",
                "agent_start": {"x": 1, "y": 1},
                "entities": [
                    {
                        "position": {"x": 1, "y": 1},
                        "entity": {
                            "id": "locked-box",
                            "icon": "\U0001f4e6",
                            "description": "A locked box.",
                            "passable": True,
                            "active": False,
                        },
                    }
                ],
            }
        ),
        inventory=("small-key", "locked-box"),
    )

    result = apply_agent_action(session, STARTING_SANITY, _action("use_item", item="small-key", target="locked-box"))

    assert result.message == "Nothing happens."


def test_inventory_entity_can_be_opened_without_movement():
    session = GameSessionState(
        map=GameMap.model_validate(
            {
                "id": "inventory-action-map",
                "name": "Inventory Action Map",
                "agent_start": {"x": 1, "y": 1},
                "unplaced_entities": [
                    {
                        "id": "small-box",
                        "icon": "\U0001f4e6",
                        "description": "A small box.",
                        "passable": True,
                        "state": "closed",
                        "behaviors": [
                            {
                                "trigger": {"action": "open"},
                                "effects": [
                                    {"type": "message", "text": "The box opens."},
                                    {"type": "set_entity_state", "state": "open"},
                                ],
                            }
                        ],
                    }
                ],
            }
        ),
        inventory=("small-box",),
    )
    action_model = _available_action_model(session)

    assert action_model.model_validate({"action": "open", "target": "small-box", "emotion": EMOTION})
    result = apply_agent_action(session, STARTING_SANITY, _action("open", target="small-box"))

    assert result.sanity == 99
    assert result.movement_path == ()
    assert result.message == "The box opens."
    assert result.session.map.entities_by_id()["small-box"].state == "open"


def test_pick_up_does_not_target_inventory_items():
    session = GameSessionState(
        map=GameMap.model_validate(
            {
                "id": "inventory-pick-up-map",
                "name": "Inventory Pick Up Map",
                "agent_start": {"x": 1, "y": 1},
                "unplaced_entities": [
                    {
                        "id": "small-box",
                        "icon": "\U0001f4e6",
                        "description": "A small box.",
                        "passable": True,
                    }
                ],
            }
        ),
        inventory=("small-box",),
    )
    schema = _available_action_model(session).model_json_schema()

    assert "AvailablePickUpAction" not in schema.get("$defs", {})


def test_add_inventory_can_add_unplaced_entity():
    session = GameSessionState(
        map=GameMap.model_validate(
            {
                "id": "hidden-item-map",
                "name": "Hidden Item Map",
                "agent_start": {"x": 1, "y": 1},
                "entities": [
                    {
                        "position": {"x": 1, "y": 1},
                        "entity": {
                            "id": "wooden-box",
                            "icon": "\U0001f4e6",
                            "description": "A wooden box.",
                            "passable": True,
                            "behaviors": [
                                {
                                    "trigger": {"action": "open"},
                                    "effects": [
                                        {"type": "message", "text": "There is a folded note inside."},
                                        {"type": "add_inventory", "entity_id": "folded-note"},
                                    ],
                                }
                            ],
                        },
                    }
                ],
                "unplaced_entities": [
                    {
                        "id": "folded-note",
                        "icon": "\U0001f4dd",
                        "description": "A note with a clue.",
                        "passable": True,
                    }
                ],
            }
        )
    )

    result = apply_agent_action(session, STARTING_SANITY, _action("open", target="wooden-box"))

    assert result.message == "There is a folded note inside."
    assert result.session.inventory == ("folded-note",)


def test_available_action_model_schema_requires_action_discriminator():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))
    schema = _available_action_model(session).model_json_schema()

    assert "action" in schema["$defs"]["AvailablePickUpAction"]["required"]
    assert list(schema["$defs"]["AvailablePickUpAction"]["properties"]) == ["action", "target", "emotion"]


def test_available_action_model_builds_fresh_schema_for_matching_action_contexts():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    assert build_available_action_model(session) is not build_available_action_model(session)


def test_available_action_model_respects_inventory_context():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    base_model = _available_action_model(session)
    inventory_model = _available_action_model(session.model_copy(update={"inventory": ("small-key",)}))

    assert inventory_model is not base_model
    assert "AvailableUseItemAction" in inventory_model.model_json_schema()["$defs"]


def test_available_action_model_constrains_targets_to_visible_entity_ids():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    action_model = _available_action_model(session)

    assert action_model.model_validate({"action": "examine", "target": "left-statue", "emotion": EMOTION})
    assert action_model.model_validate({"action": "examine", "target": "right-statue", "emotion": EMOTION})
    with pytest.raises(ValidationError, match="target"):
        action_model.model_validate({"action": "examine", "target": "statue", "emotion": EMOTION})
    with pytest.raises(ValidationError, match="target"):
        action_model.model_validate({"action": "examine", "target": "blocked-door", "emotion": EMOTION})


def test_available_action_model_requires_spoken_text_for_talk_to_targets():
    session = GameSessionState(map=GameMap.model_validate(_talking_map_payload()))
    action_model = _available_action_model(session)

    assert action_model.model_validate(
        {"action": "talk_to", "target": "gatekeeper", "text": "silver moon", "emotion": EMOTION}
    )
    with pytest.raises(ValidationError, match="text"):
        action_model.model_validate({"action": "talk_to", "target": "gatekeeper", "emotion": EMOTION})


def test_render_game_state_for_agent_describes_inventory_items():
    session = GameSessionState(
        map=GameMap.model_validate(
            {
                "id": "inventory-description-map",
                "name": "Inventory Description Map",
                "agent_start": {"x": 1, "y": 1},
                "unplaced_entities": [
                    {
                        "id": "folded-note",
                        "icon": "\U0001f4dd",
                        "description": "A folded note marked {state}.",
                        "passable": True,
                        "state": "unread",
                    }
                ],
            }
        ),
        inventory=("folded-note",),
    )

    game_state = render_game_state_for_agent(session, STARTING_SANITY)

    assert "Inventory (items you are carrying):" in game_state
    assert "- folded-note: A folded note marked unread." in game_state


def test_render_game_state_for_agent_keeps_unknown_inventory_items_readable():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()), inventory=("missing-item",))

    game_state = render_game_state_for_agent(session, STARTING_SANITY)

    assert "- missing-item" in game_state


def _action(action: str, **values: object) -> EscapeRoomAction:
    return EscapeRoomAction.model_validate({"action": action, "emotion": EMOTION, **values})


def _available_action_model(session: GameSessionState) -> type[BaseModel]:
    action_model = build_available_action_model(session)
    assert action_model is not None
    return action_model


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
                        "icon": "\U0001f9f1",
                        "description": "A solid wall.",
                        "passable": False,
                        "notable": False,
                    },
                }
                for y in range(15)
            ],
            {
                "position": {"x": 3, "y": 1},
                "entity": {
                    "id": "sealed-hatch",
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
                    "icon": "\U0001f5ff",
                    "description": "A statue to the east.",
                    "passable": True,
                    "behaviors": [{"trigger": {"action": "examine"}}],
                },
            },
        ],
    }


def _talking_map_payload():
    return {
        "id": "talking-map",
        "name": "Talking Map",
        "agent_start": {"x": 1, "y": 1},
        "entities": [
            {
                "position": {"x": 2, "y": 1},
                "entity": {
                    "id": "gatekeeper",
                    "icon": "\U0001f9cd",
                    "description": "A gatekeeper waits for a password.",
                    "passable": False,
                    "behaviors": [{"trigger": {"action": "talk_to", "phrase": "silver moon"}}],
                },
            }
        ],
    }
