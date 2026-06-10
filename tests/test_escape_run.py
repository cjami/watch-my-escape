from watch_my_escape.agent.escape_run import run_model_escape, run_model_escape_steps
from watch_my_escape.game.maps import GameMap
from watch_my_escape.llm.models import InferenceRequest, InferenceResponse

EMOTION_JSON = "curious"


class ScriptedProvider:
    """Provider fake that records requests and returns scripted actions."""

    def __init__(self, actions: tuple[str, ...]) -> None:
        self.actions = actions
        self.requests: list[InferenceRequest] = []

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Return deliberation text followed by the next scripted action JSON."""
        self.requests.append(request)
        if len(self.requests) % 2 == 1:
            return InferenceResponse(content="I will choose the next useful action.")
        action_index = (len(self.requests) // 2) - 1
        return InferenceResponse(content=self.actions[action_index])


class PairedProvider:
    """Provider fake that returns explicit deliberation/action pairs."""

    def __init__(self, pairs: tuple[tuple[str, str], ...]) -> None:
        self.pairs = pairs
        self.requests: list[InferenceRequest] = []

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Return the next deliberation or action for a pair."""
        self.requests.append(request)
        pair_index = (len(self.requests) - 1) // 2
        if len(self.requests) % 2 == 1:
            return InferenceResponse(content=self.pairs[pair_index][0])
        return InferenceResponse(content=self.pairs[pair_index][1])


def test_run_model_escape_stops_when_the_model_escapes():
    provider = ScriptedProvider(
        (
            f'{{"action":"take","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            f'{{"action":"use_item","item":"brass-key","target":"locked-door","emotion":"{EMOTION_JSON}"}}',
        )
    )

    result = run_model_escape(provider=provider)

    assert result.escaped is True
    assert result.sanity == 98
    assert result.inventory == ("brass-key",)
    assert result.status == "Escaped with 98 sanity remaining."
    assert "Turn 1 - sanity 100 -> 99" in result.transcript
    assert "Turn 2 - sanity 99 -> 98" in result.transcript
    assert "Available actions:" not in result.transcript
    assert "Deliberation: I will choose the next useful action." in result.transcript
    assert "direction: one of" not in result.transcript
    assert "Position: (14, 8)" in result.transcript
    assert len(result.frames) == 8
    assert [frame.position for frame in result.frames[:4]] == ["(7, 8)", "(8, 8)", "(9, 8)", "(10, 8)"]
    assert [frame.delay_ms for frame in result.frames[1:]] == [150] * 7
    assert [frame.action_label for frame in result.frames] == ["", "take", "", "", "", "", "", "use"]


def test_run_model_escape_steps_can_delay_before_first_model_request():
    provider = ScriptedProvider((f'{{"action":"open","target":"missing door","emotion":"{EMOTION_JSON}"}}',))
    frames = run_model_escape_steps(provider=provider, startup_delay_ms=2000)

    first_frame = next(frames)

    assert first_frame.status == "Model run started."
    assert first_frame.delay_ms == 2000
    assert first_frame.action_label == ""
    assert provider.requests == []


def test_run_model_escape_stops_when_sanity_reaches_zero():
    provider = ScriptedProvider((f'{{"action":"open","target":"missing door","emotion":"{EMOTION_JSON}"}}',))

    result = run_model_escape(provider=provider, starting_sanity=1)

    assert result.escaped is False
    assert result.sanity == 0
    assert result.status == "Sanity reached 0 before the model escaped."
    assert len(provider.requests) == 2


def test_run_model_escape_stops_when_no_actions_are_available():
    game_map = GameMap.model_validate(
        {
            "id": "empty-room",
            "name": "Empty Room",
            "agent_start": {"x": 3, "y": 4},
            "entities": [],
        }
    )
    provider = ScriptedProvider(())

    result = run_model_escape(provider=provider, game_map=game_map)

    assert result.status == "No available actions remain before the model escaped."
    assert provider.requests == []
    assert "Action: none" in result.transcript


