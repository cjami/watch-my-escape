"""Gradio Server backend for Watch My Escape."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from fastapi import Request  # noqa: TC002 - FastAPI needs this runtime annotation to inject the request.
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from gradio import Server

from watch_my_escape.escape_room import describe_escape_attempt

if TYPE_CHECKING:
    from fastapi.responses import Response

WEB_DIR: Final = Path(__file__).resolve().parent / "web"
STATIC_DIR: Final = WEB_DIR / "static"
TEMPLATES_DIR: Final = WEB_DIR / "templates"
templates: Final = Jinja2Templates(directory=TEMPLATES_DIR)


def create_app() -> Server:
    """Create the Gradio server application."""
    app = Server()
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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
