from watch_my_escape.agent.prompts import build_deliberation_messages
from watch_my_escape.agent.runner import ThinkActTurn, run_think_act_turn
from watch_my_escape.game.actions import EscapeRoomAction, ExamineAction
from watch_my_escape.llm.models import InferenceRequest, InferenceResponse


class FakeProvider:
    """Provider fake that records requests and returns a deliberation then action."""

    def __init__(self) -> None:
        self.requests: list[InferenceRequest] = []

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Record a request and return the next scripted response."""
        self.requests.append(request)
        if len(self.requests) == 1:
            return InferenceResponse(
                content=(
                    "<think>Inspect the key before trying the door.</think>\nIntended action: examine the brass key."
                )
            )
        return InferenceResponse(content='{"action":"examine","target":"brass key","emotion":"curious"}')


def test_run_think_act_turn_deliberates_before_constrained_action():
    provider = FakeProvider()

    result = run_think_act_turn(
        provider,
        ThinkActTurn(
            game_state="A brass key rests on a table beside a locked door.",
            action_model=EscapeRoomAction,
            history=("Looked around the room.",),
        ),
    )

    assert result.deliberation == (
        "<think>Inspect the key before trying the door.</think>\nIntended action: examine the brass key."
    )
    assert result.action == EscapeRoomAction(
        root=ExamineAction(action="examine", target="brass key", emotion="curious")
    )
    assert provider.requests[0].structured_output is None
    assert provider.requests[0].settings.temperature == 1.0
    assert provider.requests[0].settings.max_tokens == 4096
    deliberation_system_prompt = provider.requests[0].messages[0].content
    assert "Assess your surroundings" in deliberation_system_prompt
    assert "consider all possible actions and targets" in deliberation_system_prompt
    assert "short sentence of your reasoning" in deliberation_system_prompt
    assert "named action and target" in deliberation_system_prompt
    deliberation_prompt = provider.requests[0].messages[-1].content
    assert "Game state:" in deliberation_prompt
    assert "Objective:" not in deliberation_prompt
    assert "Available actions:" in deliberation_prompt
    assert "Recent actions, oldest to newest:" in deliberation_prompt
    assert "History:" not in deliberation_prompt
    assert "- examine(target)" in deliberation_prompt
    assert "- use_item(item, target)" in deliberation_prompt
    assert "- take(target): Take an object and add it to your inventory." in deliberation_prompt
    assert "- open(target): Open an object." in deliberation_prompt
    assert "entity" not in deliberation_prompt.casefold()
    assert "target: a visible object" not in deliberation_prompt
    assert "item: an item currently in inventory" not in deliberation_prompt
    assert provider.requests[1].structured_output is not None
    assert provider.requests[1].settings.temperature == 0.0
    assert provider.requests[1].settings.max_tokens == 256
    action_prompt = provider.requests[1].messages[-1].content
    assert "Available actions:" in action_prompt
    assert "Inspect the key before trying the door." not in provider.requests[1].messages[-1].content
    assert "<think>" not in provider.requests[1].messages[-1].content
    assert "Intended action: examine the brass key." in provider.requests[1].messages[-1].content


def test_run_think_act_turn_strips_thinking_wrappers_from_action_response():
    class ThinkingActionProvider(FakeProvider):
        def complete(self, request: InferenceRequest) -> InferenceResponse:
            self.requests.append(request)
            if len(self.requests) == 1:
                return InferenceResponse(content="The key is the most obvious lead.")
            return InferenceResponse(
                content=(
                    "<think>I should not show this in the final action.</think>\n"
                    '{"action":"examine","target":"brass key","emotion":"curious"}'
                )
            )

    result = run_think_act_turn(
        ThinkingActionProvider(),
        ThinkActTurn(
            game_state="A brass key rests on a table.",
            action_model=EscapeRoomAction,
        ),
    )

    assert isinstance(result.action, EscapeRoomAction)
    assert isinstance(result.action.root, ExamineAction)
    assert result.action.root.target == "brass key"


def test_recent_actions_are_limited_to_last_ten_entries():
    messages = build_deliberation_messages(
        game_state="A brass key rests on a table.",
        action_model=EscapeRoomAction,
        history=tuple(f"Action {index}" for index in range(1, 12)),
    )

    prompt = messages[-1].content
    assert "- Action 1\n" not in prompt
    assert "- Action 2\n" in prompt
    assert "- Action 11" in prompt
