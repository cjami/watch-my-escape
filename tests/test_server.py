from fastapi.testclient import TestClient
from gradio import Server

from watch_my_escape.agent.escape_run import EntityDisplay, EscapeRunFrame, TranscriptIntroEvent, TranscriptTurnEvent
from watch_my_escape.app import server
from watch_my_escape.app.server import (
    GENERATED_STATIC_DIR,
    SOURCE_STATIC_DIR,
    TEMPLATES_DIR,
    WarmProviderStore,
    app_data,
    build_escape_run_response,
    create_app,
    model_preset_options,
    premade_map_options,
)
from watch_my_escape.game.runtime import ActionEffectSummary
from watch_my_escape.llm.client import LlmConfigurationError
from watch_my_escape.llm.config import MODEL_PRESETS
from watch_my_escape.llm.models import InferenceResponse


def test_create_app_returns_gradio_server():
    app = create_app()

    assert isinstance(app, Server)


def test_web_assets_live_inside_package():
    assert TEMPLATES_DIR.joinpath("index.html.jinja").is_file()
    assert TEMPLATES_DIR.joinpath("screens", "_game.html.jinja").is_file()
    assert SOURCE_STATIC_DIR.joinpath("input.css").is_file()
    assert SOURCE_STATIC_DIR.joinpath("app.js").is_file()


def test_keyboard_flow_focus_contract_is_wired():
    app_script = SOURCE_STATIC_DIR.joinpath("app.js").read_text(encoding="utf-8")
    base_styles = SOURCE_STATIC_DIR.joinpath("styles", "base.css").read_text(encoding="utf-8")
    game_runner_script = SOURCE_STATIC_DIR.joinpath("app", "game-runner.js").read_text(encoding="utf-8")
    maps_script = SOURCE_STATIC_DIR.joinpath("app", "maps.js").read_text(encoding="utf-8")
    screens_script = SOURCE_STATIC_DIR.joinpath("app", "screens.js").read_text(encoding="utf-8")
    warmup_script = SOURCE_STATIC_DIR.joinpath("app", "model-warmup.js").read_text(encoding="utf-8")

    assert 'dom.screens.get("menu").addEventListener("keydown", screens.handleMainMenuKeydown);' in app_script
    assert 'if (event.key === "Escape" && handleBackAction())' in app_script
    assert "screens.handleMainMenuKeydown(event)" not in app_script
    assert "modelSelector.handleKeydown(event)" not in app_script
    assert "mapSelector.handleKeydown(event)" not in app_script
    assert 'screen.toggleAttribute("aria-hidden", !isActive);' in screens_script
    assert "screen.inert = !isActive;" in screens_script
    assert 'focusScreen("warmup");' in warmup_script
    assert "focusElement(dom.screens.get(name), { silent: true });" in screens_script
    assert "screens.focusElement(dom.runButton, { silent: true });" in app_script
    assert 'if (event.key === "Enter" || event.key === " ")' not in screens_script
    assert 'if (event.key === "Enter" || event.key === " ")' not in maps_script
    assert 'element.dataset.silentFocus = "true";' in screens_script
    assert "[data-silent-focus]:focus" in base_styles
    assert "outline: none !important;" in base_styles
    assert "mapSelector.focusSelectedMapOption();" in app_script
    assert "showSetupScreen: backToModelSelect" in app_script
    assert "showSetupScreen();" in game_runner_script
    assert "renderTranscript(dom.transcriptOutput, frame, pixelSprite);" in game_runner_script
    assert "transcriptCard(event, pixelSprite)" in game_runner_script
    assert 'event.kind === "turn"' in game_runner_script
    assert "pixelSprite(event.action_emoji" in game_runner_script
    assert 'pixelSprite(item.icon || "?"' in game_runner_script


def test_keyboard_escape_in_model_settings_stays_on_model_screen():
    models_script = SOURCE_STATIC_DIR.joinpath("app", "models.js").read_text(encoding="utf-8")

    assert "event.stopPropagation();" in models_script


def test_main_menu_keyboard_focus_does_not_add_visual_border():
    screens_styles = SOURCE_STATIC_DIR.joinpath("styles", "screens.css").read_text(encoding="utf-8")

    assert ".main-menu-option:focus-visible" in screens_styles
    assert "outline: none;" in screens_styles


