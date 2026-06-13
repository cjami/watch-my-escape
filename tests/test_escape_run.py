from watch_my_escape.agent.escape_run import TranscriptTurnEvent, run_model_escape, run_model_escape_steps
from watch_my_escape.agent.runner import ThinkActSettings
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
            f'{{"action":"pick_up","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            f'{{"action":"use_item","item":"brass-key","target":"locked-door","emotion":"{EMOTION_JSON}"}}',
        )
    )

    result = run_model_escape(provider=provider)

    assert result.escaped is True
    assert result.sanity == 98
    assert result.inventory == ()
    assert result.status == "Escaped with 98 sanity remaining."
    assert "Turn 1 - sanity 100 -> 99" in result.transcript
    assert "Turn 2 - sanity 99 -> 98" in result.transcript
    assert "Available actions:" not in result.transcript
    assert "Deliberation: I will choose the next useful action." in result.transcript
    assert "direction: one of" not in result.transcript
    assert "Position:" not in result.transcript
    assert "Action: Pick up brass-key" in result.transcript
    assert "Action: Use brass-key on locked-door" in result.transcript
    assert len(result.frames) == 7
    assert [frame.position for frame in result.frames[:4]] == ["(7, 7)", "(8, 7)", "(9, 7)", "(10, 7)"]
    assert [frame.delay_ms for frame in result.frames[1:]] == [150] * 6
    assert [frame.action_label for frame in result.frames] == ["", "pick up", "", "", "", "", "use item"]
    intro_event = result.frames[0].transcript_events[0]
    assert intro_event.kind == "intro"
    turn_events = [event for event in result.frames[-1].transcript_events if isinstance(event, TranscriptTurnEvent)]
    assert [event.kind for event in turn_events] == ["turn", "turn"]
    assert intro_event.message == ""
    assert [entity.id for entity in intro_event.visible_entities] == ["brass-key", "locked-door"]
    assert turn_events[0].action_type == "pick_up"
    assert turn_events[0].action_emoji == "\U0001f590\ufe0f"
    assert turn_events[0].action_text == "Pick up brass-key"
    assert turn_events[0].deliberation == "I will choose the next useful action."
    assert [(effect.kind, effect.text) for effect in turn_events[0].effects] == [
        ("add_inventory", "Added brass-key to inventory."),
        ("set_entity_active", "brass-key became inactive."),
    ]
    assert turn_events[1].action_type == "use_item"
    assert turn_events[1].action_emoji == "\U0001f9f0"
    assert turn_events[1].action_text == "Use brass-key on locked-door"
    assert [(effect.kind, effect.text) for effect in turn_events[1].effects] == [
        ("remove_inventory", "Removed brass-key from inventory."),
        ("set_entity_active", "locked-door became inactive."),
        ("escape", "Escape triggered."),
    ]


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


def test_run_model_escape_uses_configured_deliberation_thinking_flag():
    provider = ScriptedProvider((f'{{"action":"pick_up","target":"brass-key","emotion":"{EMOTION_JSON}"}}',))

    run_model_escape(
        provider=provider,
        starting_sanity=1,
        settings=ThinkActSettings(deliberation_enable_thinking=False),
    )

    assert provider.requests[0].phase == "deliberation"
    assert provider.requests[0].enable_thinking is False
    assert provider.requests[1].phase == "action"
    assert provider.requests[1].enable_thinking is False


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
    turn_event = _last_turn_event(result)
    assert turn_event.action_type == "none"
    assert turn_event.action_text == "No action available"


def test_run_model_escape_offers_use_item_on_visible_distant_door_after_picking_up_key():
    provider = ScriptedProvider(
        (
            f'{{"action":"pick_up","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            f'{{"action":"use_item","item":"brass-key","target":"locked-door","emotion":"{EMOTION_JSON}"}}',
        )
    )

    run_model_escape(provider=provider)

    deliberation_system_prompt = provider.requests[2].messages[0].content
    deliberation_prompt = provider.requests[2].messages[-1].content
    action_prompt = provider.requests[3].messages[-1].content
    assert "- use_item(item, target)" in deliberation_system_prompt
    assert "- use_item(item, target)" not in deliberation_prompt
    assert "- use_item(item, target)" not in action_prompt
    assert "target: one of locked-door" not in action_prompt
    assert '"action":"pick_up"' not in action_prompt
    assert "You picked up brass-key -> You pick up the brass key." in action_prompt


