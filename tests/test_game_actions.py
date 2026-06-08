import pytest
from pydantic import ValidationError

from watch_my_escape.game.actions import (
    CloseAction,
    EscapeRoomAction,
    ExamineAction,
    OpenAction,
    PickUpAction,
    PullAction,
    PushAction,
    TakeNoteAction,
    TalkToAction,
    UseAction,
    UseItemAction,
)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (UseItemAction, {"action": "use_item", "item": "brass key", "target": "locked door", "emotion": "\U0001f914"}),
        (UseAction, {"action": "use", "target": "keypad", "emotion": "\U0001f914"}),
        (PickUpAction, {"action": "pick_up", "target": "brass key", "emotion": "\U0001f642"}),
        (OpenAction, {"action": "open", "target": "locked door", "emotion": "\U0001f600"}),
        (CloseAction, {"action": "close", "target": "cabinet", "emotion": "\U0001f60c"}),
        (ExamineAction, {"action": "examine", "target": "painting", "emotion": "\U0001f9d0"}),
        (PushAction, {"action": "push", "target": "red button", "emotion": "\U0001f62c"}),
        (PullAction, {"action": "pull", "target": "lever", "emotion": "\U0001f624"}),
        (TalkToAction, {"action": "talk_to", "target": "guard", "emotion": "\U0001f60a"}),
        (TakeNoteAction, {"action": "take_note", "text": "The dial stopped at 12.", "emotion": "\U0001f913"}),
    ],
)
def test_allowed_actions_require_smiley_emoji_emotion(model, payload):
    assert model.model_validate(payload).emotion == payload["emotion"]
    assert EscapeRoomAction.model_validate(payload).root.action == payload["action"]


def test_action_emotion_rejects_non_emoji_text():
    with pytest.raises(ValidationError):
        ExamineAction.model_validate({"action": "examine", "target": "painting", "emotion": "curious"})


def test_escape_room_action_rejects_removed_action_names():
    with pytest.raises(ValidationError):
        EscapeRoomAction.model_validate({"action": "inspect_object", "target": "painting", "emotion": "\U0001f914"})
