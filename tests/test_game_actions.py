import pytest
from pydantic import ValidationError

from watch_my_escape.game.actions import (
    CloseAction,
    EscapeRoomAction,
    ExamineAction,
    OpenAction,
    OperateAction,
    PickUpAction,
    PullAction,
    PushAction,
    TalkToAction,
    UseItemAction,
)
from watch_my_escape.game.emotions import EMOTION_TO_EMOJI, emotion_to_emoji


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (UseItemAction, {"action": "use_item", "item": "brass key", "target": "locked door", "emotion": "curious"}),
        (OperateAction, {"action": "operate", "target": "keypad", "emotion": "focused"}),
        (PickUpAction, {"action": "pick_up", "target": "brass key", "emotion": "happy"}),
        (OpenAction, {"action": "open", "target": "locked door", "emotion": "confident"}),
        (CloseAction, {"action": "close", "target": "cabinet", "emotion": "relieved"}),
        (ExamineAction, {"action": "examine", "target": "painting", "emotion": "curious"}),
        (PushAction, {"action": "push", "target": "red button", "emotion": "worried"}),
        (PullAction, {"action": "pull", "target": "lever", "emotion": "frustrated"}),
        (TalkToAction, {"action": "talk_to", "target": "guard", "text": "silver moon", "emotion": "neutral"}),
    ],
)
def test_allowed_actions_require_known_emotion_word(model, payload):
    assert model.model_validate(payload).emotion == payload["emotion"]
    assert EscapeRoomAction.model_validate(payload).root.action == payload["action"]


def test_action_emotion_rejects_raw_emoji():
    with pytest.raises(ValidationError):
        ExamineAction.model_validate({"action": "examine", "target": "painting", "emotion": "\U0001f914"})


def test_action_emotion_maps_word_to_display_emoji():
    assert len(EMOTION_TO_EMOJI) == 10
    assert emotion_to_emoji("curious") == "\U0001f914"
    assert emotion_to_emoji("frustrated") == "\U0001f616"
    assert emotion_to_emoji("unknown") == "\U0001f642"


def test_action_schema_and_json_put_emotion_after_action_fields():
    schema_properties = list(ExamineAction.model_json_schema()["properties"])
    action = ExamineAction(action="examine", target="painting", emotion="curious")

    assert schema_properties == ["action", "target", "emotion"]
    assert action.model_dump_json() == '{"action":"examine","target":"painting","emotion":"curious"}'


def test_talk_to_action_requires_spoken_text():
    with pytest.raises(ValidationError, match="text"):
        TalkToAction.model_validate({"action": "talk_to", "target": "guard", "emotion": "neutral"})


def test_escape_room_action_rejects_removed_action_names():
    with pytest.raises(ValidationError):
        EscapeRoomAction.model_validate({"action": "inspect_object", "target": "painting", "emotion": "curious"})
