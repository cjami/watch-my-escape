from argparse import Namespace
from pathlib import Path

import pytest

from watch_my_escape.llm.config import MODEL_PRESETS, LlamaCppConfig, LlmProviderName
from watch_my_escape.llm.evaluate_models import (
    CASES,
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


def test_evaluate_model_scores_think_then_act_turns():
    requests: list[InferenceRequest] = []

    def complete(request: InferenceRequest) -> InferenceResponse:
        requests.append(request)
        if request.structured_output is None:
            return InferenceResponse(content="I should choose the action that directly matches the room state.")

        user_content = request.messages[-1].content
        normalized_prompt = user_content.lower()
        if "pick up the brass key" in normalized_prompt:
            return InferenceResponse(
                content='Here is JSON: {"action":"pick_up","target":"brass key","emotion":"confident"}'
            )
        if "try the silver key" in normalized_prompt:
            return InferenceResponse(
                content='{"action":"use_item","item":"silver key","target":"locked diary","emotion":"focused"}'
            )
        if "look closely at the brass key" in normalized_prompt:
            return InferenceResponse(content='{"action":"examine","target":"brass key","emotion":"curious"}')
        raise AssertionError

    results = evaluate_model(complete)

    assert all(result.passed for result in results)
    assert len(requests) == len(CASES) * 2
    assert all(request.structured_output is None for request in requests[::2])
    assert all(request.structured_output is not None for request in requests[1::2])
    deliberation_prompts = "\n".join(request.messages[-1].content for request in requests[::2])
    assert "Evaluation-specific constraints" not in deliberation_prompts
    assert "- pick_up(target)" in deliberation_prompts
    assert "- use_item(item, target)" in deliberation_prompts


def test_evaluation_prompts_do_not_embed_json_or_specific_emotions():
    prompt_parts: list[str] = []
    for case in CASES:
        prompt_parts.extend((case.game_state, *case.history))
    prompt_text = "\n".join(prompt_parts).lower()

    assert "{" not in prompt_text
    assert "emotion" not in prompt_text
    assert "mood" not in prompt_text


def test_score_case_fails_when_action_json_has_wrong_shape():
    action_case = next(case for case in CASES if case.name == "action_examine")

    result = score_case(action_case, InferenceResponse(content='{"action":"inspect_object"}'))

    assert not result.passed
    assert result.actual.startswith("Schema validation failed:")


def test_score_case_ignores_emotion_value():
    action_case = next(case for case in CASES if case.name == "action_examine")

    result = score_case(
        action_case,
        InferenceResponse(content='{"action":"examine","target":"brass key","emotion":""}'),
    )

    assert result.passed


def test_score_case_rejects_target_outside_interactable_vocabulary():
    action_case = next(case for case in CASES if case.name == "action_examine")

    result = score_case(
        action_case,
        InferenceResponse(content='{"action":"examine","target":"ceiling vent","emotion":"curious"}'),
    )

    assert not result.passed
    assert result.actual.startswith("Schema validation failed:")


def test_score_case_rejects_item_outside_inventory_vocabulary():
    action_case = next(case for case in CASES if case.name == "action_use_item")

    result = score_case(
        action_case,
        InferenceResponse(
            content='{"action":"use_item","item":"rusty coin","target":"locked diary","emotion":"focused"}'
        ),
    )

    assert not result.passed
    assert result.actual.startswith("Schema validation failed:")


def test_score_case_strips_thinking_sections_before_parsing_json():
    json_case = next(case for case in CASES if case.name == "action_pick_up")

    result = score_case(
        json_case,
        InferenceResponse(
            content=(
                '<think>\nThe answer is {"action":"pick_up","target":"brass key","emotion":"confident"}.\n</think>\n'
                '{"action":"pick_up","target":"brass key","emotion":"confident"}'
            )
        ),
    )

    assert result.passed


def test_score_case_strips_dangling_thinking_close_before_parsing_json():
    json_case = next(case for case in CASES if case.name == "action_pick_up")

    result = score_case(
        json_case,
        InferenceResponse(
            content=(
                'We need to output {"action":"pick_up","target":"brass key","emotion":"confident"}.\n'
                '</think>\n{"action":"pick_up","target":"brass key","emotion":"confident"}'
            )
        ),
    )

    assert result.passed


def test_score_case_strips_unclosed_thinking_section_before_reporting_json_failure():
    json_case = next(case for case in CASES if case.name == "action_pick_up")

    result = score_case(
        json_case,
        InferenceResponse(
            content=(
                '<think>\nFirst, the user says: "Return this object exactly: '
                '{"action":"pick_up","target":"brass key","emotion":"confident"}"\n\n'
                "So, I need to return this object exactly as it is."
            )
        ),
    )

    assert not result.passed
    assert result.actual == "Response was empty: ''"


def test_score_case_strips_thinking_sections_before_reporting_action_json_failure():
    action_case = next(case for case in CASES if case.name == "action_examine")

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
                passed=True,
                expected="ok",
                actual="ok",
            ),
            CaseResult(
                case_name="json_case",
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
