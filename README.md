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

Configure a GGUF model with `WME_MODEL_PRESET`, `WME_MODEL_PATH`, or `WME_MODEL_REPO_ID` plus `WME_MODEL_FILENAME`. Use `WME_GPU_LAYERS=-1` to offload all supported layers to GPU.

Supported Hub presets use Q4_K_M where available:

| Preset | Repository | Filename |
| --- | --- | --- |
| `gemma-4-12b-it` | `ggml-org/gemma-4-12B-it-GGUF` | `gemma-4-12B-it-Q4_K_M.gguf` |
| `nvidia-nemotron-3-nano-4b` | `nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF` | `NVIDIA-Nemotron3-Nano-4B-Q4_K_M.gguf` |
| `minicpm5-1b` | `openbmb/MiniCPM5-1B-GGUF` | `MiniCPM5-1B-Q4_K_M.gguf` |
| `tiny-aya-global` | `CohereLabs/tiny-aya-global-GGUF` | `tiny-aya-global-q4_k_m.gguf` |
| `mellum2-12b-a2.5b-thinking` | `JetBrains/Mellum2-12B-A2.5B-Thinking-GGUF-Q4_K_M` | `Mellum2-12B-A2.5B-Thinking-Q4_K_M.gguf` |

```shell
WME_MODEL_PRESET=minicpm5-1b
```

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
