"""Local setup and launch command for WATCH MY ESCAPE."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
from ipaddress import ip_address
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from watch_my_escape.app.server import create_app
from watch_my_escape.setup_llm import MANUAL_LOCAL_PROFILES, build_command, detect_local_profile

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

PROJECT_DIR: Final = Path(__file__).resolve().parents[2]
SOURCE_STATIC_DIR: Final = PROJECT_DIR / "src" / "watch_my_escape" / "web" / "static"
GENERATED_STATIC_DIR: Final = PROJECT_DIR / "build" / "web" / "static"
SETUP_STATE_PATH: Final = PROJECT_DIR / "build" / "setup-state.json"
DEFAULT_SERVER_PORT: Final = 7860
ASSET_OUTPUTS: Final = (
    GENERATED_STATIC_DIR / "styles.css",
    GENERATED_STATIC_DIR / "app.js",
    GENERATED_STATIC_DIR / "fonts" / "NotoEmoji-Variable.woff2",
    GENERATED_STATIC_DIR / "fonts" / "Silkscreen-Bold.ttf",
    GENERATED_STATIC_DIR / "fonts" / "Silkscreen-Regular.ttf",
)


def main(argv: Sequence[str] | None = None) -> None:
    """Prepare the project, then launch the local game server."""
    args = _parse_args(argv)
    ensure_project_ready(llm_profile=args.llm_profile, force=args.force_setup)
    if args.setup_only:
        print("Setup is complete.")
        return

    if args.allow_multiple:
        _launch_app(args)
        return

    port = args.server_port or DEFAULT_SERVER_PORT
    if server_port_in_use(args.server_name, port):
        host = _connect_host(args.server_name)
        print(f"WATCH MY ESCAPE appears to already be running at http://{host}:{port}/.")
        return

    _launch_app(args)


def ensure_project_ready(*, llm_profile: str, force: bool = False) -> None:
    """Install missing local dependencies and build generated assets."""
    _ensure_tool("uv", install_hint="Install uv from https://docs.astral.sh/uv/getting-started/installation/")
    _ensure_python_environment(force=force)
    _ensure_assets(force=force)
    ensure_llm(profile=llm_profile, force=force)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up WATCH MY ESCAPE, then launch the local game.")
    parser.add_argument(
        "--llm-profile",
        choices=("auto", *MANUAL_LOCAL_PROFILES),
        default="auto",
        help="Local llama.cpp backend to install. Auto prefers Metal, CUDA, Vulkan, then CPU.",
    )
    parser.add_argument("--force-setup", action="store_true", help="Re-run dependency setup and asset builds.")
    parser.add_argument("--setup-only", action="store_true", help="Prepare the project without starting the server.")
    parser.add_argument("--no-browser", action="store_true", help="Start the server without opening a browser.")
    parser.add_argument("--server-name", help="Host/interface for the local Gradio server.")
    parser.add_argument("--server-port", type=int, help="Port for the local Gradio server.")
    parser.add_argument("--allow-multiple", action="store_true", help="Start even if another local server is running.")
    return parser.parse_args(argv)


def _launch_app(args: argparse.Namespace) -> None:
    create_app().launch(
        show_error=True,
        inbrowser=not args.no_browser,
        server_name=args.server_name,
        server_port=args.server_port,
    )


def server_port_in_use(server_name: str | None, server_port: int) -> bool:
    """Return whether the target launch port is already accepting connections."""
    try:
        with socket.create_connection((_connect_host(server_name), server_port), timeout=0.2):
            return True
    except OSError:
        return False


def _connect_host(server_name: str | None) -> str:
    if not server_name:
        return "127.0.0.1"
    try:
        if ip_address(server_name).is_unspecified:
            return "127.0.0.1"
    except ValueError:
        return server_name
    return server_name


def _ensure_python_environment(*, force: bool) -> None:
    if force or not (PROJECT_DIR / ".venv").exists():
        _run(("uv", "sync"))


def _ensure_assets(*, force: bool) -> None:
    if not force and not assets_need_build():
        print("Frontend assets are already built.")
        return

    _ensure_tool("node", install_hint="Install Node.js from https://nodejs.org/")
    _ensure_tool("npm", install_hint="Install Node.js from https://nodejs.org/; npm is included.")
    if force or not (PROJECT_DIR / "node_modules").exists():
        _run(("npm", "ci"))
    _build_assets()


def ensure_llm(*, profile: str, force: bool) -> None:
    """Install the selected llama-cpp-python backend when it is missing or stale."""
    selected_profile = detect_local_profile() if profile == "auto" else profile
    state = _read_setup_state()
    installed_profile = state.get("llm_profile")
    llama_cpp_installed = importlib.util.find_spec("llama_cpp") is not None
    needs_install = (
        force
        or not llama_cpp_installed
        or (selected_profile != installed_profile and (profile != "auto" or selected_profile != "cpu"))
    )
    if not needs_install:
        print(f"llama-cpp-python is already installed ({installed_profile or 'existing'} profile).")
        return

    print(f"Installing llama-cpp-python with the {selected_profile} profile.")
    command, env = build_command(selected_profile)
    _run(command, env=env)
    _write_setup_state({**state, "llm_profile": selected_profile})


def assets_need_build() -> bool:
    """Return whether generated frontend assets are missing or older than sources."""
    if any(not path.exists() for path in ASSET_OUTPUTS):
        return True
    sources = tuple(_asset_sources())
    if not sources:
        return True
    newest_source = max(path.stat().st_mtime for path in sources)
    oldest_output = min(path.stat().st_mtime for path in ASSET_OUTPUTS)
    return newest_source > oldest_output


def _asset_sources() -> Iterable[Path]:
    return (path for path in SOURCE_STATIC_DIR.rglob("*") if path.is_file())


def _build_assets() -> None:
    GENERATED_STATIC_DIR.mkdir(parents=True, exist_ok=True)
    _run(
        (
            "npm",
            "exec",
            "--",
            "@tailwindcss/cli",
            "-i",
            str(SOURCE_STATIC_DIR / "input.css"),
            "-o",
            str(GENERATED_STATIC_DIR / "styles.css"),
            "--minify",
        )
    )
    _run(
        (
            "npm",
            "exec",
            "--",
            "esbuild",
            str(SOURCE_STATIC_DIR / "app.js"),
            "--bundle",
            "--minify",
            "--format=esm",
            f"--outfile={GENERATED_STATIC_DIR / 'app.js'}",
        )
    )
    _copy_fonts()


def _copy_fonts() -> None:
    source_dir = SOURCE_STATIC_DIR / "fonts"
    target_dir = GENERATED_STATIC_DIR / "fonts"
    target_dir.mkdir(parents=True, exist_ok=True)
    for source in source_dir.iterdir():
        if source.is_file():
            shutil.copy2(source, target_dir / source.name)


def _ensure_tool(command: str, *, install_hint: str) -> None:
    if shutil.which(command) is not None:
        return
    msg = f"`{command}` is required before setup can continue. {install_hint}"
    raise SystemExit(msg)


def _read_setup_state() -> dict[str, Any]:
    if not SETUP_STATE_PATH.exists():
        return {}
    try:
        value = json.loads(SETUP_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_setup_state(state: dict[str, Any]) -> None:
    SETUP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETUP_STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _run(command: Sequence[str], *, env: dict[str, str] | None = None) -> None:
    executable = shutil.which(command[0])
    resolved_command = (executable, *command[1:]) if executable is not None else command
    subprocess.run(resolved_command, check=True, cwd=PROJECT_DIR, env=env)


if __name__ == "__main__":
    main(sys.argv[1:])
