"""Gradio Server backend for WATCH MY ESCAPE."""

from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Annotated, Any, Final, cast

from fastapi import HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from gradio import Server
from pydantic import BaseModel, Field, ValidationError

from watch_my_escape.agent.escape_run import (
    EntityDisplay,
    EscapeRunFrame,
    TranscriptIntroEvent,
    TranscriptTurnEvent,
    run_model_escape,
    run_model_escape_steps,
)
from watch_my_escape.agent.runner import ThinkActSettings, think_act_settings_for_config
from watch_my_escape.game.maps import GameSessionState, render_user_map_color_view, render_user_map_view
from watch_my_escape.game.premade_maps import (
    PremadeMapDocument,
    PremadeMapError,
    get_premade_map,
    list_premade_maps,
)
from watch_my_escape.game.runtime import ActionEffectSummary
from watch_my_escape.llm.client import LlmConfigurationError, create_provider
from watch_my_escape.llm.config import MODEL_PRESETS, ModelPreset, ModelPresetError, config_for_model_preset
from watch_my_escape.llm.models import ChatMessage, InferenceRequest, InferenceSettings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from fastapi.responses import Response

    from watch_my_escape.game.maps import GameMap
    from watch_my_escape.game.premade_maps import PremadeMap
    from watch_my_escape.llm.client import InferenceProvider
    from watch_my_escape.llm.config import LlamaCppConfig
    from watch_my_escape.llm.models import InferenceResponse

PACKAGE_DIR: Final = Path(__file__).resolve().parents[1]
PROJECT_DIR: Final = PACKAGE_DIR.parents[1]
WEB_DIR: Final = PACKAGE_DIR / "web"
SOURCE_STATIC_DIR: Final = WEB_DIR / "static"
GENERATED_STATIC_DIR: Final = PROJECT_DIR / "build" / "web" / "static"
TEMPLATES_DIR: Final = WEB_DIR / "templates"
templates: Final = Jinja2Templates(directory=TEMPLATES_DIR)
CUSTOM_MAP_TOKEN_TTL_SECONDS: Final = 15 * 60
WARM_PROVIDER_SESSION_TTL_SECONDS: Final = 5 * 60
ESCAPE_RUN_TTL_SECONDS: Final = 30 * 60
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CustomMapRun:
    """A validated custom map available to a pending stream."""

    game_map: GameMap
    expires_at: float


@dataclass(frozen=True, slots=True)
class WarmProviderRun:
    """A warmed model provider available to one browser session."""

    session_id: str
    model_preset: str
    provider: InferenceProvider
    expires_at: float


@dataclass(frozen=True, slots=True)
class EscapeRunRecord:
    """A cancellable escape run for one browser session."""

    session_id: str
    run_id: str
    cancelled: bool
    expires_at: float


@dataclass(frozen=True, slots=True)
class EscapeStreamLifecycle:
    """Cancellation hooks for a streaming run."""

    is_cancelled: Callable[[], bool]
    on_complete: Callable[[], None]


DEFAULT_STREAM_LIFECYCLE: Final = EscapeStreamLifecycle(is_cancelled=lambda: False, on_complete=lambda: None)


class CustomMapTokenError(ValueError):
    """Raised when a custom map run token cannot be used."""


class EscapeRunCancelledError(RuntimeError):
    """Raised when a cancelled run tries to continue inference."""


class ModelWarmupRequest(BaseModel):
    """Request to prepare a model before the game screen appears."""

    session_id: str = Field(min_length=1)
    model_preset: str = Field(min_length=1)


class EscapeStreamRequest(BaseModel):
    """Query parameters for a streaming escape run."""

    model_preset: str = Field(min_length=1)
    map_id: str | None = Field(default=None, min_length=1)
    custom_map_token: str | None = Field(default=None, min_length=1)
    session_id: str | None = Field(default=None, min_length=1)
    run_id: str | None = Field(default=None, min_length=1)
    startup_delay_ms: int = Field(default=0, ge=0, le=10_000)
    deliberation_enable_thinking: bool | None = None
    deliberation_temperature: float | None = Field(default=None, ge=0.0, le=1.0)


class CancelEscapeRunRequest(BaseModel):
    """Request to cancel one browser session's active run."""

    session_id: str = Field(min_length=1)
    run_id: str | None = Field(default=None, min_length=1)


