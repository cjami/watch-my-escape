import pytest

from watch_my_escape.llm.tool_calls import ToolCallParseError, parse_tool_call


def test_parse_tool_call_returns_none_when_response_has_no_tool_calls():
    assert parse_tool_call({"content": "No tool."}) is None


def test_parse_tool_call_rejects_invalid_json_arguments():
    with pytest.raises(ToolCallParseError, match="not valid JSON"):
        parse_tool_call(
            {
                "tool_calls": [
                    {
                        "function": {
                            "name": "move_north",
                            "arguments": "{",
                        }
                    }
                ]
            }
        )


def test_parse_tool_call_rejects_non_object_arguments():
    with pytest.raises(ToolCallParseError, match="decode to an object"):
        parse_tool_call(
            {
                "tool_calls": [
                    {
                        "function": {
                            "name": "move_north",
                            "arguments": "[]",
                        }
                    }
                ]
            }
        )
