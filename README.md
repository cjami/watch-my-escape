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
Flash Attention defaults to `auto`: it is enabled when the installed llama.cpp
backend supports GPU offload and `WME_GPU_LAYERS` is not `0`. Override it with
`WME_FLASH_ATTN=true` or `WME_FLASH_ATTN=false`.

Supported Hub presets use Q4_K_M where available:

| Preset | Repository | Filename |
| --- | --- | --- |
| `gemma-4-12b-it` | `ggml-org/gemma-4-12B-it-GGUF` | `gemma-4-12B-it-Q4_K_M.gguf` |
| `nvidia-nemotron-3-nano-4b` | `nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF` | `NVIDIA-Nemotron3-Nano-4B-Q4_K_M.gguf` |
| `minicpm-v-4.6-thinking` | `openbmb/MiniCPM-V-4.6-Thinking-gguf` | `MiniCPM-V-4_6-Thinking-Q4_K_M.gguf` |
| `tiny-aya-global` | `CohereLabs/tiny-aya-global-GGUF` | `tiny-aya-global-q4_k_m.gguf` |
| `mellum2-12b-a2.5b-thinking` | `JetBrains/Mellum2-12B-A2.5B-Thinking-GGUF-Q4_K_M` | `Mellum2-12B-A2.5B-Thinking-Q4_K_M.gguf` |

```shell
WME_MODEL_PRESET=minicpm-v-4.6-thinking
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

Compare model reliability for Pydantic-constrained action JSON and structured JSON output:

```shell
uv run watch-my-escape-eval-models --preset minicpm-v-4.6-thinking --preset tiny-aya-global
uv run watch-my-escape-eval-models --all-presets
uv run watch-my-escape-eval-models --model-path local-small=~/models/model.gguf
```

When no model selector is provided, the evaluator uses the currently configured
`WME_MODEL_PRESET`, `WME_MODEL_PATH`, or Hub model source.

The evaluator sends Pydantic JSON Schemas through llama.cpp `response_format`,
so action commands are measured as structured JSON rather than native model
tool calls.

Hub presets are downloaded on first use through `huggingface-hub` and then reused
from the local Hugging Face cache. Prefer testing one preset first before
running `--all-presets`, since the full set can require many gigabytes:

```shell
WME_MODEL_PRESET=minicpm-v-4.6-thinking uv run watch-my-escape-eval-models
```