class SynchronizedInferenceProvider:
    """Serialize calls into a single provider instance."""

    def __init__(self, provider: InferenceProvider) -> None:
        self.inner = provider
        self._lock = Lock()

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Run one completion without re-entering the wrapped provider."""
        with self._lock:
            return self.inner.complete(request)


def synchronized_provider(provider: InferenceProvider) -> InferenceProvider:
    """Return a provider guarded against instance-level re-entry."""
    if isinstance(provider, SynchronizedInferenceProvider):
        return provider
    return SynchronizedInferenceProvider(provider)


class CancellableInferenceProvider:
    """Stop a stream before entering inference after cancellation."""

    def __init__(self, provider: InferenceProvider, is_cancelled: Callable[[], bool]) -> None:
        self.inner = provider
        self._is_cancelled = is_cancelled

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Run one completion unless the owning stream has been cancelled."""
        if self._is_cancelled():
            raise EscapeRunCancelledError
        response = self.inner.complete(request)
        if self._is_cancelled():
            raise EscapeRunCancelledError
        return response


class WarmProviderStore:
    """Short-lived in-memory storage for warmed model providers."""

    def __init__(self, *, ttl_seconds: int = WARM_PROVIDER_SESSION_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._runs: dict[tuple[str, str], WarmProviderRun] = {}
        self._lock = Lock()

    def add(self, *, session_id: str, model_preset: str, provider: InferenceProvider) -> None:
        """Store a warmed provider for one browser session and preset."""
        self._prune_expired()
        with self._lock:
            self._runs[(session_id, model_preset)] = WarmProviderRun(
                session_id=session_id,
                model_preset=model_preset,
                provider=synchronized_provider(provider),
                expires_at=time.monotonic() + self._ttl_seconds,
            )

    def get(self, *, session_id: str, model_preset: str) -> InferenceProvider | None:
        """Return a warmed provider if it is fresh and belongs to the session."""
        self._prune_expired()
        with self._lock:
            run = self._runs.get((session_id, model_preset))
            if run is None or run.expires_at <= time.monotonic():
                return None
            self._runs[(session_id, model_preset)] = replace(
                run,
                expires_at=time.monotonic() + self._ttl_seconds,
            )
        return run.provider

    def _prune_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired_keys = [key for key, run in self._runs.items() if run.expires_at <= now]
            for key in expired_keys:
                del self._runs[key]


class EscapeRunStore:
    """Short-lived cancellation state for browser escape runs."""

    def __init__(self, *, ttl_seconds: int = ESCAPE_RUN_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._runs: dict[tuple[str, str], EscapeRunRecord] = {}
        self._lock = Lock()

    def start(self, *, session_id: str, run_id: str) -> None:
        """Register an active run."""
        self._prune_expired()
        with self._lock:
            self._runs[(session_id, run_id)] = EscapeRunRecord(
                session_id=session_id,
                run_id=run_id,
                cancelled=False,
                expires_at=time.monotonic() + self._ttl_seconds,
            )

    def cancel(self, *, session_id: str, run_id: str | None = None) -> None:
        """Mark one run, or all known session runs, as cancelled."""
        self._prune_expired()
        with self._lock:
            for key, run in tuple(self._runs.items()):
                if run.session_id != session_id or (run_id is not None and run.run_id != run_id):
                    continue
                self._runs[key] = replace(
                    run,
                    cancelled=True,
                    expires_at=time.monotonic() + self._ttl_seconds,
                )

    def is_cancelled(self, *, session_id: str, run_id: str) -> bool:
        """Return whether a run has been cancelled."""
        self._prune_expired()
        with self._lock:
            run = self._runs.get((session_id, run_id))
            if run is None:
                return False
            return run.cancelled

    def finish(self, *, session_id: str, run_id: str) -> None:
        """Drop completed run state."""
        with self._lock:
            self._runs.pop((session_id, run_id), None)

    def _prune_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired_keys = [key for key, run in self._runs.items() if run.expires_at <= now]
            for key in expired_keys:
                del self._runs[key]


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
escape_run_store: Final = EscapeRunStore()


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
                "app_name": "WATCH MY ESCAPE",
                "app_data": app_data(),
            },
        )

    @app.api(name="run_model_escape")
    def run_escape_game() -> dict[str, Any]:
        return build_escape_run_response()

    @app.get("/escape-stream")
    def escape_stream(query: Annotated[EscapeStreamRequest, Query()]) -> StreamingResponse:
        try:
            config = config_for_model_preset(query.model_preset)
            game_map = _selected_stream_map(map_id=query.map_id, custom_map_token=query.custom_map_token)
            provider = _stream_provider(config=config, model_preset=query.model_preset, session_id=query.session_id)
            settings = think_act_settings_for_config(
                config,
                deliberation_enable_thinking=query.deliberation_enable_thinking,
                deliberation_temperature=query.deliberation_temperature,
            )
        except (ModelPresetError, PremadeMapError, CustomMapTokenError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        lifecycle = _stream_run_lifecycle(session_id=query.session_id, run_id=query.run_id)
        return StreamingResponse(
            _escape_event_stream(
                provider=provider,
                game_map=game_map,
                startup_delay_ms=query.startup_delay_ms,
                settings=settings,
                lifecycle=lifecycle,
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
        return warm_model_preset(session_id=request.session_id, model_preset=request.model_preset)

    app.post("/runs/cancel")(cancel_escape_run)

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
            "transcript_events": (
                {
                    "kind": "intro",
                    "message": str(exc),
                    "visible_entities": (),
                },
            ),
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
        "transcript_events": _transcript_events_payload(getattr(result, "transcript_events", ())),
    }


def cancel_escape_run(request: CancelEscapeRunRequest) -> dict[str, bool]:
    """Cancel one browser session's active escape run."""
    escape_run_store.cancel(session_id=request.session_id, run_id=request.run_id)
    return {"cancelled": True}


def app_data() -> dict[str, object]:
    """Return JSON-safe application data for the browser."""
    return {
        "models": model_preset_options(),
        "maps": premade_map_options(),
    }


def warm_model_preset(*, session_id: str, model_preset: str) -> dict[str, object]:
    """Run a tiny completion to prepare a model for the first game turn."""
    try:
        provider = warm_provider_store.get(session_id=session_id, model_preset=model_preset)
        if provider is None:
            provider = synchronized_provider(create_provider(config_for_model_preset(model_preset)))
            warm_provider_store.add(session_id=session_id, model_preset=model_preset, provider=provider)
        _run_warmup_completion(provider)
    except ModelPresetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LlmConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"warmed": True}


def _run_warmup_completion(provider: InferenceProvider) -> None:
    provider.complete(
        InferenceRequest(
            messages=(ChatMessage(role="user", content="Reply with OK."),),
            phase="warmup",
            settings=InferenceSettings(max_tokens=8, temperature=0.0),
            enable_thinking=False,
        )
    )


def _stream_provider(*, config: LlamaCppConfig, model_preset: str, session_id: str | None) -> InferenceProvider:
    if session_id is not None:
        provider = warm_provider_store.get(session_id=session_id, model_preset=model_preset)
        if provider is not None:
            return provider
    return synchronized_provider(create_provider(config))


def _stream_run_lifecycle(
    *,
    session_id: str | None,
    run_id: str | None,
) -> EscapeStreamLifecycle:
    if session_id is None or run_id is None:
        return DEFAULT_STREAM_LIFECYCLE

    escape_run_store.start(session_id=session_id, run_id=run_id)
    return EscapeStreamLifecycle(
        is_cancelled=lambda: escape_run_store.is_cancelled(session_id=session_id, run_id=run_id),
        on_complete=lambda: escape_run_store.finish(session_id=session_id, run_id=run_id),
    )


def model_preset_options() -> tuple[dict[str, object], ...]:
    """Return JSON-safe preset selector metadata."""
    return tuple(_model_preset_option(preset_id, preset) for preset_id, preset in MODEL_PRESETS.items())


def _model_preset_option(preset_id: str, preset: ModelPreset) -> dict[str, object]:
    thinking_enabled = preset.thinking_enabled if preset.thinking_enabled is not None else preset.thinking_supported
    return {
        "id": preset_id,
        "display_name": preset.display_name,
        "company": preset.company,
        "brand_color": preset.brand_color,
        "agent_icon": preset.agent_icon,
        "parameter_size_b": preset.parameter_size_b,
        "active_parameter_size_b": preset.active_parameter_size_b,
        "repo_id": preset.repo_id,
        "filename": preset.filename,
        "thinking_supported": preset.thinking_supported,
        "thinking_enabled": thinking_enabled,
        "thinking_temperature": preset.thinking_temperature,
        "thinking_top_p": preset.thinking_top_p,
        "thinking_top_k": preset.thinking_top_k,
    }


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
    lifecycle: EscapeStreamLifecycle = DEFAULT_STREAM_LIFECYCLE,
) -> Iterator[str]:
    stream_provider = _cancellable_stream_provider(provider, lifecycle=lifecycle)
    try:
        for frame in run_model_escape_steps(
            provider=stream_provider,
            game_map=game_map,
            startup_delay_ms=startup_delay_ms,
            settings=settings,
        ):
            if lifecycle.is_cancelled():
                break
            yield f"data: {json.dumps(_frame_payload(frame))}\n\n"
            if frame.delay_ms and _sleep_frame_delay(frame.delay_ms, is_cancelled=lifecycle.is_cancelled):
                break
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
            "transcript_events": (
                {
                    "kind": "intro",
                    "message": str(exc),
                    "visible_entities": (),
                },
            ),
            "escaped": False,
        }
        yield f"data: {json.dumps(payload)}\n\n"
    except EscapeRunCancelledError:
        return
    except Exception as exc:
        LOGGER.exception("Escape stream failed.")
        yield f"data: {json.dumps(_stream_error_payload(exc))}\n\n"
    finally:
        lifecycle.on_complete()


