"""Gradio Server backend for Watch My Escape."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from fastapi import Request  # noqa: TC002 - FastAPI needs this runtime annotation to inject the request.
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from gradio import Server

from watch_my_escape.game.engine import describe_escape_attempt

if TYPE_CHECKING:
    from fastapi.responses import Response

PACKAGE_DIR: Final = Path(__file__).resolve().parents[1]
PROJECT_DIR: Final = PACKAGE_DIR.parents[1]
WEB_DIR: Final = PACKAGE_DIR / "web"
SOURCE_STATIC_DIR: Final = WEB_DIR / "static"
GENERATED_STATIC_DIR: Final = PROJECT_DIR / "build" / "web" / "static"
TEMPLATES_DIR: Final = WEB_DIR / "templates"
templates: Final = Jinja2Templates(directory=TEMPLATES_DIR)


def create_app() -> Server:
    """Create the Gradio server application."""
    app = Server()
    app.mount("/static", StaticFiles(directory=GENERATED_STATIC_DIR), name="static")

    @app.get("/")
    async def homepage(request: Request) -> Response:
        return templates.TemplateResponse(
            request=request,
            name="index.html.jinja",
            context={
                "app_name": "Watch My Escape",
                "project_description": "An LLM tries to escape a man-made puzzle room.",
            },
        )

    @app.api(name="attempt_escape")
    def attempt_escape(action: str) -> str:
        return describe_escape_attempt(action)

    return app


def main() -> None:
    """Launch the development server."""
    create_app().launch(show_error=True)
