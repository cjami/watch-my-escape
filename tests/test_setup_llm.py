from watch_my_escape.setup_llm import build_command


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

    assert command == (
        "uv",
        "pip",
        "install",
        "--force-reinstall",
        "--no-cache-dir",
        "llama-cpp-python",
    )
    assert env["CMAKE_ARGS"] == "-DGGML_METAL=on"
