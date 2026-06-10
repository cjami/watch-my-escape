# Watch My Escape

## Project Description

'Watch My Escape!' is an application where an LLM tries to escape a man-made puzzle room.

## Project Structure

- `src/watch_my_escape/app/` contains Gradio/FastAPI app wiring and API schemas.
- `src/watch_my_escape/game/` contains escape-room state, maps, rules, and tool wrappers.
- `src/watch_my_escape/agent/` contains LLM agent orchestration, prompts, history, and emotions.
- `src/watch_my_escape/llm/` contains local model integration and tool-call parsing.
- `src/watch_my_escape/web/` contains the Jinja2 templates and custom frontend assets.
- `tests/` contains pytest tests for backend behavior.
- `pyproject.toml` defines dependencies, Ruff linting, pytest settings, and package metadata.
- `.pre-commit-config.yaml` defines Git pre-commit hooks that run formatting, linting, type checking, and tests.
- `Makefile` provides the common development commands.

## Development Workflow

- Always use modern Python practices for Python 3.14+.
- Use TDD where appropriate to keep a considered design and protect key behaviours.
- Tidy-up and refactor after changes - make sure to follow SOLID principles.
- Run `make lint` and `make test` after changes.
- Use `uv run` for Python commands.
- Do not commit changes unless instructed.
- Do not start the web server unless instructed.

## Comments

- Keep all comments concise, clear, and suitable for inclusion in final production.
- Only use comments when the intent cannot be explained through thoughtful naming or code structure.

## Attribution

- When committing Codex-assisted work, include this trailer in the commit message:
  `Co-authored-by: Codex <codex@openai.com>`
