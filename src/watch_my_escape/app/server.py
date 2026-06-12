"""Gradio Server backend for Watch My Escape."""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, Final, cast

from fastapi import HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from gradio import Server
from pydantic import BaseModel, ValidationError

from watch_my_escape.agent.escape_run import EntityDisplay, EscapeRunFrame, run_model_escape, run_model_escape_steps
from watch_my_escape.agent.runner import ThinkActSettings, think_act_settings_for_config
from watch_my_escape.game.maps import GameSessionState, render_user_map_color_view, render_user_map_view
from watch_my_escape.game.premade_maps import (
    PremadeMapDocument,
    PremadeMapError,
    get_premade_map,
    list_premade_maps,
)
from watch_my_escape.llm.client import LlmConfigurationError, create_provider
from watch_my_escape.llm.config import MODEL_PRESETS, ModelPresetError, config_for_model_preset
from watch_my_escape.llm.models import ChatMessage, InferenceRequest, InferenceSettings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.responses import Response

    from watch_my_escape.game.maps import GameMap
    from watch_my_escape.game.premade_maps import PremadeMap
    from watch_my_escape.llm.client import InferenceProvider
    from watch_my_escape.llm.config import LlamaCppConfig

PACKAGE_DIR: Final = Path(__file__).resolve().parents[1]
PROJECT_DIR: Final = PACKAGE_DIR.parents[1]
WEB_DIR: Final = PACKAGE_DIR / "web"
SOURCE_STATIC_DIR: Final = WEB_DIR / "static"
GENERATED_STATIC_DIR: Final = PROJECT_DIR / "build" / "web" / "static"
TEMPLATES_DIR: Final = WEB_DIR / "templates"
templates: Final = Jinja2Templates(directory=TEMPLATES_DIR)
CUSTOM_MAP_TOKEN_TTL_SECONDS: Final = 15 * 60
WARM_PROVIDER_TOKEN_TTL_SECONDS: Final = 5 * 60


@dataclass(frozen=True, slots=True)
class CustomMapRun:
    """A validated custom map available to a pending stream."""

    game_map: GameMap
    expires_at: float


@dataclass(frozen=True, slots=True)
class WarmProviderRun:
    """A warmed model provider available to the next matching game stream."""

    model_preset: str
    provider: InferenceProvider
    expires_at: float


class CustomMapTokenError(ValueError):
    """Raised when a custom map run token cannot be used."""


class ModelWarmupRequest(BaseModel):
    """Request to prepare a model before the game screen appears."""

    model_preset: str


