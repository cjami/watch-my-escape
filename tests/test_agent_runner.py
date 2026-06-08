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
        return InferenceResponse(content='{"action":"examine","target":"brass key","emotion":"🤔"}')


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
    assert result.action == EscapeRoomAction(root=ExamineAction(action="examine", target="brass key", emotion="🤔"))
    assert provider.requests[0].structured_output is None
    assert provider.requests[0].settings.temperature == 1.0
    assert provider.requests[0].settings.max_tokens == 2048
    deliberation_system_prompt = provider.requests[0].messages[0].content
    assert "Briefly outline your overall plan." in deliberation_system_prompt
    assert "Choose the immediate next single action to perform." in deliberation_system_prompt
    assert "Choose a target for this action." in deliberation_system_prompt
    assert "Provide a reason why you wish to perform this action." in deliberation_system_prompt
    deliberation_prompt = provider.requests[0].messages[-1].content
    assert "Game state:" in deliberation_prompt
    assert "Objective:" not in deliberation_prompt
    assert "Available actions:" in deliberation_prompt
    assert "Recent actions:" in deliberation_prompt
    assert "History:" not in deliberation_prompt
    assert "- examine(target)" in deliberation_prompt
    assert "- use_item(item, target)" in deliberation_prompt
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
                    '{"action":"examine","target":"brass key","emotion":"🤔"}'
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