def test_run_model_escape_offers_use_item_on_visible_distant_door_after_taking_key():
    provider = ScriptedProvider(
        (
            f'{{"action":"take","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            f'{{"action":"use_item","item":"brass-key","target":"locked-door","emotion":"{EMOTION_JSON}"}}',
        )
    )

    run_model_escape(provider=provider)

    action_prompt = provider.requests[3].messages[-1].content
    assert "- use_item(item, target)" in action_prompt
    assert "target: one of locked-door" not in action_prompt
    assert '"action":"take"' not in action_prompt
    assert "You took brass-key -> You take the brass key." in action_prompt


def test_run_model_escape_prompts_include_full_action_vocabulary():
    provider = PairedProvider(
        (
            (
                "The next useful step is to take the key.",
                f'{{"action":"take","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            ),
        )
    )

    run_model_escape(provider=provider, starting_sanity=1)

    deliberation_prompt = provider.requests[0].messages[-1].content
    action_prompt = provider.requests[1].messages[-1].content
    assert "- close(target): Close an object." in action_prompt
    assert "- push(target): Push an object." in action_prompt
    assert "- pull(target): Pull an object." in action_prompt
    assert "- talk_to(target, text): Say something to an object or character." in action_prompt
    assert "- operate(target): Operate a device, mechanism, or control." in action_prompt
    assert "- use_item(item, target): Use an object from your inventory on another object." in deliberation_prompt
    assert "- use_item(item, target): Use an object from your inventory on another object." in action_prompt


def test_run_model_escape_keeps_general_action_descriptions_after_taking_item():
    provider = PairedProvider(
        (
            (
                "The next useful step is to take the key.",
                f'{{"action":"take","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            ),
        )
    )

    result = run_model_escape(provider=provider, starting_sanity=1)

    action_prompt = provider.requests[1].messages[-1].content
    assert "- take(target)" in action_prompt
    assert "- open(target)" in action_prompt
    assert "target: one of brass-key" not in action_prompt
    assert result.frames[-1].position == "(8, 8)"


def test_run_model_escape_rejects_missing_discriminator_when_multiple_actions_are_available():
    provider = PairedProvider(
        (
            (
                "I will take the brass key.",
                f'{{"target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            ),
        )
    )

    result = run_model_escape(provider=provider, starting_sanity=1)

    assert result.sanity == 0
    assert result.frames[-1].position == "(7, 8)"
    assert result.frames[-1].action_label == ""
    assert "Deliberation: I will take the brass key." in result.transcript
    assert "Model returned an action outside the current grammar" in result.transcript


def test_run_model_escape_omits_thinking_sections_from_transcript():
    provider = PairedProvider(
        (
            (
                "<think>I should quietly reason through the password.</think>\nI will take the key.",
                f'{{"action":"take","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            ),
        )
    )

    result = run_model_escape(provider=provider, starting_sanity=1)

    assert "<think>" not in result.transcript
    assert "</think>" not in result.transcript
    assert "quietly reason" not in result.transcript
    assert "Deliberation: I will take the key." in result.transcript


def test_run_model_escape_renders_action_emotion_as_agent_icon():
    provider = ScriptedProvider((f'{{"action":"take","target":"brass-key","emotion":"{EMOTION_JSON}"}}',))

    result = run_model_escape(provider=provider, starting_sanity=1)

    assert result.frames[-1].map_view[8][8] == "\U0001f914"


def test_run_model_escape_uses_selected_map():
    game_map = GameMap.model_validate(
        {
            "id": "empty-room",
            "name": "Empty Room",
            "agent_start": {"x": 3, "y": 4},
            "entities": [],
        }
    )

    result = run_model_escape(provider=ScriptedProvider(()), game_map=game_map, starting_sanity=0)

    assert result.frames[0].position == "(3, 4)"
    assert result.frames[0].map_view[4][3] == "\U0001f642"
