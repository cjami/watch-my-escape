import pytest
from pydantic import ValidationError

from watch_my_escape.game.action_options import build_available_action_model
from watch_my_escape.game.actions import EscapeRoomAction
from watch_my_escape.game.maps import GameMap, GameSessionState
from watch_my_escape.game.runtime import STARTING_SANITY, apply_agent_action, render_game_state_for_agent

EMOTION = "\U0001f914"


def test_action_on_sealed_entity_fails_and_costs_one_sanity():
    session = GameSessionState(map=GameMap.model_validate(_sealed_map_payload()))

    result = apply_agent_action(session, STARTING_SANITY, _action("examine", target="sealed-hatch"))

    assert result.sanity == 99
    assert result.session == session
    assert result.movement_path == ()
    assert "no active target matches" in result.message


def test_failed_action_still_reduces_sanity():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    result = apply_agent_action(session, STARTING_SANITY, _action("open", target="missing door"))

    assert result.sanity == 99
    assert result.session == session
    assert "no active target matches" in result.message


def test_write_note_records_journal_and_renders_to_agent():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    result = apply_agent_action(session, STARTING_SANITY, _action("write_note", text="The key should open the door."))

    assert result.sanity == 99
    assert result.session.notes == ("The key should open the door.",)
    assert "Your notes:\n- The key should open the door." in render_game_state_for_agent(result.session, result.sanity)


def test_empty_journal_is_rendered_to_agent():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    assert "Your notes:\n- You have not recorded any notes." in render_game_state_for_agent(session, STARTING_SANITY)


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
                            "name": "Small key",
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
                            "name": "Locked box",
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
    action_model = build_available_action_model(session)

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
                            "name": "Locked door",
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
                            "name": "Locked box",
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


def test_available_action_model_schema_requires_action_discriminator():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))
    schema = build_available_action_model(session).model_json_schema()

    assert "action" in schema["$defs"]["AvailablePickUpAction"]["required"]
    assert "action" in schema["$defs"]["AvailableWriteNoteAction"]["required"]


def test_available_action_model_is_reused_for_matching_action_contexts():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    assert build_available_action_model(session) is build_available_action_model(session)


def test_available_action_model_cache_respects_inventory_context():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    base_model = build_available_action_model(session)
    inventory_model = build_available_action_model(session.model_copy(update={"inventory": ("small-key",)}))

    assert inventory_model is not base_model
    assert "AvailableUseItemAction" in inventory_model.model_json_schema()["$defs"]


def test_available_action_model_accepts_target_text_for_runtime_resolution():
    session = GameSessionState(map=GameMap.model_validate(_duplicate_name_map_payload()))

    action_model = build_available_action_model(session)

    assert action_model.model_validate({"action": "examine", "target": "left-statue", "emotion": EMOTION})
    assert action_model.model_validate({"action": "examine", "target": "right-statue", "emotion": EMOTION})
    assert action_model.model_validate({"action": "examine", "target": "statue", "emotion": EMOTION})
    with pytest.raises(ValidationError, match="target"):
        action_model.model_validate({"action": "examine", "target": "", "emotion": EMOTION})


def test_available_action_model_requires_spoken_text_for_talk_to_targets():
    session = GameSessionState(map=GameMap.model_validate(_talking_map_payload()))
    action_model = build_available_action_model(session)

    assert action_model.model_validate(
        {"action": "talk_to", "target": "gatekeeper", "text": "silver moon", "emotion": EMOTION}
    )
    with pytest.raises(ValidationError, match="text"):
        action_model.model_validate({"action": "talk_to", "target": "gatekeeper", "emotion": EMOTION})


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
                    "name": "Gatekeeper",
                    "icon": "\U0001f9cd",
                    "description": "A gatekeeper waits for a password.",
                    "passable": False,
                    "behaviors": [{"trigger": {"action": "talk_to", "phrase": "silver moon"}}],
                },
            }
        ],
    }
