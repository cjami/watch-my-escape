"""Gradio Server backend for Watch My Escape."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Final

from fastapi import Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from gradio import Server

from watch_my_escape.agent.escape_demo import EscapeDemoFrame, run_model_escape, run_model_escape_steps
from watch_my_escape.llm.client import LlmConfigurationError

if TYPE_CHECKING:
    from collections.abc import Iterator

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

    @app.api(name="run_model_escape")
    def run_escape_demo() -> dict[str, str]:
        return build_escape_demo_response()

    @app.get("/escape-stream")
    def escape_stream() -> StreamingResponse:
        return StreamingResponse(_escape_event_stream(), media_type="text/event-stream")

    return app


def main() -> None:
    """Launch the development server."""
    create_app().launch(show_error=True)


def build_escape_demo_response() -> dict[str, str]:
    """Return the API payload for one model escape demo run."""
    try:
        result = run_model_escape()
    except LlmConfigurationError as exc:
        return {
            "status": "Model is not configured.",
            "sanity": "100",
            "visible_entities": "- None.",
            "inventory": "- Empty.",
            "journal": "- No notes recorded.",
            "map": "",
            "transcript": str(exc),
        }

    return {
        "status": result.status,
        "sanity": str(result.sanity),
        "visible_entities": _format_list(result.visible_entities, empty="- None."),
        "inventory": _format_list(result.inventory, empty="- Empty."),
        "journal": _format_list(result.journal, empty="- No notes recorded."),
        "map": _format_map(result.map_view),
        "transcript": result.transcript or "No turns were run.",
    }


def _format_list(values: tuple[str, ...], *, empty: str) -> str:
    if not values:
        return empty
    return "\n".join(f"- {value}" for value in values)


def _format_map(map_view: tuple[tuple[str, ...], ...]) -> str:
    return "\n".join(" ".join(row) for row in map_view)


def _escape_event_stream() -> Iterator[str]:
    try:
        for frame in run_model_escape_steps():
            yield f"data: {json.dumps(_frame_payload(frame))}\n\n"
            if frame.delay_ms:
                time.sleep(frame.delay_ms / 1000)
    except LlmConfigurationError as exc:
        payload = {
            "status": "Model is not configured.",
            "sanity": "100",
            "position": "",
            "visible_entities": "- None.",
            "inventory": "- Empty.",
            "journal": "- No notes recorded.",
            "map": "",
            "transcript": str(exc),
            "escaped": False,
        }
        yield f"data: {json.dumps(payload)}\n\n"


def _frame_payload(frame: EscapeDemoFrame) -> dict[str, str | bool]:
    return {
        "status": frame.status,
        "sanity": str(frame.sanity),
        "position": frame.position,
        "visible_entities": _format_list(frame.visible_entities, empty="- None."),
        "inventory": _format_list(frame.inventory, empty="- Empty."),
        "journal": _format_list(frame.journal, empty="- No notes recorded."),
        "map": _format_map(frame.map_view),
        "transcript": frame.transcript or "Waiting for the first turn.",
        "escaped": frame.escaped,
    }
