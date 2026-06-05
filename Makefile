.PHONY: assets dev format lint test

assets:
	npx @tailwindcss/cli -i src/watch_my_escape/web/static/input.css -o src/watch_my_escape/web/static/dist/styles.css --minify
	npx esbuild src/watch_my_escape/web/static/app.js --minify --format=esm --outfile=src/watch_my_escape/web/static/dist/app.js

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ty check

format:
	uv run ruff check --fix .
	uv run ruff format .

dev:
	$(MAKE) assets
	uv run python -m watch_my_escape
