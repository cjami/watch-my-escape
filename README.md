# Watch My Escape

An LLM tries to escape a man-made puzzle room.

## Development

Use `uv` for dependency management:

```shell
uv sync
```

Run checks with Make:

```shell
make test
make lint
```

Run the app:

```shell
make dev
```

## LLM setup

The application uses `llama-cpp-python` for inference. Choose one setup profile:

```shell
uv run python -m watch_my_escape.setup_llm cpu
uv run python -m watch_my_escape.setup_llm cuda
uv run python -m watch_my_escape.setup_llm metal
uv run python -m watch_my_escape.setup_llm hf-zerogpu
```

`make setup-llm-cpu`, `make setup-llm-cuda`, `make setup-llm-metal`, and `make setup-hf-zerogpu` are shortcuts when Make is available.

Configure a GGUF model with either `WME_MODEL_PATH` or `WME_MODEL_REPO_ID` plus `WME_MODEL_FILENAME`. Use `WME_GPU_LAYERS=-1` to offload all supported layers to GPU.

Sampling settings prefer explicit environment overrides, then GGUF model metadata, then reasoning-model fallbacks:

```shell
WME_TEMPERATURE=1.0
WME_TOP_P=0.95
WME_TOP_K=64
```

Check the current setup:

```shell
uv run python -m watch_my_escape.doctor
```