class WarmProviderStore:
    """Short-lived in-memory storage for warmed model providers."""

    def __init__(self, *, ttl_seconds: int = WARM_PROVIDER_TOKEN_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._runs: dict[str, WarmProviderRun] = {}
        self._lock = Lock()

    def add(self, *, model_preset: str, provider: InferenceProvider) -> str:
        """Store a warmed provider and return its opaque warmup token."""
        self._prune_expired()
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._runs[token] = WarmProviderRun(
                model_preset=model_preset,
                provider=provider,
                expires_at=time.monotonic() + self._ttl_seconds,
            )
        return token

    def claim(self, *, token: str, model_preset: str) -> InferenceProvider | None:
        """Return and remove a warmed provider if it is fresh and matches the preset."""
        self._prune_expired()
        with self._lock:
            run = self._runs.pop(token, None)
        if run is None or run.expires_at <= time.monotonic() or run.model_preset != model_preset:
            return None
        return run.provider

    def _prune_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired_tokens = [token for token, run in self._runs.items() if run.expires_at <= now]
            for token in expired_tokens:
                del self._runs[token]


class CustomMapRunStore:
    """Short-lived in-memory storage for validated custom map runs."""

    def __init__(self, *, ttl_seconds: int = CUSTOM_MAP_TOKEN_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._runs: dict[str, CustomMapRun] = {}
        self._lock = Lock()

    def add(self, game_map: GameMap) -> str:
        """Store a custom map and return its opaque run token."""
        self._prune_expired()
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._runs[token] = CustomMapRun(game_map=game_map, expires_at=time.monotonic() + self._ttl_seconds)
        return token

    def get(self, token: str) -> GameMap:
        """Return the map for a token if it is known and still fresh."""
        self._prune_expired()
        with self._lock:
            run = self._runs.get(token)
        if run is None:
            msg = "Unknown or expired custom map token."
            raise CustomMapTokenError(msg)
        if run.expires_at <= time.monotonic():
            self._prune_expired()
            msg = "Unknown or expired custom map token."
            raise CustomMapTokenError(msg)
        return run.game_map

    def _prune_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired_tokens = [token for token, run in self._runs.items() if run.expires_at <= now]
            for token in expired_tokens:
                del self._runs[token]


custom_map_run_store: Final = CustomMapRunStore()
warm_provider_store: Final = WarmProviderStore()


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
                "app_data": app_data(),
            },
        )

    @app.api(name="run_model_escape")
    def run_escape_game() -> dict[str, Any]:
        return build_escape_run_response()

    @app.get("/escape-stream")
    def escape_stream(
        model_preset: str = Query(min_length=1),
        map_id: str | None = Query(default=None, min_length=1),
        custom_map_token: str | None = Query(default=None, min_length=1),
        warmup_token: str | None = Query(default=None, min_length=1),
        startup_delay_ms: int = Query(default=0, ge=0, le=10_000),
    ) -> StreamingResponse:
        try:
            config = config_for_model_preset(model_preset)
            game_map = _selected_stream_map(map_id=map_id, custom_map_token=custom_map_token)
            provider = _stream_provider(config=config, model_preset=model_preset, warmup_token=warmup_token)
            settings = think_act_settings_for_config(config)
        except (ModelPresetError, PremadeMapError, CustomMapTokenError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return StreamingResponse(
            _escape_event_stream(
                provider=provider,
                game_map=game_map,
                startup_delay_ms=startup_delay_ms,
                settings=settings,
            ),
            media_type="text/event-stream",
        )

    @app.post("/maps/custom-run-token")
    async def create_custom_map_run_token(payload: dict[str, object]) -> dict[str, str]:
        try:
            document = PremadeMapDocument.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        return {"token": custom_map_run_store.add(document.map)}

    @app.post("/maps/validate")
    async def validate_map_document(payload: dict[str, object]) -> dict[str, object]:
        try:
            document = PremadeMapDocument.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        return document.model_dump(mode="json")

    @app.post("/models/warmup")
    def warmup_model(request: ModelWarmupRequest) -> dict[str, object]:
        return warm_model_preset(request.model_preset)

    return app


def main() -> None:
    """Launch the development server."""
    create_app().launch(show_error=True)


def build_escape_run_response() -> dict[str, Any]:
    """Return the API payload for one model escape run."""
    try:
        result = run_model_escape()
    except LlmConfigurationError as exc:
        return {
            "status": "Model is not configured.",
            "sanity": "100",
            "visible_entities": "- None.",
            "inventory": "- Empty.",
            "visible_entity_details": (),
            "inventory_details": (),
            "map": "",
            "map_colors": "",
            "visibility": "",
            "transcript": str(exc),
        }

    return {
        "status": result.status,
        "sanity": str(result.sanity),
        "visible_entities": _format_list(result.visible_entities, empty="- None."),
        "inventory": _format_list(result.inventory, empty="- Empty."),
        "visible_entity_details": _entity_details_payload(getattr(result, "visible_entity_details", ())),
        "inventory_details": _entity_details_payload(getattr(result, "inventory_details", ())),
        "map": _format_map(result.map_view),
        "map_colors": _format_map(getattr(result, "map_color_view", ())),
        "visibility": _format_visibility(result.visibility_view),
        "transcript": result.transcript or "No turns were run.",
    }


def app_data() -> dict[str, object]:
    """Return JSON-safe application data for the browser."""
    return {
        "models": model_preset_options(),
        "maps": premade_map_options(),
    }


def warm_model_preset(model_preset: str) -> dict[str, object]:
    """Run a tiny completion to prepare a model for the first game turn."""
    try:
        provider = create_provider(config_for_model_preset(model_preset))
        provider.complete(
            InferenceRequest(
                messages=(ChatMessage(role="user", content="Reply with OK."),),
                settings=InferenceSettings(max_tokens=8, temperature=0.0),
                enable_thinking=False,
            )
        )
    except ModelPresetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LlmConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"warmed": True, "warmup_token": warm_provider_store.add(model_preset=model_preset, provider=provider)}


def _stream_provider(*, config: LlamaCppConfig, model_preset: str, warmup_token: str | None) -> InferenceProvider:
    if warmup_token is not None:
        provider = warm_provider_store.claim(token=warmup_token, model_preset=model_preset)
        if provider is not None:
            return provider
    return create_provider(config)


