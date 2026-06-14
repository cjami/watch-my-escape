"""Hugging Face Space entry point for WATCH MY ESCAPE."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from watch_my_escape.app.server import create_app

app = create_app()

if __name__ == "__main__":
    app.launch(show_error=True)
