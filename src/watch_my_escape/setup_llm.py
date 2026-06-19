"""Install helper for llama-cpp-python setup profiles."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_DIR = Path(__file__).resolve().parents[2]
REQUIREMENTS_DIR = PROJECT_DIR / "requirements"


def _install_requirements_command(requirement_file: str) -> tuple[str, ...]:
    return ("uv", "pip", "install", "--python", sys.executable, "-r", str(REQUIREMENTS_DIR / requirement_file))


PROFILE_COMMANDS: dict[str, tuple[str, ...]] = {
    "cpu": _install_requirements_command("llm-cpu.txt"),
    "cuda": _install_requirements_command("llm-cuda-cu124.txt"),
    "hf-zerogpu": _install_requirements_command("hf-zerogpu.txt"),
    "metal": _install_requirements_command("llm-metal.txt"),
    "vulkan": _install_requirements_command("llm-vulkan.txt"),
}
LOCAL_PROFILES: tuple[str, ...] = ("metal", "cuda", "vulkan", "cpu")
MANUAL_LOCAL_PROFILES: tuple[str, ...] = (*LOCAL_PROFILES, "rocm")


def detect_local_profile() -> str:
    """Return the best local acceleration profile detected on this machine."""
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin" and machine in {"arm64", "aarch64"}:
        return "metal"
    if _command_succeeds("nvidia-smi"):
        return "cuda"
    if _command_available("vulkaninfo") or _command_available("vkcube"):
        return "vulkan"
    return "cpu"


def build_command(profile: str) -> tuple[tuple[str, ...], dict[str, str]]:
    """Return the install command and environment for a setup profile."""
    env = os.environ.copy()
    if profile == "auto":
        profile = detect_local_profile()
    if profile == "rocm":
        return _rocm_command(env)
    try:
        return PROFILE_COMMANDS[profile], env
    except KeyError as exc:
        msg = f"Unknown setup profile: {profile}"
        raise ValueError(msg) from exc


def _rocm_command(env: dict[str, str]) -> tuple[tuple[str, ...], dict[str, str]]:
    if sys.platform.startswith("linux"):
        return _install_requirements_command("llm-rocm-linux.txt"), env
    if sys.platform == "win32":
        return _install_requirements_command("llm-rocm-windows.txt"), env
    env["CMAKE_ARGS"] = "-DGGML_HIP=on"
    return (
        (
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--force-reinstall",
            "--no-cache-dir",
            "llama-cpp-python",
        ),
        env,
    )


def _command_available(command: str) -> bool:
    return shutil.which(command) is not None


def _command_succeeds(command: str) -> bool:
    executable = shutil.which(command)
    if executable is None:
        return False
    result = subprocess.run((executable,), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def main(argv: Sequence[str] | None = None) -> None:
    """Run an LLM setup profile."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=sorted([*PROFILE_COMMANDS, "auto", "rocm"]))
    parser.add_argument("--dry-run", action="store_true", help="Print the command without running it.")
    args = parser.parse_args(argv)

    command, env = build_command(args.profile)
    if args.dry_run:
        cmake_args = env.get("CMAKE_ARGS")
        if cmake_args:
            print(f"CMAKE_ARGS={cmake_args}")
        print(" ".join(command))
        return

    subprocess.run(command, check=True, env=env)


if __name__ == "__main__":
    main(sys.argv[1:])