def test_editor_typing_uses_quiet_validation_schedule():
    behavior_form_script = SOURCE_STATIC_DIR.joinpath("app", "editor", "behavior-form.js").read_text(encoding="utf-8")
    controller_script = SOURCE_STATIC_DIR.joinpath("app", "editor", "controller.js").read_text(encoding="utf-8")
    entity_form_script = SOURCE_STATIC_DIR.joinpath("app", "editor", "entity-form.js").read_text(encoding="utf-8")
    validation_script = SOURCE_STATIC_DIR.joinpath("app", "editor", "validation.js").read_text(encoding="utf-8")

    assert "function scheduleTyping()" in validation_script
    assert "showPendingImmediately: false" in validation_script
    assert 'dom.editorMapName.addEventListener("input"' in controller_script
    assert "validation.scheduleTyping();" in controller_script
    assert 'input.type === "checkbox" ? validation.schedule : validation.scheduleTyping' in entity_form_script
    assert "function scheduleFieldValidation(input)" in behavior_form_script
    assert "validation.scheduleTyping();" in behavior_form_script


def test_generated_assets_live_outside_package_source():
    assert GENERATED_STATIC_DIR.parts[-3:] == ("build", "web", "static")
    assert "src" not in GENERATED_STATIC_DIR.parts


def test_homepage_renders_without_request_query_parameter():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "WATCH" in response.text
    assert "Play Game" in response.text
    assert "Map Editor" in response.text
    assert "Select Model" in response.text
    assert 'id="model-menu"' in response.text
    assert 'aria-label="Premade and custom maps"' in response.text
    assert 'id="warmup-screen"' in response.text
    assert 'id="saved-map-list"' in response.text
    assert 'id="saved-map-preview"' in response.text
    assert 'id="save-map"' in response.text
    assert 'id="load-map"' in response.text
    assert 'id="save-map-dialog"' in response.text
    assert 'id="load-saved-map"' in response.text
    assert 'id="delete-saved-map"' in response.text
    assert 'id="escape-result-icon"' in response.text
    assert 'id="escape-result-message"' in response.text
    assert 'id="transcript" class="transcript-log" role="log"' in response.text
    assert 'aria-label="Undo"' in response.text
    assert 'aria-label="Redo"' in response.text
    assert "Main Menu" in response.text
    assert "key-door-room" in response.text
    assert next(iter(MODEL_PRESETS)) in response.text


def test_app_data_includes_browser_options():
    assert set(app_data()) == {"models", "maps"}


def test_model_warmup_endpoint_uses_short_non_thinking_completion(monkeypatch):
    seen = {}
    preset_id = next(iter(MODEL_PRESETS))
    session_id = "warmup-short-completion"

    class FakeProvider:
        def complete(self, request):
            seen["request"] = request
            return InferenceResponse(content="OK")

    provider = FakeProvider()
    monkeypatch.setattr(server, "create_provider", lambda _config: provider)
    client = TestClient(create_app())

    response = client.post("/models/warmup", json={"session_id": session_id, "model_preset": preset_id})
    payload = response.json()

    assert response.status_code == 200
    assert payload == {"warmed": True}
    assert seen["request"].messages[0].content == "Reply with OK."
    assert seen["request"].phase == "warmup"
    assert seen["request"].settings.max_tokens == 8
    assert seen["request"].settings.temperature == 0.0
    assert seen["request"].enable_thinking is False
    assert server.warm_provider_store.get(session_id=session_id, model_preset=preset_id) is provider


def test_model_warmup_endpoint_reuses_existing_session_provider(monkeypatch):
    preset_id = next(iter(MODEL_PRESETS))
    session_id = "warmup-existing-provider"
    provider = _RecordingProvider()
    server.warm_provider_store.add(session_id=session_id, model_preset=preset_id, provider=provider)

    monkeypatch.setattr(server, "create_provider", lambda _config: None)
    client = TestClient(create_app())

    response = client.post("/models/warmup", json={"session_id": session_id, "model_preset": preset_id})

    assert response.status_code == 200
    assert response.json() == {"warmed": True}
    assert provider.requests
    assert provider.requests[0].phase == "warmup"
    assert provider.requests[0].enable_thinking is False
    assert provider.requests[0].settings.max_tokens == 8
    assert server.warm_provider_store.get(session_id=session_id, model_preset=preset_id) is provider


