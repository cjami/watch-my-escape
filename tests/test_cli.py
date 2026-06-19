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


def test_ensure_llm_repairs_cuda_when_runtime_packages_are_missing(monkeypatch, tmp_path):
    calls = []
    state_path = tmp_path / "setup-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{"llm_profile": "cuda"}', encoding="utf-8")
    monkeypatch.setattr(cli, "SETUP_STATE_PATH", state_path)
    monkeypatch.setattr(cli, "detect_local_profile", lambda: "cuda")

    def fake_find_spec(name):
        if name == "llama_cpp":
            return object()
        if name in cli.CUDA_RUNTIME_PACKAGES:
            return None
        msg = f"No module named {name!r}"
        raise ModuleNotFoundError(msg)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(cli, "build_command", lambda profile: (("uv", "pip", "install", profile), {}))
    monkeypatch.setattr(cli, "_run", lambda command, **_kwargs: calls.append(command))

    cli.ensure_llm(profile="auto", force=False)

    assert calls == [("uv", "pip", "install", "cuda")]


def test_main_launches_browser_by_default(monkeypatch):
    captured = {}

    class FakeApp:
        def launch(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(cli, "server_port_in_use", lambda *_args: False)
    monkeypatch.setattr(cli, "ensure_project_ready", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "create_app", FakeApp)

    cli.main([])

    assert captured["inbrowser"] is True


def test_main_respects_no_browser(monkeypatch):
    captured = {}

    class FakeApp:
        def launch(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(cli, "server_port_in_use", lambda *_args: False)
    monkeypatch.setattr(cli, "ensure_project_ready", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "create_app", FakeApp)

    cli.main(["--no-browser"])

    assert captured["inbrowser"] is False


def test_main_skips_launch_when_default_server_port_is_in_use(monkeypatch, capsys):
    launched = False

    class FakeApp:
        def launch(self, **_kwargs):
            nonlocal launched
            launched = True

    monkeypatch.setattr(cli, "server_port_in_use", lambda server_name, port: server_name is None and port == 7860)
    monkeypatch.setattr(cli, "ensure_project_ready", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "create_app", FakeApp)

    cli.main([])

    assert not launched
    assert "already be running at http://127.0.0.1:7860/" in capsys.readouterr().out


def test_main_checks_requested_server_port(monkeypatch):
    captured = {}
    seen = {}

    class FakeApp:
        def launch(self, **kwargs):
            captured.update(kwargs)

    def port_in_use(server_name, port):
        seen["server_name"] = server_name
        seen["port"] = port
        return False

    monkeypatch.setattr(cli, "server_port_in_use", port_in_use)
    monkeypatch.setattr(cli, "ensure_project_ready", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "create_app", FakeApp)

    cli.main(["--server-port", "8000"])

    assert seen == {"server_name": None, "port": 8000}
    assert captured["server_port"] == 8000


def test_main_allow_multiple_skips_port_check(monkeypatch):
    captured = {}

    class FakeApp:
        def launch(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(cli, "server_port_in_use", lambda *_args: True)
    monkeypatch.setattr(cli, "ensure_project_ready", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "create_app", FakeApp)

    cli.main(["--allow-multiple"])

    assert captured["server_port"] is None
