import pytest
from pydantic import ValidationError

from watch_my_escape.game.actions import (
    CloseAction,
    EscapeRoomAction,
    ExamineAction,
    MoveAction,
    OpenAction,
    PickUpAction,
    PullAction,
    PushAction,
    TakeNoteAction,
    TalkToAction,
    UseItemAction,
)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (UseItemAction, {"action": "use_item", "item": "brass key", "target": "locked door", "emotion": "🤔"}),
        (PickUpAction, {"action": "pick_up", "target": "brass key", "emotion": "🙂"}),
        (OpenAction, {"action": "open", "target": "locked door", "emotion": "😀"}),
        (CloseAction, {"action": "close", "target": "cabinet", "emotion": "😌"}),
        (ExamineAction, {"action": "examine", "target": "painting", "emotion": "🧐"}),
        (PushAction, {"action": "push", "target": "red button", "emotion": "😬"}),
        (PullAction, {"action": "pull", "target": "lever", "emotion": "😤"}),
        (TalkToAction, {"action": "talk_to", "target": "guard", "emotion": "😊"}),
        (TakeNoteAction, {"action": "take_note", "text": "The dial stopped at 12.", "emotion": "🤓"}),
        (MoveAction, {"action": "move", "direction": "North", "emotion": "😎"}),
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
        EscapeRoomAction.model_validate({"action": "inspect_object", "target": "painting", "emotion": "🤔"})
