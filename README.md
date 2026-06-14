# WATCH MY ESCAPE

An LLM tries to escape a man-made puzzle room.

## Quick Start

Install the prerequisites, then run one command from the repository:

```shell
git clone https://github.com/cjami/watch-my-escape.git
cd watch-my-escape
uv run watch-my-escape
```

The command sets up missing dependencies, builds the browser assets, installs the best local `llama-cpp-python` backend it can detect, starts the local server, and opens the game in your browser.

On first run, the selected GGUF model downloads from Hugging Face. That can take a while and may use several gigabytes of disk space.

## Prerequisites

- Git, if you are cloning the repository.
- `uv` for Python environment management: https://docs.astral.sh/uv/getting-started/installation/
- Node.js and npm for building browser assets: https://nodejs.org/
- Python 3.12 or newer. `uv` can usually install and manage this for you.

Make is not required to run the app.

## Setup Options

Run setup without starting the server:

```shell
uv run watch-my-escape --setup-only
```

Force setup to run again:

```shell
uv run watch-my-escape --force-setup
```

Start the server without opening a browser:

```shell
uv run watch-my-escape --no-browser
```

Override the detected local LLM backend:

```shell
uv run watch-my-escape --llm-profile metal
uv run watch-my-escape --llm-profile cuda
uv run watch-my-escape --llm-profile vulkan
uv run watch-my-escape --llm-profile rocm
uv run watch-my-escape --llm-profile cpu
```

Auto-detection prefers Apple Metal, then NVIDIA CUDA, then Vulkan, then CPU. ROCm is available as an explicit override because ROCm support depends more heavily on the installed OS, GPU, and driver stack.

## Langfuse Tracing

Langfuse tracing is optional. Add these variables to your shell or a local `.env` file:

```shell
LANGFUSE_TRACING_ENABLED=true
LANGFUSE_SECRET_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_BASE_URL=...
```

Set `LANGFUSE_TRACING_ENABLED=false` to disable tracing locally.

## Development

Common contributor commands:

```shell
make app
make test
make lint
make format
make assets
```

Without Make:

```shell
uv run watch-my-escape
uv run pytest
uv run ruff check .
uv run ty check
```

Check the current local LLM setup:

```shell
uv run watch-my-escape-doctor
```

Evaluate model reliability for structured action JSON:

```shell
uv run watch-my-escape-eval-models --preset minicpm5-1b
```
