import sys
from types import ModuleType

from watch_my_escape.llm.tracing import is_langfuse_tracing_enabled, observe_if_enabled


def test_langfuse_tracing_is_disabled_without_complete_environment(monkeypatch):
    monkeypatch.delenv("LANGFUSE_TRACING_ENABLED", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)

    assert not is_langfuse_tracing_enabled()


def test_observe_if_enabled_returns_original_function_when_disabled(monkeypatch):
    monkeypatch.delenv("LANGFUSE_TRACING_ENABLED", raising=False)

    def function() -> str:
        return "ok"

    assert observe_if_enabled(function, name="test", as_type="span") is function


def test_observe_if_enabled_wraps_function_when_langfuse_is_configured(monkeypatch):
    calls: list[tuple[str, str]] = []

    def observe(*, name: str, as_type: str):
        calls.append((name, as_type))

        def decorator(function):
            def wrapped() -> str:
                return f"traced {function()}"

            return wrapped

        return decorator

    fake_langfuse = ModuleType("langfuse")
    fake_langfuse.__dict__["observe"] = observe
    monkeypatch.setitem(sys.modules, "langfuse", fake_langfuse)
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://langfuse.example")

    def function() -> str:
        return "ok"

    wrapped = observe_if_enabled(function, name="test", as_type="span")

    assert wrapped() == "traced ok"
    assert calls == [("test", "span")]
