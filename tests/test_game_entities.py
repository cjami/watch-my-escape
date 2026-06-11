import pytest
from pydantic import ValidationError

from watch_my_escape.game.models import BehaviorContext, BehaviorResult, Entity, evaluate_entity_behavior


def test_entity_defaults_to_default_state_and_no_behaviors():
    entity = Entity(
        id="stone-wall",
        icon="#",
        description="Cold stone blocks line this side of the room.",
        passable=False,
    )

    assert entity.id == "stone-wall"
    assert entity.active is True
    assert entity.notable is True
    assert entity.color is None
    assert entity.state == "default"
    assert entity.behaviors == ()


def test_entity_accepts_hex_icon_color():
    entity = Entity(
        id="brass-key",
        icon="key",
        color="#FFD447",
        description="A tarnished brass key.",
        passable=True,
    )

    assert entity.color == "#FFD447"


@pytest.mark.parametrize("color", ["yellow", "#fff", "#FFFFFG", "FFD447"])
def test_entity_rejects_invalid_icon_color(color):
    with pytest.raises(ValidationError):
        Entity.model_validate(
            {
                "id": "brass-key",
                "icon": "key",
                "color": color,
                "description": "A tarnished brass key.",
                "passable": True,
            }
        )


@pytest.mark.parametrize("field", ["id", "icon", "description"])
def test_entity_rejects_blank_required_text_fields(field):
    payload = {
        "id": "brass-key",
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
        icon="door",
        description="A heavy locked door.",
        passable=False,
        state="locked",
    )
    lever = Entity.model_validate(
        {
            "id": "brass-lever",
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


def test_behavior_state_conditions_are_case_insensitive():
    entity = Entity.model_validate(
        {
            "id": "suspicious-shelf",
            "icon": "shelf",
            "description": "A shelf with a hidden note.",
            "passable": False,
            "state": "default",
            "behaviors": [
                {
                    "trigger": {"action": "examine"},
                    "conditions": [{"state": "DEFAULT"}],
                    "effects": [{"type": "message", "text": "A note falls out."}],
                }
            ],
        }
    )

    result = evaluate_entity_behavior(
        entity,
        action="examine",
        context=BehaviorContext(entities={entity.id: entity}),
    )

    assert result.messages == ("A note falls out.",)


def test_use_item_behavior_can_match_inventory_item():
    entity = Entity.model_validate(
        {
            "id": "locked-door",
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


def test_simple_behavior_can_match_multiple_actions():
    entity = Entity.model_validate(
        {
            "id": "control-button",
            "icon": "button",
            "description": "A broad button waits on the wall.",
            "passable": False,
            "behaviors": [
                {
                    "trigger": {"action": "push", "actions": ["push", "operate"]},
                    "effects": [{"type": "message", "text": "A panel opens nearby."}],
                }
            ],
        }
    )

    push_result = evaluate_entity_behavior(
        entity,
        action="push",
        context=BehaviorContext(entities={entity.id: entity}),
    )
    operate_result = evaluate_entity_behavior(
        entity,
        action="operate",
        context=BehaviorContext(entities={entity.id: entity}),
    )
    pull_result = evaluate_entity_behavior(
        entity,
        action="pull",
        context=BehaviorContext(entities={entity.id: entity}),
    )

    assert push_result.messages == ("A panel opens nearby.",)
    assert operate_result.messages == ("A panel opens nearby.",)
    assert pull_result == BehaviorResult()


@pytest.mark.parametrize(
    "trigger",
    [
        {"action": "talk_to", "actions": ["push"]},
        {"action": "use_item", "actions": ["operate"]},
        {"action": "push", "actions": ["push", "push"]},
        {"action": "push", "actions": ["operate"]},
        {"action": "push", "actions": ["push"], "item": "brass-key"},
        {"action": "push", "actions": ["push"], "phrase": "hello"},
    ],
)
def test_multi_action_trigger_rejects_non_simple_shapes(trigger):
    with pytest.raises(ValidationError):
        Entity.model_validate(
            {
                "id": "control-button",
                "icon": "button",
                "description": "A broad button waits on the wall.",
                "passable": False,
                "behaviors": [{"trigger": trigger}],
            }
        )


def test_talk_to_behavior_matches_normalized_phrase():
    entity = Entity.model_validate(
        {
            "id": "gatekeeper",
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
