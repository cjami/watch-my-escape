"""Hugging Face Space entry point for Watch My Escape."""

from watch_my_escape.app.server import create_app

app = create_app()

if __name__ == "__main__":
    app.launch(show_error=True)
