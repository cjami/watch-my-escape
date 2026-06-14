import importlib.util
import os
import time

from watch_my_escape import cli


def test_assets_need_build_when_outputs_are_missing(tmp_path, monkeypatch):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "app.js").write_text("console.log('hi')", encoding="utf-8")
    monkeypatch.setattr(cli, "SOURCE_STATIC_DIR", source_dir)
    monkeypatch.setattr(cli, "ASSET_OUTPUTS", (tmp_path / "build" / "app.js",))

    assert cli.assets_need_build()


def test_assets_skip_when_outputs_are_newer(tmp_path, monkeypatch):
    source_dir = tmp_path / "src"
    output_dir = tmp_path / "build"
    source_dir.mkdir()
    output_dir.mkdir()
    source = source_dir / "app.js"
    output = output_dir / "app.js"
    source.write_text("console.log('hi')", encoding="utf-8")
    output.write_text("bundle", encoding="utf-8")
    now = time.time()
    source_time = now - 10
    output_time = now
    source.touch()
    output.touch()

    os.utime(source, (source_time, source_time))
    os.utime(output, (output_time, output_time))
    monkeypatch.setattr(cli, "SOURCE_STATIC_DIR", source_dir)
    monkeypatch.setattr(cli, "ASSET_OUTPUTS", (output,))

    assert not cli.assets_need_build()


def test_ensure_llm_skips_existing_auto_cpu_without_state(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "SETUP_STATE_PATH", tmp_path / "setup-state.json")
    monkeypatch.setattr(cli, "detect_local_profile", lambda: "cpu")
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "llama_cpp" else None)
    monkeypatch.setattr(cli, "_run", lambda *_args, **_kwargs: None)

    cli.ensure_llm(profile="auto", force=False)

    assert not (tmp_path / "setup-state.json").exists()


def test_ensure_llm_installs_when_profile_changes(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "SETUP_STATE_PATH", tmp_path / "setup-state.json")
    monkeypatch.setattr(cli, "detect_local_profile", lambda: "vulkan")
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "llama_cpp" else None)
    monkeypatch.setattr(cli, "build_command", lambda profile: (("uv", "pip", "install", profile), {}))
    monkeypatch.setattr(cli, "_run", lambda command, **_kwargs: calls.append(command))

    cli.ensure_llm(profile="auto", force=False)

    assert calls == [("uv", "pip", "install", "vulkan")]
    assert '"llm_profile": "vulkan"' in (tmp_path / "setup-state.json").read_text(encoding="utf-8")


def test_main_launches_browser_by_default(monkeypatch):
    captured = {}

    class FakeApp:
        def launch(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(cli, "ensure_project_ready", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "create_app", FakeApp)

    cli.main([])

    assert captured["inbrowser"] is True


def test_main_respects_no_browser(monkeypatch):
    captured = {}

    class FakeApp:
        def launch(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(cli, "ensure_project_ready", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "create_app", FakeApp)

    cli.main(["--no-browser"])

    assert captured["inbrowser"] is False