def test_escape_stream_uses_session_warmed_provider(monkeypatch):
    seen = {}
    preset_id = next(iter(MODEL_PRESETS))
    session_id = "stream-warmed-provider"
    provider = _NoopProvider()
    server.warm_provider_store.add(session_id=session_id, model_preset=preset_id, provider=provider)

    monkeypatch.setattr(server, "create_provider", lambda _config: None)
    monkeypatch.setattr(server, "run_model_escape_steps", lambda **kwargs: _fake_stream_steps(seen, **kwargs))
    client = TestClient(create_app())

    response = client.get(f"/escape-stream?model_preset={preset_id}&map_id=key-door-room&session_id={session_id}")

    assert response.status_code == 200
    assert seen["provider"] is provider


def test_escape_stream_reuses_session_provider_for_multiple_runs(monkeypatch):
    seen_providers = []
    preset_id = next(iter(MODEL_PRESETS))
    session_id = "stream-reusable-provider"
    warmed_provider = _NoopProvider()
    fallback_provider = _NoopProvider()
    server.warm_provider_store.add(session_id=session_id, model_preset=preset_id, provider=warmed_provider)

    monkeypatch.setattr(server, "create_provider", lambda _config: fallback_provider)
    monkeypatch.setattr(
        server,
        "run_model_escape_steps",
        lambda **kwargs: _fake_stream_steps({"providers": seen_providers}, **kwargs),
    )
    client = TestClient(create_app())

    first = client.get(f"/escape-stream?model_preset={preset_id}&map_id=key-door-room&session_id={session_id}")
    second = client.get(f"/escape-stream?model_preset={preset_id}&map_id=key-door-room&session_id={session_id}")

    assert first.status_code == 200
    assert second.status_code == 200
    assert seen_providers == [warmed_provider, warmed_provider]


def test_escape_stream_ignores_session_provider_for_different_preset(monkeypatch):
    seen = {}
    preset_id, other_preset_id = tuple(MODEL_PRESETS)[:2]
    session_id = "stream-different-preset"
    fallback_provider = _NoopProvider()
    warmed_provider = _NoopProvider()
    server.warm_provider_store.add(session_id=session_id, model_preset=other_preset_id, provider=warmed_provider)

    monkeypatch.setattr(server, "create_provider", lambda _config: fallback_provider)
    monkeypatch.setattr(server, "run_model_escape_steps", lambda **kwargs: _fake_stream_steps(seen, **kwargs))
    client = TestClient(create_app())

    response = client.get(f"/escape-stream?model_preset={preset_id}&map_id=key-door-room&session_id={session_id}")

    assert response.status_code == 200
    assert seen["provider"] is fallback_provider
    assert server.warm_provider_store.get(session_id=session_id, model_preset=other_preset_id) is warmed_provider


def test_warm_provider_store_drops_expired_sessions():
    provider = _NoopProvider()
    store = WarmProviderStore(ttl_seconds=0)
    store.add(session_id="expired-session", model_preset="example", provider=provider)

    assert store.get(session_id="expired-session", model_preset="example") is None


def test_model_preset_options_include_selector_metadata():
    options = model_preset_options()
    tiny_aya = next(option for option in options if option["id"] == "tiny-aya-global")

    assert options
    assert {option["id"] for option in options} == set(MODEL_PRESETS)
    assert all(option["agent_icon"] for option in options)
    assert all(isinstance(option["parameter_size_b"], int | float) for option in options)
    assert all("thinking_supported" in option for option in options)
    assert all("thinking_enabled" in option for option in options)
    assert tiny_aya["thinking_supported"] is False
    assert tiny_aya["thinking_enabled"] is False


def test_premade_map_options_include_preview_metadata():
    options = premade_map_options()
    key_door_room = next(option for option in options if option["id"] == "key-door-room")
    mission_impawsible = next(option for option in options if option["id"] == "mission-impawsible")

    assert key_door_room["name"] == "Key Door Room"
    assert key_door_room["description"]
    assert key_door_room["agent_position"] == "(7, 7)"
    assert len(key_door_room["preview_map"].splitlines()) == 15
    assert len(key_door_room["preview_map_colors"].splitlines()) == 15
    assert all(len(row.split(" ")) == 15 for row in key_door_room["preview_map"].splitlines())
    assert all(len(row.split(" ")) == 15 for row in key_door_room["preview_map_colors"].splitlines())
    assert mission_impawsible["name"] == "Mission: Impawsible"
    assert mission_impawsible["description"] == "someone is hungry."
    assert len(mission_impawsible["preview_map"].splitlines()) == 15


