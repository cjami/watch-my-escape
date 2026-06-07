"""Optional Langfuse tracing integration."""

from __future__ import annotations

import os
from importlib import import_module
from typing import TYPE_CHECKING

from watch_my_escape.llm.config import BOOLEAN_TRUE_VALUES, LANGFUSE_REQUIRED_KEYS

if TYPE_CHECKING:
    from collections.abc import Callable


def observe_if_enabled[**P, R](
    function: Callable[P, R],
    *,
    name: str,
    as_type: str,
    enabled: bool | None = None,
) -> Callable[P, R]:
    """Return a Langfuse-observed function when tracing is fully configured."""
    tracing_enabled = is_langfuse_tracing_enabled() if enabled is None else enabled
    if not tracing_enabled:
        return function

    try:
        observe = import_module("langfuse").__dict__["observe"]
    except (ImportError, KeyError):
        return function

    return observe(
        name=name,
        as_type=as_type,
    )(function)


def is_langfuse_tracing_enabled() -> bool:
    """Return whether Langfuse tracing should be active for this process."""
    if os.environ.get("LANGFUSE_TRACING_ENABLED", "").strip().lower() not in BOOLEAN_TRUE_VALUES:
        return False
    return all(os.environ.get(key, "").strip() for key in LANGFUSE_REQUIRED_KEYS)


def flush_langfuse_if_enabled() -> None:
    """Flush queued Langfuse events when tracing is active."""
    if not is_langfuse_tracing_enabled():
        return

    try:
        get_client = import_module("langfuse").__dict__["get_client"]
    except (ImportError, KeyError):
        return

    flush = getattr(get_client(), "flush", None)
    if callable(flush):
        flush()
