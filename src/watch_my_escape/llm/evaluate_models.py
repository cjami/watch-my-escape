"""Evaluate model reliability for Pydantic-constrained JSON output."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from watch_my_escape.game.actions import ExamineAction, MoveAction, TakeNoteAction, UseItemAction
from watch_my_escape.llm.client import LlmConfigurationError, create_provider
from watch_my_escape.llm.config import MODEL_PRESETS, LlamaCppConfig, load_config
from watch_my_escape.llm.models import (
    ChatMessage,
    InferenceRequest,
    InferenceResponse,
    InferenceSettings,
    StructuredOutputSpec,
)
from watch_my_escape.llm.structured import StructuredOutputError, parse_json_object, strip_thinking_sections

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence


class Capability(StrEnum):
    """Model capability families measured by the evaluator."""

    ACTION_JSON = "action_json"
    STRUCTURED_JSON = "structured_json"


@dataclass(frozen=True, slots=True)
class ExpectedPydanticJson:
    """Expected constrained JSON shape for one evaluation case."""

    model: type[BaseModel]
    value: BaseModel


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """One deterministic prompt and its expected model response."""

    name: str
    capability: Capability
    messages: tuple[ChatMessage, ...]
    expected: ExpectedPydanticJson


@dataclass(frozen=True, slots=True)
class CaseResult:
    """Pass/fail result for one model response."""

    case_name: str
    capability: Capability
    passed: bool
    expected: str
    actual: str


@dataclass(frozen=True, slots=True)
class ModelTarget:
    """A configured model source to evaluate."""

    name: str
    config: LlamaCppConfig


@dataclass(frozen=True, slots=True)
class ModelResult:
    """All case results for one model."""

    model_name: str
    case_results: tuple[CaseResult, ...]
    error: str | None = None

    @property
    def passed(self) -> int:
        """Return the number of passed cases."""
        return sum(result.passed for result in self.case_results)

    @property
    def total(self) -> int:
        """Return the number of attempted cases."""
        return len(self.case_results)

    @property
    def accuracy(self) -> float:
        """Return the pass ratio for attempted cases."""
        if self.total == 0:
            return 0.0
        return self.passed / self.total


CASES: tuple[EvaluationCase, ...] = (
    EvaluationCase(
        name="action_examine",
        capability=Capability.ACTION_JSON,
        messages=(
            ChatMessage(
                role="system",
                content=(
                    "You are controlling an escape-room agent. Return only the requested JSON command. "
                    "Do not include prose, markdown, or hidden reasoning."
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    "Return an examine command for the brass key with a thinking-face emotion. "
                    'The JSON shape is {"action":"examine","target":string,"emotion":emoji}.'
                ),
            ),
        ),
        expected=ExpectedPydanticJson(
            model=ExamineAction,
            value=ExamineAction(action="examine", target="brass key", emotion="🤔"),
        ),
    ),
    EvaluationCase(
        name="action_use_item",
        capability=Capability.ACTION_JSON,
        messages=(
            ChatMessage(
                role="system",
                content=(
                    "You are controlling an escape-room agent. Return only the requested JSON command. "
                    "Do not include prose, markdown, or hidden reasoning."
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    'Return a use_item command. The item is "silver key" and the target is "locked diary". '
                    'Use a smiling emotion. The JSON shape is {"action":"use_item","item":string,"target":string,'
                    '"emotion":emoji}.'
                ),
            ),
        ),
        expected=ExpectedPydanticJson(
            model=UseItemAction,
            value=UseItemAction(action="use_item", item="silver key", target="locked diary", emotion="🙂"),
        ),
    ),
    EvaluationCase(
        name="json_move_action",
        capability=Capability.STRUCTURED_JSON,
        messages=(
            ChatMessage(
                role="system",
                content=("Return only valid JSON. Use double quotes, no markdown, no prose, and no trailing commas."),
            ),
            ChatMessage(
                role="user",
                content='Return this object exactly: {"action":"move","direction":"East","emotion":"🙂"}',
            ),
        ),
        expected=ExpectedPydanticJson(
            model=MoveAction,
            value=MoveAction(action="move", direction="East", emotion="🙂"),
        ),
    ),
    EvaluationCase(
        name="json_take_note_action",
        capability=Capability.STRUCTURED_JSON,
        messages=(
            ChatMessage(
                role="system",
                content=("Return only valid JSON. Use double quotes, no markdown, no prose, and no trailing commas."),
            ),
            ChatMessage(
                role="user",
                content=(
                    'Return this object exactly: {"action":"take_note","text":"Clock code is 1432.","emotion":"🤓"}'
                ),
            ),
        ),
        expected=ExpectedPydanticJson(
            model=TakeNoteAction,
            value=TakeNoteAction(action="take_note", text="Clock code is 1432.", emotion="🤓"),
        ),
    ),
)


def evaluate_model(provider_complete: Callable[[InferenceRequest], InferenceResponse]) -> tuple[CaseResult, ...]:
    """Run all capability checks against a provider completion function."""
    results: list[CaseResult] = []
    for case in CASES:
        request = InferenceRequest(
            messages=case.messages,
            structured_output=StructuredOutputSpec.from_pydantic_model(case.expected.model),
            settings=InferenceSettings(max_tokens=128, temperature=0.0, top_p=1.0),
        )
        response = provider_complete(request)
        results.append(score_case(case, response))
    return tuple(results)


def score_case(case: EvaluationCase, response: InferenceResponse) -> CaseResult:
    """Score one response against the case expectation."""
    return _score_pydantic_json(case, case.expected, response)


def format_results(results: Sequence[ModelResult]) -> str:
    """Return a compact plain-text report for model capability results."""
    rows = [
        (
            "Model",
            "Action JSON",
            "Structured JSON",
            "Overall",
            "Passed",
            "Status",
        )
    ]
    rows.extend(
        (
            result.model_name,
            _format_capability_accuracy(result, Capability.ACTION_JSON),
            _format_capability_accuracy(result, Capability.STRUCTURED_JSON),
            f"{result.accuracy:.0%}",
            f"{result.passed}/{result.total}",
            result.error or "ok",
        )
        for result in results
    )

    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    lines = ["  ".join(value.ljust(widths[index]) for index, value in enumerate(rows[0]))]
    lines.append("  ".join("-" * width for width in widths))
    lines.extend("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in rows[1:])

    failure_lines = _format_failures(results)
    if failure_lines:
        lines.extend(("", "Failures:", *failure_lines))
    return "\n".join(lines)


def build_model_targets(args: argparse.Namespace, base_config: LlamaCppConfig) -> tuple[ModelTarget, ...]:
    """Resolve CLI model selectors into concrete model targets."""
    targets: list[ModelTarget] = []
    preset_names = list(args.preset)
    if args.all_presets:
        preset_names.extend(MODEL_PRESETS)
    targets.extend(_target_from_preset(preset_name, base_config) for preset_name in dict.fromkeys(preset_names))

    targets.extend(_target_from_model_path(raw_model_path, base_config) for raw_model_path in args.model_path)

    if not targets and base_config.has_model_source:
        targets.append(ModelTarget(name=_configured_model_name(base_config), config=base_config))

    if not targets:
        msg = "Configure WME_MODEL_PATH/WME_MODEL_PRESET, pass --model-path, or pass --preset/--all-presets."
        raise ValueError(msg)
    return tuple(targets)


def main(argv: Sequence[str] | None = None) -> int:
    """Run model capability evaluation from the command line."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        targets = build_model_targets(args, load_config())
    except (ValueError, LlmConfigurationError) as exc:
        parser.error(str(exc))

    results: list[ModelResult] = []
    for target in targets:
        print(f"Evaluating {target.name}...", flush=True)
        try:
            provider = create_provider(target.config)
            case_results = evaluate_model(provider.complete)
        except Exception as exc:  # noqa: BLE001
            results.append(ModelResult(model_name=target.name, case_results=(), error=f"{type(exc).__name__}: {exc}"))
            continue
        results.append(ModelResult(model_name=target.name, case_results=case_results))

    print()
    print(format_results(results))
    return 1 if any(result.error for result in results) else 0