def _cancellable_stream_provider(
    provider: InferenceProvider | None,
    *,
    lifecycle: EscapeStreamLifecycle,
) -> InferenceProvider | None:
    if provider is None or lifecycle is DEFAULT_STREAM_LIFECYCLE:
        return provider
    return CancellableInferenceProvider(provider, lifecycle.is_cancelled)


def _sleep_frame_delay(delay_ms: int, *, is_cancelled: Callable[[], bool]) -> bool:
    remaining_seconds = delay_ms / 1000
    while remaining_seconds > 0:
        if is_cancelled():
            return True
        sleep_seconds = min(0.1, remaining_seconds)
        time.sleep(sleep_seconds)
        remaining_seconds -= sleep_seconds
    return is_cancelled()


def _stream_error_payload(exc: Exception) -> dict[str, object]:
    return {
        "status": "Model run failed.",
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
        "transcript": f"Model run failed: {exc}",
        "transcript_events": (
            {
                "kind": "intro",
                "message": f"Model run failed: {exc}",
                "visible_entities": (),
            },
        ),
        "escaped": False,
    }


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
        "transcript_events": _transcript_events_payload(frame.transcript_events),
        "escaped": frame.escaped,
    }


def _transcript_events_payload(events: object) -> tuple[dict[str, object], ...]:
    if not isinstance(events, tuple):
        return ()
    return tuple(_transcript_event_payload(event) for event in events)


