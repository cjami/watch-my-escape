from watch_my_escape.game.engine import describe_escape_attempt


def test_describe_escape_attempt_uses_submitted_action():
    result = describe_escape_attempt("turn the brass key")

    assert result == "The room studies the attempt: turn the brass key. A hidden mechanism clicks somewhere nearby."


def test_describe_escape_attempt_handles_blank_action():
    result = describe_escape_attempt("   ")

    assert result == "The room waits. Every puzzle needs an opening attempt."