def model_preset_options() -> tuple[dict[str, object], ...]:
    """Return JSON-safe preset selector metadata."""
    return tuple(
        {
            "id": preset_id,
            "display_name": preset.display_name,
            "company": preset.company,
            "brand_color": preset.brand_color,
            "agent_icon": preset.agent_icon,
            "parameter_size_b": preset.parameter_size_b,
            "active_parameter_size_b": preset.active_parameter_size_b,
            "repo_id": preset.repo_id,
            "filename": preset.filename,
            "thinking_temperature": preset.thinking_temperature,
            "thinking_top_p": preset.thinking_top_p,
            "thinking_top_k": preset.thinking_top_k,
        }
        for preset_id, preset in MODEL_PRESETS.items()
    )


def premade_map_options() -> tuple[dict[str, str], ...]:
    """Return JSON-safe map selector metadata."""
    return tuple(_premade_map_option(premade_map) for premade_map in list_premade_maps())


def _premade_map_option(premade_map: PremadeMap) -> dict[str, str]:
    session = GameSessionState(map=premade_map.map)
    position = session.current_position
    return {
        **premade_map.as_selection_option(),
        "preview_map": _format_map(render_user_map_view(session)),
        "preview_map_colors": _format_map(render_user_map_color_view(session)),
        "agent_position": f"({position.x}, {position.y})",
    }


def _selected_stream_map(*, map_id: str | None, custom_map_token: str | None) -> GameMap:
    if (map_id is None) == (custom_map_token is None):
        msg = "Choose exactly one map source."
        raise CustomMapTokenError(msg)
    if map_id is not None:
        return get_premade_map(map_id).map
    if custom_map_token is None:
        msg = "Choose exactly one map source."
        raise CustomMapTokenError(msg)
    return custom_map_run_store.get(custom_map_token)


def _format_list(values: tuple[str, ...], *, empty: str) -> str:
    if not values:
        return empty
    return "\n".join(f"- {value}" for value in values)


def _format_map(map_view: tuple[tuple[str, ...], ...]) -> str:
    return "\n".join(" ".join(row) for row in map_view)


def _format_visibility(visibility_view: tuple[tuple[bool, ...], ...]) -> str:
    return "\n".join(" ".join("1" if cell else "0" for cell in row) for row in visibility_view)


def _escape_event_stream(
    *,
    provider: InferenceProvider | None = None,
    game_map: GameMap | None = None,
    startup_delay_ms: int = 0,
    settings: ThinkActSettings | None = None,
) -> Iterator[str]:
    try:
        for frame in run_model_escape_steps(
            provider=provider,
            game_map=game_map,
            startup_delay_ms=startup_delay_ms,
            settings=settings,
        ):
            yield f"data: {json.dumps(_frame_payload(frame))}\n\n"
            if frame.delay_ms:
                time.sleep(frame.delay_ms / 1000)
    except LlmConfigurationError as exc:
        payload = {
            "status": "Model is not configured.",
            "sanity": "100",
            "position": "",
            "action_label": "",
            "visible_entities": "- None.",
            "inventory": "- Empty.",
            "visible_entity_details": (),
            "inventory_details": (),
            "map": "",
            "map_colors": "",
            "visibility": "",
            "transcript": str(exc),
            "escaped": False,
        }
        yield f"data: {json.dumps(payload)}\n\n"


def _frame_payload(frame: EscapeRunFrame) -> dict[str, object]:
    return {
        "status": frame.status,
        "sanity": str(frame.sanity),
        "position": frame.position,
        "action_label": frame.action_label,
        "visible_entities": _format_list(frame.visible_entities, empty="- None."),
        "inventory": _format_list(frame.inventory, empty="- Empty."),
        "visible_entity_details": _entity_details_payload(frame.visible_entity_details),
        "inventory_details": _entity_details_payload(frame.inventory_details),
        "map": _format_map(frame.map_view),
        "map_colors": _format_map(frame.map_color_view),
        "visibility": _format_visibility(frame.visibility_view),
        "transcript": frame.transcript or "Waiting for the first turn.",
        "escaped": frame.escaped,
    }


def _entity_details_payload(details: object) -> tuple[dict[str, str], ...]:
    if not isinstance(details, tuple):
        return ()
    return tuple(_entity_detail_payload(detail) for detail in details)


def _entity_detail_payload(detail: object) -> dict[str, str]:
    if isinstance(detail, EntityDisplay):
        return {"id": detail.id, "icon": detail.icon, "description": detail.description, "color": detail.color or ""}
    if isinstance(detail, dict):
        values = cast("dict[object, object]", detail)
        return {
            "id": str(values.get("id", "")),
            "icon": str(values.get("icon", "")),
            "description": str(values.get("description", "")),
            "color": str(values.get("color", "")),
        }
    return {"id": str(detail), "icon": "", "description": "", "color": ""}