def _score_pydantic_json(
    case: EvaluationCase,
    expected: ExpectedPydanticJson,
    response: InferenceResponse,
) -> CaseResult:
    sanitized_content = strip_thinking_sections(response.content)
    try:
        parsed = parse_json_object(sanitized_content)
    except StructuredOutputError as exc:
        return CaseResult(
            case_name=case.name,
            capability=case.capability,
            passed=False,
            expected=_format_json(_model_dump(expected.value)),
            actual=f"{exc}: {sanitized_content!r}",
        )
    try:
        actual_value = expected.model.model_validate(parsed)
    except ValidationError as exc:
        return CaseResult(
            case_name=case.name,
            capability=case.capability,
            passed=False,
            expected=_format_json(_model_dump(expected.value)),
            actual=f"Schema validation failed: {exc.errors(include_url=False)}",
        )

    return CaseResult(
        case_name=case.name,
        capability=case.capability,
        passed=_normalize_value(_model_dump(actual_value)) == _normalize_value(_model_dump(expected.value)),
        expected=_format_json(_model_dump(expected.value)),
        actual=_format_json(_model_dump(actual_value)),
    )


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_value(inner_value) for key, inner_value in sorted(value.items())}
    if isinstance(value, list):
        return [_normalize_value(inner_value) for inner_value in value]
    if isinstance(value, str):
        return " ".join(value.strip().lower().split())
    return value