def test_escape_run_response_reports_model_configuration_error(monkeypatch):
    def raise_configuration_error():
        message = "Configure WME_MODEL_PATH before running inference."
        raise LlmConfigurationError(message)

    monkeypatch.setattr(server, "run_model_escape", raise_configuration_error)

    response = build_escape_run_response()

    assert response["status"] == "Model is not configured."
    assert response["sanity"] == "100"
    assert response["visible_entities"] == "- None."
    assert response["inventory"] == "- Empty."
    assert response["visibility"] == ""
    assert "Configure WME_MODEL_PATH" in response["transcript"]


def test_escape_run_response_formats_successful_run(monkeypatch):
    class FakeResult:
        status = "Escaped with 98 sanity remaining."
        sanity = 98
        visible_entities = ("locked-door: A locked door bars the exit.",)
        inventory = ("brass-key",)
        map_view = ((".", "door"), ("key", "."))
        map_color_view = ((".", "#C8793A"), ("#FFD447", "."))
        visibility_view = ((True, False), (False, True))
        transcript = "Turn 1 - sanity 100 -> 99"

    monkeypatch.setattr(server, "run_model_escape", FakeResult)

    response = build_escape_run_response()

    assert response["status"] == "Escaped with 98 sanity remaining."
    assert response["sanity"] == "98"
    assert response["visible_entities"] == "- locked-door: A locked door bars the exit."
    assert response["inventory"] == "- brass-key"
    assert response["map"] == ". door\nkey ."
    assert response["map_colors"] == ". #C8793A\n#FFD447 ."
    assert response["visibility"] == "1 0\n0 1"
    assert response["transcript"] == "Turn 1 - sanity 100 -> 99"


def test_escape_stream_returns_turn_frames(monkeypatch):
    seen = {}
    preset_id = next(iter(MODEL_PRESETS))
    preset = MODEL_PRESETS[preset_id]

    def fake_steps(**kwargs):
        seen.update(kwargs)
        yield EscapeRunFrame(
            escaped=False,
            sanity=99,
            position="(8, 8)",
            visible_entities=("locked-door: A locked door bars the exit.",),
            inventory=("brass-key",),
            visible_entity_details=(
                EntityDisplay(
                    id="locked-door",
                    icon="\U0001f6aa",
                    description="A locked door bars the exit.",
                    color="#C8793A",
                ),
            ),
            inventory_details=(
                EntityDisplay(id="brass-key", icon="\U0001f511", description="A brass key.", color="#FFD447"),
            ),
            map_view=((".", "\U0001f642"), ("\U0001f511", "\U0001f6aa")),
            map_color_view=((".", "."), ("#FFD447", "#C8793A")),
            visibility_view=((True, True), (False, True)),
            transcript="Turn 1 - sanity 100 -> 99",
            status="Still searching with 99 sanity remaining.",
            action_label="open",
            transcript_events=(
                TranscriptIntroEvent(
                    visible_entities=(
                        EntityDisplay(
                            id="locked-door",
                            icon="\U0001f6aa",
                            description="A locked door bars the exit.",
                            color="#C8793A",
                        ),
                    ),
                    message="",
                ),
                TranscriptTurnEvent(
                    turn_number=1,
                    sanity_before=100,
                    sanity_after=99,
                    deliberation="I should try the door.",
                    action_type="open",
                    action_emoji="\U0001f6aa",
                    action_text="Open locked-door",
                    result="The door is locked.",
                    effects=(
                        ActionEffectSummary(
                            kind="set_entity_state",
                            entity_id="locked-door",
                            text="locked-door state changed to unlocked.",
                        ),
                    ),
                ),
            ),
        )

    provider = object()
    monkeypatch.setattr(server, "create_provider", lambda _config: provider)
    monkeypatch.setattr(server, "run_model_escape_steps", fake_steps)
    client = TestClient(create_app())

    response = client.get(f"/escape-stream?model_preset={preset_id}&map_id=key-door-room&startup_delay_ms=2000")

    assert response.status_code == 200
    assert seen["provider"] is provider
    assert seen["game_map"].id == "key-door-room"
    assert seen["startup_delay_ms"] == 2000
    assert seen["settings"].deliberation.temperature == preset.thinking_temperature
    assert seen["settings"].deliberation.top_p == preset.thinking_top_p
    assert seen["settings"].deliberation.top_k == preset.thinking_top_k
    assert seen["settings"].deliberation_enable_thinking is True
    assert seen["settings"].action.temperature == 0.0
    assert "objective" not in seen
    assert "Still searching with 99 sanity remaining." in response.text
    assert "(8, 8)" in response.text
    assert '"action_label": "open"' in response.text
    assert '"visibility": "1 1\\n0 1"' in response.text
    assert '"map_colors": ". .\\n#FFD447 #C8793A"' in response.text
    assert '"visible_entity_details": [{"id": "locked-door"' in response.text
    assert '"color": "#C8793A"' in response.text
    assert '"inventory_details": [{"id": "brass-key"' in response.text
    assert '"transcript_events": [{"kind": "intro"' in response.text
    assert '"kind": "turn"' in response.text
    assert '"action_type": "open"' in response.text
    assert '"action_text": "Open locked-door"' in response.text
    assert '"effects": [{"kind": "set_entity_state"' in response.text
    assert '"text": "locked-door state changed to unlocked."' in response.text
    assert "locked-door" in response.text
    assert "Turn 1 - sanity 100 -> 99" in response.text


