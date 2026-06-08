"""Puzzle-room escape behavior."""


def describe_escape_attempt(action: str) -> str:
    """Describe the next room response to an attempted escape action."""
    normalized_action = action.strip()
    if not normalized_action:
        return "The room waits. Every puzzle needs an opening attempt."

    return f"The room studies the attempt: {normalized_action}. A hidden mechanism clicks somewhere nearby."
