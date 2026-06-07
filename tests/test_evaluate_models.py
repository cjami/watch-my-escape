from argparse import Namespace
from pathlib import Path

import pytest

from watch_my_escape.llm.config import MODEL_PRESETS, LlamaCppConfig, LlmProviderName
from watch_my_escape.llm.evaluate_models import (
    CASES,
    Capability,
    CaseResult,
    ModelResult,
    build_model_targets,
    evaluate_model,
    format_results,
    score_case,
)
from watch_my_escape.llm.models import InferenceRequest, InferenceResponse


def _config(model_path: Path | None = None) -> LlamaCppConfig:
    return LlamaCppConfig(
        provider=LlmProviderName.LLAMA_CPP,
        model_preset=None,
        model_path=model_path,
        model_repo_id=None,
        model_filename=None,
        chat_format=None,
        context_tokens=4096,
        max_tokens=256,
        temperature=None,
        top_p=None,
        top_k=None,
        gpu_layers=-1,
        zerogpu_duration=60,
    )


def test_evaluate_model_scores_action_json_and_structured_json():
    def complete(request: InferenceRequest) -> InferenceResponse:
        assert request.structured_output is not None
        user_content = request.messages[-1].content
        if "brass key" in user_content:
            return InferenceResponse(content='{"action":"examine","target":"Brass Key","emotion":"🤔"}')
        if "silver key" in user_content:
            return InferenceResponse(
                content='{"action":"use_item","item":"silver key","target":"locked diary","emotion":"🙂"}'
            )
        if "move" in user_content:
            return InferenceResponse(content='```json\n{"action":"move","direction":"East","emotion":"🙂"}\n```')
        return InferenceResponse(
            content='Here is JSON: {"action":"take_note","text":"Clock code is 1432.","emotion":"🤓"}'
        )

    results = evaluate_model(complete)

    assert all(result.passed for result in results)
    assert {result.capability for result in results} == {Capability.ACTION_JSON, Capability.STRUCTURED_JSON}


def test_score_case_fails_when_action_json_has_wrong_shape():
    action_case = next(case for case in CASES if case.capability is Capability.ACTION_JSON)

    result = score_case(action_case, InferenceResponse(content='{"action":"inspect_object"}'))

    assert not result.passed
    assert result.actual.startswith("Schema validation failed:")


def test_score_case_strips_thinking_sections_before_parsing_json():
    json_case = next(case for case in CASES if case.name == "json_take_note_action")

    result = score_case(
        json_case,
        InferenceResponse(
            content=(
                '<think>\nThe answer is {"action":"take_note","text":"Clock code is 1432.","emotion":"🤓"}.\n</think>\n'
                '{"action":"take_note","text":"Clock code is 1432.","emotion":"🤓"}'
            )
        ),
    )

    assert result.passed


def test_score_case_strips_dangling_thinking_close_before_parsing_json():
    json_case = next(case for case in CASES if case.name == "json_move_action")

    result = score_case(
        json_case,
        InferenceResponse(
            content=(
                'We need to output {"action":"move","direction":"East","emotion":"🙂"}.\n'
                '</think>\n{"action":"move","direction":"East","emotion":"🙂"}'
            )
        ),
    )

    assert result.passed


def test_score_case_strips_unclosed_thinking_section_before_reporting_json_failure():
    json_case = next(case for case in CASES if case.name == "json_take_note_action")

    result = score_case(
        json_case,
        InferenceResponse(
            content=(
                '<think>\nFirst, the user says: "Return this object exactly: '
                '{"action":"take_note","text":"Clock code is 1432.","emotion":"🤓"}"\n\n'
                "So, I need to return this object exactly as it is."
            )
        ),
    )

    assert not result.passed
    assert result.actual == "Response was empty: ''"


def test_score_case_strips_thinking_sections_before_reporting_action_json_failure():
    action_case = next(case for case in CASES if case.capability is Capability.ACTION_JSON)

    result = score_case(action_case, InferenceResponse(content='<think>Use JSON.</think>\n{"action":"examine"}'))

    assert not result.passed
    assert result.actual.startswith("Schema validation failed:")


def test_build_model_targets_uses_configured_model_when_no_selectors_are_passed():
    args = Namespace(preset=[], all_presets=False, model_path=[])

    targets = build_model_targets(args, _config(Path("escape.gguf")))

    assert len(targets) == 1
    assert targets[0].name == "escape"
    assert targets[0].config.model_path == Path("escape.gguf")


def test_build_model_targets_can_select_all_presets():
    args = Namespace(preset=[], all_presets=True, model_path=[])

    targets = build_model_targets(args, _config())

    assert {target.name for target in targets} == set(MODEL_PRESETS)


def test_build_model_targets_rejects_missing_model_source():
    args = Namespace(preset=[], all_presets=False, model_path=[])

    with pytest.raises(ValueError, match="Configure WME_MODEL_PATH"):
        build_model_targets(args, _config())


def test_format_results_outputs_accuracy_table_and_failures():
    result = ModelResult(
        model_name="example",
        case_results=(
            CaseResult(
                case_name="action_case",
                capability=Capability.ACTION_JSON,
                passed=True,
                expected="ok",
                actual="ok",
            ),
            CaseResult(
                case_name="json_case",
                capability=Capability.STRUCTURED_JSON,
                passed=False,
                expected='{"ok":true}',
                actual="not json",
            ),
        ),
    )

    report = format_results((result,))

    assert "example" in report
    assert "50%" in report
    assert "Failures:" in report
    assert "json_case" in report
