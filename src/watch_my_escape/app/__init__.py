"""Application entrypoints and HTTP/API wiring."""

from watch_my_escape.app.server import create_app

__all__ = ["create_app"]