def _transcript_event_payload(event: object) -> dict[str, object]:
    if isinstance(event, TranscriptIntroEvent):
        return {
            "kind": "intro",
            "message": event.message,
            "visible_entities": _entity_details_payload(event.visible_entities),
        }
    if isinstance(event, TranscriptTurnEvent):
        payload: dict[str, object] = {
            "kind": "turn",
            "turn_number": event.turn_number,
            "sanity_before": event.sanity_before,
            "sanity_after": event.sanity_after,
            "deliberation": event.deliberation,
            "action_type": event.action_type,
            "action_emoji": event.action_emoji,
            "action_text": event.action_text,
            "result": event.result,
            "effects": _action_effects_payload(event.effects),
        }
        if event.spoken_text is not None:
            payload["spoken_text"] = event.spoken_text
        return payload
    if isinstance(event, dict):
        return cast("dict[str, object]", event)
    return {"kind": "intro", "message": str(event), "visible_entities": ()}


def _action_effects_payload(effects: object) -> tuple[dict[str, str], ...]:
    if not isinstance(effects, tuple):
        return ()
    return tuple(_action_effect_payload(effect) for effect in effects)


def _action_effect_payload(effect: object) -> dict[str, str]:
    if isinstance(effect, ActionEffectSummary):
        return {
            "kind": effect.kind,
            "text": effect.text,
            "entity_id": effect.entity_id or "",
        }
    if isinstance(effect, dict):
        values = cast("dict[object, object]", effect)
        return {
            "kind": str(values.get("kind", "")),
            "text": str(values.get("text", "")),
            "entity_id": str(values.get("entity_id", "")),
        }
    return {"kind": "", "text": str(effect), "entity_id": ""}


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
