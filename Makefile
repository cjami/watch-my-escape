.PHONY: assets dev doctor eval-models format lint setup-llm-cpu setup-llm-cuda setup-llm-metal setup-hf-zerogpu test

assets:
	npx @tailwindcss/cli -i src/watch_my_escape/web/static/input.css -o build/web/static/styles.css --minify
	npx esbuild src/watch_my_escape/web/static/app.js --minify --format=esm --outfile=build/web/static/app.js

test:
	uv run pytest

doctor:
	uv run python -m watch_my_escape.doctor

eval-models:
	uv run python -m watch_my_escape.llm.evaluate_models

setup-llm-cpu:
	uv run python -m watch_my_escape.setup_llm cpu

setup-llm-cuda:
	uv run python -m watch_my_escape.setup_llm cuda

setup-llm-metal:
	uv run python -m watch_my_escape.setup_llm metal

setup-hf-zerogpu:
	uv run python -m watch_my_escape.setup_llm hf-zerogpu

lint:
	uv run ruff check .
	uv run ty check

format:
	uv run ruff check --fix .
	uv run ruff format .

dev:
	$(MAKE) assets
	uv run python -m watch_my_escape
