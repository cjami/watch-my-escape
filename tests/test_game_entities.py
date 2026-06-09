import pytest
from pydantic import ValidationError

from watch_my_escape.game.models import BehaviorContext, BehaviorResult, Entity, evaluate_entity_behavior


def test_entity_defaults_to_default_state_and_no_behaviors():
    entity = Entity(
        id="stone-wall",
        name="Stone wall",
        icon="#",
        description="Cold stone blocks line this side of the room.",
        passable=False,
    )

    assert entity.id == "stone-wall"
    assert entity.active is True
    assert entity.notable is True
    assert entity.state == "default"
    assert entity.behaviors == ()


@pytest.mark.parametrize("field", ["id", "name", "icon", "description"])
def test_entity_rejects_blank_required_text_fields(field):
    payload = {
        "id": "brass-key",
        "name": "Brass key",
        "icon": "key",
        "description": "A tarnished brass key.",
        "passable": True,
    }
    payload[field] = ""

    with pytest.raises(ValidationError):
        Entity.model_validate(payload)


def test_entity_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Entity.model_validate(
            {
                "id": "brass-key",
                "name": "Brass key",
                "icon": "key",
                "description": "A tarnished brass key.",
                "passable": True,
                "weight": "heavy",
            }
        )


def test_entity_json_round_trip_with_behavior():
    entity = Entity.model_validate(
        {
            "id": "brass-key",
            "name": "Brass key",
            "icon": "key",
            "description": "A tarnished brass key.",
            "passable": True,
            "behaviors": [
                {
                    "trigger": {"action": "examine"},
                    "effects": [{"type": "message", "text": "The teeth are marked with a tiny sun."}],
                }
            ],
        }
    )

    restored = Entity.model_validate_json(entity.model_dump_json())

    assert restored == entity


def test_examine_behavior_returns_message_text():
    entity = Entity.model_validate(
        {
            "id": "clock",
            "name": "Wall clock",
            "icon": "clock",
            "description": "A stopped wall clock.",
            "passable": False,
            "behaviors": [
                {
                    "trigger": {"action": "examine"},
                    "effects": [{"type": "message", "text": "The clock is frozen at twelve."}],
                }
            ],
        }
    )

    result = evaluate_entity_behavior(
        entity,
        action="examine",
        context=BehaviorContext(entities={entity.id: entity}),
    )

    assert result == BehaviorResult(messages=("The clock is frozen at twelve.",))
    assert result.text == "The clock is frozen at twelve."


def test_pick_up_behavior_adds_item_to_inventory():
    entity = Entity.model_validate(
        {
            "id": "brass-key",
            "name": "Brass key",
            "icon": "key",
            "description": "A tarnished brass key.",
            "passable": True,
            "behaviors": [
                {
                    "trigger": {"action": "pick_up"},
                    "effects": [
                        {"type": "message", "text": "You pick up the brass key."},
                        {"type": "add_inventory", "entity_id": "brass-key"},
                        {"type": "set_entity_active", "active": False},
                    ],
                }
            ],
        }
    )

    result = evaluate_entity_behavior(
        entity,
        action="pick_up",
        context=BehaviorContext(entities={entity.id: entity}),
    )

    assert result.messages == ("You pick up the brass key.",)
    assert result.add_inventory == ("brass-key",)
    assert result.entity_updates["brass-key"].active is False
    assert result.entity_updates["brass-key"].state is None


def test_lever_behavior_can_change_another_entity_when_condition_matches():
    door = Entity(
        id="north-door",
        name="North door",
        icon="door",
        description="A heavy locked door.",
        passable=False,
        state="locked",
    )
    lever = Entity.model_validate(
        {
            "id": "brass-lever",
            "name": "Brass lever",
            "icon": "lever",
            "description": "A lever set into the wall.",
            "passable": False,
            "state": "ready",
            "behaviors": [
                {
                    "trigger": {"action": "pull"},
                    "conditions": [{"state": "ready"}],
                    "effects": [
                        {"type": "message", "text": "The lever clunks down and the north door opens."},
                        {"type": "set_entity_state", "entity_id": "north-door", "state": "open"},
                        {"type": "set_entity_passable", "entity_id": "north-door", "passable": True},
                        {"type": "set_entity_state", "state": "used"},
                    ],
                }
            ],
        }
    )

    result = evaluate_entity_behavior(
        lever,
        action="pull",
        context=BehaviorContext(entities={lever.id: lever, door.id: door}),
    )

    assert result.messages == ("The lever clunks down and the north door opens.",)
    assert result.entity_updates["north-door"].state == "open"
    assert result.entity_updates["north-door"].passable is True
    assert result.entity_updates["brass-lever"].state == "used"


def test_behavior_conditions_that_do_not_match_produce_no_effects():
    entity = Entity.model_validate(
        {
            "id": "brass-lever",
            "name": "Brass lever",
            "icon": "lever",
            "description": "A lever set into the wall.",
            "passable": False,
            "state": "stuck",
            "behaviors": [
                {
                    "trigger": {"action": "pull"},
                    "conditions": [{"state": "ready"}],
                    "effects": [{"type": "message", "text": "The lever opens the door."}],
                }
            ],
        }
    )

    result = evaluate_entity_behavior(
        entity,
        action="pull",
        context=BehaviorContext(entities={entity.id: entity}),
    )

    assert result == BehaviorResult()


def test_use_item_behavior_can_match_inventory_item():
    entity = Entity.model_validate(
        {
            "id": "locked-door",
            "name": "Locked door",
            "icon": "door",
            "description": "A locked door.",
            "passable": False,
            "behaviors": [
                {
                    "trigger": {"action": "use_item", "item": "brass-key"},
                    "effects": [{"type": "set_entity_state", "state": "unlocked"}],
                }
            ],
        }
    )

    wrong_item_result = evaluate_entity_behavior(
        entity,
        action="use_item",
        item="silver-key",
        context=BehaviorContext(entities={entity.id: entity}, inventory=("silver-key",)),
    )
    matching_item_result = evaluate_entity_behavior(
        entity,
        action="use_item",
        item="brass-key",
        context=BehaviorContext(entities={entity.id: entity}, inventory=("brass-key",)),
    )

    assert wrong_item_result == BehaviorResult()
    assert matching_item_result.entity_updates["locked-door"].state == "unlocked"


def test_talk_to_behavior_matches_normalized_phrase():
    entity = Entity.model_validate(
        {
            "id": "gatekeeper",
            "name": "Gatekeeper",
            "icon": "guard",
            "description": "A guard waits for the password.",
            "passable": False,
            "behaviors": [
                {
                    "trigger": {"action": "talk_to", "phrase": "silver moon"},
                    "effects": [{"type": "message", "text": "The gatekeeper steps aside."}],
                }
            ],
        }
    )

    wrong_phrase_result = evaluate_entity_behavior(
        entity,
        action="talk_to",
        text="gold sun",
        context=BehaviorContext(entities={entity.id: entity}),
    )
    matching_phrase_result = evaluate_entity_behavior(
        entity,
        action="talk_to",
        text="  I think the password is SILVER   MOON, please let me pass.  ",
        context=BehaviorContext(entities={entity.id: entity}),
    )

    assert wrong_phrase_result == BehaviorResult()
    assert matching_phrase_result.messages == ("The gatekeeper steps aside.",)