def test_escape_stream_applies_deliberation_query_overrides(monkeypatch):
    seen = {}
    preset_id = "gemma-4-12b-it"

    monkeypatch.setattr(server, "create_provider", lambda _config: object())
    monkeypatch.setattr(server, "run_model_escape_steps", lambda **kwargs: _fake_stream_steps(seen, **kwargs))
    client = TestClient(create_app())

    response = client.get(
        "/escape-stream",
        params={
            "model_preset": preset_id,
            "map_id": "key-door-room",
            "deliberation_enable_thinking": "false",
            "deliberation_temperature": "0.35",
        },
    )

    assert response.status_code == 200
    assert seen["settings"].deliberation_enable_thinking is False
    assert seen["settings"].deliberation.temperature == 0.35
    assert seen["settings"].action.temperature == 0.0


def test_escape_stream_rejects_deliberation_temperature_above_slider_range():
    client = TestClient(create_app())

    response = client.get(
        "/escape-stream",
        params={
            "model_preset": "gemma-4-12b-it",
            "map_id": "key-door-room",
            "deliberation_temperature": "1.5",
        },
    )

    assert response.status_code == 422


def test_escape_stream_keeps_thinking_disabled_for_unsupported_model(monkeypatch):
    seen = {}

    monkeypatch.setattr(server, "create_provider", lambda _config: object())
    monkeypatch.setattr(server, "run_model_escape_steps", lambda **kwargs: _fake_stream_steps(seen, **kwargs))
    client = TestClient(create_app())

    response = client.get(
        "/escape-stream",
        params={
            "model_preset": "tiny-aya-global",
            "map_id": "key-door-room",
            "deliberation_enable_thinking": "true",
        },
    )

    assert response.status_code == 200
    assert seen["settings"].deliberation_enable_thinking is False
    assert seen["settings"].deliberation.temperature == MODEL_PRESETS["tiny-aya-global"].thinking_temperature


def test_escape_stream_rejects_unknown_model_preset():
    client = TestClient(create_app())

    response = client.get("/escape-stream?model_preset=missing&map_id=key-door-room")

    assert response.status_code == 400
    assert "Unknown model preset" in response.text


def test_escape_stream_rejects_unknown_map(monkeypatch):
    monkeypatch.setattr(server, "create_provider", lambda _config: object())
    client = TestClient(create_app())

    response = client.get(f"/escape-stream?model_preset={next(iter(MODEL_PRESETS))}&map_id=missing")

    assert response.status_code == 400
    assert "Unknown map" in response.text


def test_custom_map_run_token_accepts_export_document():
    client = TestClient(create_app())

    response = client.post("/maps/custom-run-token", json=_custom_map_document())

    assert response.status_code == 200
    assert response.json()["token"]


