from fastapi.testclient import TestClient
from gradio import Server

from watch_my_escape.agent.escape_demo import EscapeDemoFrame
from watch_my_escape.app import server
from watch_my_escape.app.server import (
    GENERATED_STATIC_DIR,
    SOURCE_STATIC_DIR,
    TEMPLATES_DIR,
    build_escape_demo_response,
    create_app,
)
from watch_my_escape.llm.client import LlmConfigurationError


def test_create_app_returns_gradio_server():
    app = create_app()

    assert isinstance(app, Server)


def test_web_assets_live_inside_package():
    assert TEMPLATES_DIR.joinpath("index.html.jinja").is_file()
    assert SOURCE_STATIC_DIR.joinpath("input.css").is_file()
    assert SOURCE_STATIC_DIR.joinpath("app.js").is_file()


def test_generated_assets_live_outside_package_source():
    assert GENERATED_STATIC_DIR.parts[-3:] == ("build", "web", "static")
    assert "src" not in GENERATED_STATIC_DIR.parts


def test_homepage_renders_without_request_query_parameter():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Watch My Escape" in response.text
    assert "Run model escape" in response.text


def test_escape_demo_response_reports_model_configuration_error(monkeypatch):
    def raise_configuration_error():
        message = "Configure WME_MODEL_PATH before running inference."
        raise LlmConfigurationError(message)

    monkeypatch.setattr(server, "run_model_escape", raise_configuration_error)

    response = build_escape_demo_response()

    assert response["status"] == "Model is not configured."
    assert response["sanity"] == "100"
    assert response["visible_entities"] == "- None."
    assert response["inventory"] == "- Empty."
    assert response["journal"] == "- No notes recorded."
    assert "Configure WME_MODEL_PATH" in response["transcript"]


def test_escape_demo_response_formats_successful_run(monkeypatch):
    class FakeResult:
        status = "Escaped with 98 sanity remaining."
        sanity = 98
        visible_entities = ("(15, 8) locked-door: Locked door. A locked door bars the exit.",)
        inventory = ("brass key",)
        journal = ("The key should open the door.",)
        map_view = ((".", "door"), ("key", "."))
        transcript = "Turn 1 - sanity 100 -> 99"

    monkeypatch.setattr(server, "run_model_escape", FakeResult)

    response = build_escape_demo_response()

    assert response["status"] == "Escaped with 98 sanity remaining."
    assert response["sanity"] == "98"
    assert response["visible_entities"] == "- (15, 8) locked-door: Locked door. A locked door bars the exit."
    assert response["inventory"] == "- brass key"
    assert response["journal"] == "- The key should open the door."
    assert response["map"] == ". door\nkey ."
    assert response["transcript"] == "Turn 1 - sanity 100 -> 99"


def test_escape_stream_returns_turn_frames(monkeypatch):
    def fake_steps():
        yield EscapeDemoFrame(
            escaped=False,
            sanity=99,
            position="(8, 8)",
            visible_entities=("(15, 8) locked-door: Locked door. A locked door bars the exit.",),
            inventory=("brass key",),
            journal=("The key opens the door.",),
            map_view=((".", "\U0001f642"), ("\U0001f511", "\U0001f6aa")),
            transcript="Turn 1 - sanity 100 -> 99",
            status="Still searching with 99 sanity remaining.",
        )

    monkeypatch.setattr(server, "run_model_escape_steps", fake_steps)
    client = TestClient(create_app())

    response = client.get("/escape-stream")

    assert response.status_code == 200
    assert "Still searching with 99 sanity remaining." in response.text
    assert "(8, 8)" in response.text
    assert "locked-door" in response.text
    assert "Turn 1 - sanity 100 -> 99" in response.text
