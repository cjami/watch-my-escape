from watch_my_escape import setup_llm
from watch_my_escape.setup_llm import build_command, detect_local_profile


def test_cpu_profile_installs_cpu_requirements():
    command, env = build_command("cpu")

    assert command[:4] == ("uv", "pip", "install", "-r")
    assert command[4].endswith("requirements\\llm-cpu.txt") or command[4].endswith("requirements/llm-cpu.txt")
    assert "CMAKE_ARGS" not in env


def test_cuda_profile_installs_cuda_requirements():
    command, _env = build_command("cuda")

    assert command[:4] == ("uv", "pip", "install", "-r")
    assert command[4].endswith("requirements\\llm-cuda-cu124.txt") or command[4].endswith(
        "requirements/llm-cuda-cu124.txt"
    )


def test_metal_profile_sets_metal_build_flag():
    command, env = build_command("metal")

    assert command[:4] == ("uv", "pip", "install", "-r")
    assert command[4].endswith("requirements\\llm-metal.txt") or command[4].endswith("requirements/llm-metal.txt")
    assert "CMAKE_ARGS" not in env


def test_vulkan_profile_installs_vulkan_requirements():
    command, _env = build_command("vulkan")

    assert command[:4] == ("uv", "pip", "install", "-r")
    assert command[4].endswith("requirements\\llm-vulkan.txt") or command[4].endswith("requirements/llm-vulkan.txt")


def test_rocm_profile_installs_linux_requirements(monkeypatch):
    monkeypatch.setattr(setup_llm.sys, "platform", "linux")

    command, _env = build_command("rocm")

    assert command[:4] == ("uv", "pip", "install", "-r")
    assert command[4].endswith("requirements\\llm-rocm-linux.txt") or command[4].endswith(
        "requirements/llm-rocm-linux.txt"
    )


def test_rocm_profile_installs_windows_requirements(monkeypatch):
    monkeypatch.setattr(setup_llm.sys, "platform", "win32")

    command, _env = build_command("rocm")

    assert command[:4] == ("uv", "pip", "install", "-r")
    assert command[4].endswith("requirements\\llm-rocm-windows.txt") or command[4].endswith(
        "requirements/llm-rocm-windows.txt"
    )


def test_auto_detects_metal_first(monkeypatch):
    monkeypatch.setattr(setup_llm.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(setup_llm.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(setup_llm, "_command_succeeds", lambda _command: True)
    monkeypatch.setattr(setup_llm, "_command_available", lambda _command: True)

    assert detect_local_profile() == "metal"


def test_auto_detects_cuda_before_vulkan(monkeypatch):
    monkeypatch.setattr(setup_llm.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup_llm.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(setup_llm, "_command_succeeds", lambda command: command == "nvidia-smi")
    monkeypatch.setattr(setup_llm, "_command_available", lambda _command: True)

    assert detect_local_profile() == "cuda"


def test_auto_detects_vulkan_before_cpu(monkeypatch):
    monkeypatch.setattr(setup_llm.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup_llm.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(setup_llm, "_command_succeeds", lambda _command: False)
    monkeypatch.setattr(setup_llm, "_command_available", lambda command: command == "vulkaninfo")

    assert detect_local_profile() == "vulkan"


def test_auto_falls_back_to_cpu(monkeypatch):
    monkeypatch.setattr(setup_llm.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup_llm.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(setup_llm, "_command_succeeds", lambda _command: False)
    monkeypatch.setattr(setup_llm, "_command_available", lambda _command: False)

    assert detect_local_profile() == "cpu"
