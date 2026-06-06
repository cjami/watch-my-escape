from watch_my_escape.agent.runner import ThinkActTurn, run_think_act_turn
from watch_my_escape.game.actions import InspectObjectAction
from watch_my_escape.llm.models import InferenceRequest, InferenceResponse


class FakeProvider:
    """Provider fake that records requests and returns a deliberation then action."""

    def __init__(self) -> None:
        self.requests: list[InferenceRequest] = []

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Record a request and return the next scripted response."""
        self.requests.append(request)
        if len(self.requests) == 1:
            return InferenceResponse(content="<think>Inspect the key before trying the door.</think>")
        return InferenceResponse(content='{"action":"inspect_object","object_name":"brass key","detail_level":2}')


def test_run_think_act_turn_deliberates_before_constrained_action():
    provider = FakeProvider()

    result = run_think_act_turn(
        provider,
        ThinkActTurn(
            room_state="A brass key rests on a table beside a locked door.",
            objective="Escape the room.",
            action_model=InspectObjectAction,
            history=("Looked around the room.",),
        ),
    )

    assert result.deliberation == "<think>Inspect the key before trying the door.</think>"
    assert result.action == InspectObjectAction(action="inspect_object", object_name="brass key", detail_level=2)
    assert provider.requests[0].structured_output is None
    assert provider.requests[0].settings.temperature == 1.0
    assert provider.requests[0].settings.max_tokens == 2048
    assert provider.requests[1].structured_output is not None
    assert provider.requests[1].settings.temperature == 0.0
    assert "Inspect the key before trying the door." in provider.requests[1].messages[-1].content


def test_run_think_act_turn_strips_thinking_wrappers_from_action_response():
    class ThinkingActionProvider(FakeProvider):
        def complete(self, request: InferenceRequest) -> InferenceResponse:
            self.requests.append(request)
            if len(self.requests) == 1:
                return InferenceResponse(content="The key is the most obvious lead.")
            return InferenceResponse(
                content=(
                    "<think>I should not show this in the final action.</think>\n"
                    '{"action":"inspect_object","object_name":"brass key","detail_level":2}'
                )
            )

    result = run_think_act_turn(
        ThinkingActionProvider(),
        ThinkActTurn(
            room_state="A brass key rests on a table.",
            objective="Escape the room.",
            action_model=InspectObjectAction,
        ),
    )

    assert isinstance(result.action, InspectObjectAction)
    assert result.action.object_name == "brass key"