def test_run_model_escape_prompts_include_full_action_vocabulary():
    provider = PairedProvider(
        (
            (
                "The next useful step is to pick up the key.",
                f'{{"action":"pick_up","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            ),
        )
    )

    run_model_escape(provider=provider, starting_sanity=1)

    deliberation_system_prompt = provider.requests[0].messages[0].content
    deliberation_prompt = provider.requests[0].messages[-1].content
    action_prompt = provider.requests[1].messages[-1].content
    assert "- close(target): Close an object." in deliberation_system_prompt
    assert "- push(target): Push an object." in deliberation_system_prompt
    assert "- pull(target): Pull an object." in deliberation_system_prompt
    assert "- talk_to(target, text): Say something to an object or character." in deliberation_system_prompt
    assert "- operate(target): Operate a device, mechanism, or control." in deliberation_system_prompt
    assert "- use_item(item, target): Use your inventory item on another object." in deliberation_system_prompt
    assert "- use_item(item, target): Use your inventory item on another object." not in deliberation_prompt
    assert "- close(target): Close an object." not in action_prompt
    assert "- use_item(item, target): Use your inventory item on another object." not in action_prompt


def test_run_model_escape_keeps_general_action_descriptions_in_deliberation_prompt():
    provider = PairedProvider(
        (
            (
                "The next useful step is to pick up the key.",
                f'{{"action":"pick_up","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            ),
        )
    )

    result = run_model_escape(provider=provider, starting_sanity=1)

    deliberation_system_prompt = provider.requests[0].messages[0].content
    deliberation_prompt = provider.requests[0].messages[-1].content
    action_prompt = provider.requests[1].messages[-1].content
    assert "- pick_up(target)" in deliberation_system_prompt
    assert "- open(target)" in deliberation_system_prompt
    assert "- pick_up(target)" not in deliberation_prompt
    assert "- open(target)" not in deliberation_prompt
    assert "- pick_up(target)" not in action_prompt
    assert "- open(target)" not in action_prompt
    assert "target: one of brass-key" not in action_prompt
    assert result.frames[-1].position == "(8, 7)"


def test_run_model_escape_rejects_missing_discriminator_when_multiple_actions_are_available():
    provider = PairedProvider(
        (
            (
                "I will pick up the brass key.",
                f'{{"target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            ),
        )
    )

    result = run_model_escape(provider=provider, starting_sanity=1)

    assert result.sanity == 0
    assert result.frames[-1].position == "(7, 7)"
    assert result.frames[-1].action_label == ""
    assert "Deliberation: I will pick up the brass key." in result.transcript
    assert "Model returned an action outside the current grammar" in result.transcript
    turn_event = _last_turn_event(result)
    assert turn_event.action_type == "invalid"
    assert turn_event.action_emoji == "\u26a0\ufe0f"
    assert turn_event.deliberation == "I will pick up the brass key."


def test_run_model_escape_omits_thinking_sections_from_transcript():
    provider = PairedProvider(
        (
            (
                "<think>I should quietly reason through the password.</think>\nI will pick up the key.",
                f'{{"action":"pick_up","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            ),
        )
    )

    result = run_model_escape(provider=provider, starting_sanity=1)

    assert "<think>" not in result.transcript
    assert "</think>" not in result.transcript
    assert "quietly reason" not in result.transcript
    assert "Deliberation: I will pick up the key." in result.transcript
    assert _last_turn_event(result).deliberation == "I will pick up the key."


def test_run_model_escape_omits_gemma_thought_channel_from_transcript():
    provider = PairedProvider(
        (
            (
                "<|channel>thought\nI should quietly reason through the password.\n<channel|>\nI will pick up the key.",
                f'{{"action":"pick_up","target":"brass-key","emotion":"{EMOTION_JSON}"}}',
            ),
        )
    )

    result = run_model_escape(provider=provider, starting_sanity=1)

    assert "<|channel>thought" not in result.transcript
    assert "<channel|>" not in result.transcript
    assert "quietly reason" not in result.transcript
    assert "Deliberation: I will pick up the key." in result.transcript
    assert _last_turn_event(result).deliberation == "I will pick up the key."


def test_run_model_escape_transcript_event_highlights_talk_actions():
    provider = PairedProvider(
        (
            (
                "I should say the passphrase.",
                f'{{"action":"talk_to","target":"gatekeeper","text":"silver moon","emotion":"{EMOTION_JSON}"}}',
            ),
        )
    )
    game_map = GameMap.model_validate(
        {
            "id": "talk-room",
            "name": "Talk Room",
            "agent_start": {"x": 1, "y": 1},
            "entities": [
                {
                    "position": {"x": 2, "y": 1},
                    "entity": {
                        "id": "gatekeeper",
                        "icon": "!",
                        "description": "A silent gatekeeper.",
                        "passable": True,
                        "behaviors": [
                            {
                                "trigger": {"action": "talk_to", "phrase": "silver moon"},
                                "effects": [{"type": "message", "text": "The gatekeeper steps aside."}],
                            }
                        ],
                    },
                }
            ],
        }
    )

    result = run_model_escape(provider=provider, game_map=game_map, starting_sanity=1)

    turn_event = _last_turn_event(result)
    assert turn_event.action_type == "talk_to"
    assert turn_event.action_emoji == "\U0001f4ac"
    assert turn_event.action_text == "Talk to gatekeeper"
    assert turn_event.spoken_text == "silver moon"


def test_run_model_escape_renders_action_emotion_as_agent_icon():
    provider = ScriptedProvider((f'{{"action":"pick_up","target":"brass-key","emotion":"{EMOTION_JSON}"}}',))

    result = run_model_escape(provider=provider, starting_sanity=1)

    assert result.frames[-1].map_view[7][8] == "\U0001f914"


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


def _last_turn_event(result):
    event = result.frames[-1].transcript_events[-1]
    assert isinstance(event, TranscriptTurnEvent)
    return event