def _model_dump(value: BaseModel) -> dict[str, Any]:
    return value.model_dump(mode="json")


def _target_from_preset(preset_name: str, base_config: LlamaCppConfig) -> ModelTarget:
    try:
        preset = MODEL_PRESETS[preset_name]
    except KeyError as exc:
        available = ", ".join(MODEL_PRESETS)
        msg = f"Unknown preset {preset_name!r}. Available presets: {available}."
        raise ValueError(msg) from exc

    return ModelTarget(
        name=preset_name,
        config=replace(
            base_config,
            model_preset=preset_name,
            model_path=None,
            model_repo_id=preset.repo_id,
            model_filename=preset.filename,
        ),
    )


def _target_from_model_path(raw_model_path: str, base_config: LlamaCppConfig) -> ModelTarget:
    if "=" in raw_model_path:
        name, raw_path = raw_model_path.split("=", maxsplit=1)
        if not name or not raw_path:
            msg = "--model-path must be PATH or NAME=PATH."
            raise ValueError(msg)
    else:
        path = Path(raw_model_path).expanduser()
        name = path.stem
        raw_path = raw_model_path

    return ModelTarget(
        name=name,
        config=replace(
            base_config,
            model_preset=None,
            model_path=Path(raw_path).expanduser(),
            model_repo_id=None,
            model_filename=None,
        ),
    )


def _configured_model_name(config: LlamaCppConfig) -> str:
    if config.model_preset:
        return config.model_preset
    if config.model_path:
        return config.model_path.stem
    if config.model_repo_id and config.model_filename:
        return f"{config.model_repo_id}/{config.model_filename}"
    return "configured"


def _format_capability_accuracy(result: ModelResult, capability: Capability) -> str:
    case_results = [case_result for case_result in result.case_results if case_result.capability is capability]
    if not case_results:
        return "n/a"
    passed = sum(case_result.passed for case_result in case_results)
    return f"{passed / len(case_results):.0%}"


def _format_failures(results: Iterable[ModelResult]) -> list[str]:
    lines: list[str] = []
    for result in results:
        for case_result in result.case_results:
            if case_result.passed:
                continue
            lines.append(
                f"- {result.model_name} {case_result.case_name}: expected {case_result.expected}; "
                f"actual {case_result.actual}"
            )
    return lines


def _format_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preset",
        action="append",
        default=[],
        choices=sorted(MODEL_PRESETS),
        help="Evaluate a known Hub model preset. Can be passed more than once.",
    )
    parser.add_argument(
        "--all-presets",
        action="store_true",
        help="Evaluate every known Hub model preset.",
    )
    parser.add_argument(
        "--model-path",
        action="append",
        default=[],
        metavar="PATH|NAME=PATH",
        help="Evaluate a local GGUF model path. Can be passed more than once.",
    )
    return parser


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
