"""Install helper for llama-cpp-python setup profiles."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_DIR = Path(__file__).resolve().parents[2]
REQUIREMENTS_DIR = PROJECT_DIR / "requirements"

PROFILE_COMMANDS: dict[str, tuple[str, ...]] = {
    "cpu": ("uv", "pip", "install", "-r", str(REQUIREMENTS_DIR / "llm-cpu.txt")),
    "cuda": ("uv", "pip", "install", "-r", str(REQUIREMENTS_DIR / "llm-cuda-cu124.txt")),
    "hf-zerogpu": ("uv", "pip", "install", "-r", str(REQUIREMENTS_DIR / "hf-zerogpu.txt")),
}


def build_command(profile: str) -> tuple[tuple[str, ...], dict[str, str]]:
    """Return the install command and environment for a setup profile."""
    env = os.environ.copy()
    if profile == "metal":
        env["CMAKE_ARGS"] = "-DGGML_METAL=on"
        return (
            (
                "uv",
                "pip",
                "install",
                "--force-reinstall",
                "--no-cache-dir",
                "llama-cpp-python",
            ),
            env,
        )
    try:
        return PROFILE_COMMANDS[profile], env
    except KeyError as exc:
        msg = f"Unknown setup profile: {profile}"
        raise ValueError(msg) from exc


def main(argv: Sequence[str] | None = None) -> None:
    """Run an LLM setup profile."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=sorted([*PROFILE_COMMANDS, "metal"]))
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