def test_escape_stream_returns_custom_map_turn_frames(monkeypatch):
    seen = {}
    preset_id = next(iter(MODEL_PRESETS))

    def fake_steps(**kwargs):
        seen.update(kwargs)
        yield EscapeRunFrame(
            escaped=False,
            sanity=99,
            position="(1, 1)",
            visible_entities=("custom-exit: A custom way out.",),
            inventory=(),
            visible_entity_details=(),
            inventory_details=(),
            map_view=((".", "\U0001f642"), (".", "\U0001f3c1")),
            map_color_view=((".", "."), (".", "#71F7B1")),
            visibility_view=((True, True), (True, True)),
            transcript="Turn 1 - custom map",
            status="Still searching with 99 sanity remaining.",
            action_label="examine",
        )

    provider = object()
    monkeypatch.setattr(server, "create_provider", lambda _config: provider)
    monkeypatch.setattr(server, "run_model_escape_steps", fake_steps)
    client = TestClient(create_app())
    token_response = client.post("/maps/custom-run-token", json=_custom_map_document())
    token = token_response.json()["token"]

    response = client.get(f"/escape-stream?model_preset={preset_id}&custom_map_token={token}")

    assert response.status_code == 200
    assert seen["provider"] is provider
    assert seen["game_map"].id == "custom-room"
    assert "Turn 1 - custom map" in response.text


def test_escape_stream_rejects_unknown_custom_map_token():
    client = TestClient(create_app())

    response = client.get(f"/escape-stream?model_preset={next(iter(MODEL_PRESETS))}&custom_map_token=missing")

    assert response.status_code == 400
    assert "Unknown or expired custom map token" in response.text


def test_escape_stream_rejects_missing_map_source():
    client = TestClient(create_app())

    response = client.get(f"/escape-stream?model_preset={next(iter(MODEL_PRESETS))}")

    assert response.status_code == 400
    assert "Choose exactly one map source" in response.text


def test_escape_stream_rejects_ambiguous_map_source():
    client = TestClient(create_app())

    response = client.get(
        f"/escape-stream?model_preset={next(iter(MODEL_PRESETS))}&map_id=key-door-room&custom_map_token=extra"
    )

    assert response.status_code == 400
    assert "Choose exactly one map source" in response.text


def test_map_validation_accepts_export_document():
    client = TestClient(create_app())

    response = client.post(
        "/maps/validate",
        json={
            "description": "A small room.",
            "map": {
                "id": "small-room",
                "name": "Small Room",
                "agent_start": {"x": 1, "y": 1},
                "entities": [
                    {
                        "position": {"x": 2, "y": 1},
                        "entity": {
                            "id": "exit",
                            "icon": "\U0001f3c1",
                            "description": "The way out.",
                            "passable": True,
                            "behaviors": [{"trigger": {"action": "operate"}, "effects": [{"type": "escape_map"}]}],
                        },
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["map"]["id"] == "small-room"


def test_map_validation_rejects_objective_field():
    client = TestClient(create_app())

    response = client.post(
        "/maps/validate",
        json={
            "description": "A small room.",
            "objective": "Escape with coaching.",
            "map": {"id": "small-room", "name": "Small Room", "agent_start": {"x": 1, "y": 1}, "entities": []},
        },
    )

    assert response.status_code == 422
    assert "objective" in response.text


def _fake_stream_steps(seen, **kwargs):
    if "providers" in seen:
        seen["providers"].append(kwargs["provider"])
    else:
        seen.update(kwargs)
    yield EscapeRunFrame(
        escaped=False,
        sanity=99,
        position="(8, 8)",
        visible_entities=(),
        inventory=(),
        visible_entity_details=(),
        inventory_details=(),
        map_view=((".",),),
        map_color_view=((".",),),
        visibility_view=((True,),),
        transcript="Turn 1",
        status="Still searching with 99 sanity remaining.",
        action_label="wait",
    )


class _NoopProvider:
    def complete(self, request):
        del request
        return InferenceResponse(content="OK")


class _RecordingProvider:
    def __init__(self):
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return InferenceResponse(content="OK")


def _custom_map_document():
    return {
        "description": "A custom room.",
        "map": {
            "id": "custom-room",
            "name": "Custom Room",
            "agent_start": {"x": 1, "y": 1},
            "entities": [
                {
                    "position": {"x": 2, "y": 1},
                    "entity": {
                        "id": "custom-exit",
                        "icon": "\U0001f3c1",
                        "color": "#71F7B1",
                        "description": "A custom way out.",
                        "passable": True,
                        "behaviors": [{"trigger": {"action": "operate"}, "effects": [{"type": "escape_map"}]}],
                    },
                }
            ],
        },
    }
