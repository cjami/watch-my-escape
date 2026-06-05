from fastapi.testclient import TestClient
from gradio import Server

from watch_my_escape.app.server import GENERATED_STATIC_DIR, SOURCE_STATIC_DIR, TEMPLATES_DIR, create_app


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
