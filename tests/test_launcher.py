import argparse
import builtins

import launcher


def test_launcher_list_chat_sessions_command(monkeypatch) -> None:
    class _FakeApp:
        def load_model(self):
            return None

        class runtime:
            @staticmethod
            def list_chat_sessions():
                return [{"session_id": "chat_1", "name": "Primary", "created_at": "2026-06-30T00:00:00"}]

            @staticmethod
            def list_story_sessions():
                return []

    monkeypatch.setattr(launcher, "build_app", lambda args: _FakeApp())
    output = []
    monkeypatch.setattr(builtins, "print", lambda *args, **kwargs: output.append(" ".join(str(arg) for arg in args)))

    exit_code = launcher.main([
        "--model-path",
        "model.gguf",
        "--no-isolation",
        "list-chat-sessions",
    ])
    assert exit_code == 0
    assert any("chat_1" in line for line in output)


def test_launcher_doctor_command_without_model_path(monkeypatch) -> None:
    class _FakeApp:
        def __init__(self):
            self.sandbox = type("Sandbox", (), {"base_path": type("PathLike", (), {"exists": staticmethod(lambda: True)})()})()
            self.bootstrap_path = type("PathLike", (), {"exists": staticmethod(lambda: True), "__str__": lambda self: "bootstrap.json"})()
            self.world_state = type("World", (), {"data_path": type("PathLike", (), {"exists": staticmethod(lambda: True), "__str__": lambda self: "world.json"})()})()
            self.lorebook = type("Lore", (), {"data_path": type("PathLike", (), {"exists": staticmethod(lambda: True), "__str__": lambda self: "lorebook.json"})()})()
            self.tool_registry = type(
                "Registry",
                (),
                {
                    "allowed_commands": frozenset({"python3"}),
                    "get_tool_schemas": staticmethod(lambda: [{"function": {"name": "hf_text_task"}}]),
                },
            )()

        def load_model(self):
            return None

    app = _FakeApp()
    monkeypatch.setattr(
        launcher,
        "probe_hardware_profile",
        lambda: {
            "platform": "Linux-test",
            "cpu_logical_cores": 8,
            "ram_total_gb": 16.0,
            "llama_cpp_gpu_offload_support": False,
            "nvidia_devices": [],
            "recommended_profile": "cpu-fast",
        },
    )
    args = launcher.build_parser().parse_args([
        "--no-isolation",
        "doctor",
    ])
    output = []
    exit_code = launcher.run_doctor_command(
        app,
        args,
        output_fn=lambda message: output.append(message),
    )
    assert exit_code == 0
    assert any("model_path" in line for line in output)
    assert any("hardware_profile" in line for line in output)
    assert any("recommended_profile: cpu-fast" in line for line in output)
    assert any("ready with warnings" in line.lower() for line in output)


def test_launcher_doctor_warns_when_gpu_requested_without_backend(monkeypatch) -> None:
    class _FakeApp:
        def __init__(self):
            self.sandbox = type("Sandbox", (), {"base_path": type("PathLike", (), {"exists": staticmethod(lambda: True)})()})()
            self.bootstrap_path = type("PathLike", (), {"exists": staticmethod(lambda: True), "__str__": lambda self: "bootstrap.json"})()
            self.world_state = type("World", (), {"data_path": type("PathLike", (), {"exists": staticmethod(lambda: True), "__str__": lambda self: "world.json"})()})()
            self.lorebook = type("Lore", (), {"data_path": type("PathLike", (), {"exists": staticmethod(lambda: True), "__str__": lambda self: "lorebook.json"})()})()
            self.tool_registry = type(
                "Registry",
                (),
                {
                    "allowed_commands": frozenset({"python3"}),
                    "get_tool_schemas": staticmethod(lambda: [{"function": {"name": "hf_text_task"}}]),
                },
            )()

        def load_model(self):
            return None

    monkeypatch.setattr(
        launcher,
        "probe_hardware_profile",
        lambda: {
            "platform": "Linux-test",
            "cpu_logical_cores": 8,
            "ram_total_gb": 16.0,
            "llama_cpp_gpu_offload_support": False,
            "nvidia_devices": [{"name": "Test GPU", "memory": "8 GiB"}],
            "recommended_profile": "cpu-fast",
        },
    )

    app = _FakeApp()
    args = launcher.build_parser().parse_args([
        "--no-isolation",
        "--gpu-layers",
        "12",
        "doctor",
    ])

    output = []
    exit_code = launcher.run_doctor_command(app, args, output_fn=lambda message: output.append(message))
    assert exit_code == 0
    assert any("gpu_layers_requested_supported" in line for line in output)
    assert any("[WARN] gpu_layers_requested_supported" in line for line in output)


def test_launcher_companion_one_shot_command(monkeypatch) -> None:
    class _FakeApp:
        def __init__(self):
            self.last_restore_latest = None

        def load_model(self):
            return None

        def generate_companion_turn(self, user_input, session_name=None, restore_latest=True):
            self.last_restore_latest = restore_latest
            return type("Result", (), {"response": f"echo:{user_input}"})()

    app = _FakeApp()
    output = []
    args = launcher.build_parser().parse_args([
        "--model-path",
        "model.gguf",
        "--no-isolation",
        "companion",
        "--message",
        "hello",
    ])
    exit_code = launcher.run_companion_command(
        app,
        args,
        output_fn=lambda message: output.append(message),
    )
    assert exit_code == 0
    assert output[-1] == "echo:hello"
    assert app.last_restore_latest is False


def test_ensure_story_session_requires_story_metadata() -> None:
    args = argparse.Namespace(
        session_id=None,
        title=None,
        genre="Fantasy",
        tone="Dark",
        setting="Ruins",
        player_name="Mira",
        player_desc="",
    )

    try:
        launcher.ensure_story_session(object(), args)
    except ValueError as exc:
        assert "title" in str(exc)
    else:
        raise AssertionError("ensure_story_session should reject incomplete story metadata.")


def test_launcher_requires_model_for_companion_command(monkeypatch) -> None:
    output = []
    monkeypatch.setattr(builtins, "print", lambda *args, **kwargs: output.append(" ".join(str(arg) for arg in args)))

    exit_code = launcher.main([
        "--no-isolation",
        "companion",
        "--message",
        "hello",
    ])
    assert exit_code == 1


def test_install_and_run_demo_skill_commands(monkeypatch) -> None:
    class _FakeApp:
        def ensure_demo_skill(self):
            return {
                "skill_name": "demo_echo",
                "schema_path": "/tmp/demo_echo.schema.json",
                "script_path": "/tmp/echo_demo.py",
            }

        def run_demo_skill(self, text: str, timeout: int = 30):
            return {
                "success": True,
                "result": {
                    "success": True,
                    "returncode": 0,
                    "stdout": '{"skill":"demo_echo","received_text":"' + text + '","length":5}',
                    "stderr": "",
                    "error": "",
                },
            }

        def load_model(self):
            return None

    app = _FakeApp()
    install_args = launcher.build_parser().parse_args([
        "--no-isolation",
        "install-demo-skill",
    ])
    install_output = []
    install_exit = launcher.run_install_demo_skill_command(
        app,
        install_args,
        output_fn=lambda message: install_output.append(message),
    )
    assert install_exit == 0
    assert any("demo_echo" in line for line in install_output)

    run_args = launcher.build_parser().parse_args([
        "--no-isolation",
        "run-demo-skill",
        "--text",
        "hello",
    ])
    run_output = []
    run_exit = launcher.run_demo_skill_command(
        app,
        run_args,
        output_fn=lambda message: run_output.append(message),
    )
    assert run_exit == 0
    assert any("execution successful" in line for line in run_output)
    assert any("received_text: hello" in line for line in run_output)


def test_launcher_cpu_fast_applies_load_and_sampling_overrides(monkeypatch) -> None:
    class _FakeInferenceEngine:
        def __init__(self) -> None:
            self.override_calls = []
            self.response_length_modes = []

        def set_generation_overrides(self, **kwargs):
            self.override_calls.append(kwargs)

        def set_response_length_mode(self, mode):
            self.response_length_modes.append(mode)

    class _FakeApp:
        def __init__(self):
            self.inference_engine = _FakeInferenceEngine()
            self.load_calls = []

        def load_model(self, n_gpu_layers=None, ctx_size=None):
            self.load_calls.append({"n_gpu_layers": n_gpu_layers, "ctx_size": ctx_size})

        def generate_companion_turn(self, user_input, session_name=None, restore_latest=True):
            return type("Result", (), {"response": f"ok:{user_input}"})()

    fake_app = _FakeApp()
    monkeypatch.setattr(launcher, "build_app", lambda args: fake_app)

    exit_code = launcher.main([
        "--model-path",
        "model.gguf",
        "--no-isolation",
        "--cpu-fast",
        "companion",
        "--message",
        "hello",
    ])

    assert exit_code == 0
    assert fake_app.load_calls == [{"n_gpu_layers": 0, "ctx_size": 2048}]
    assert fake_app.inference_engine.override_calls[-1] == {"max_tokens": 160}
    assert fake_app.inference_engine.response_length_modes == ["normal"]


def test_launcher_manual_gpu_and_context_overrides(monkeypatch) -> None:
    class _FakeApp:
        def __init__(self):
            self.inference_engine = type(
                "Engine",
                (),
                {
                    "set_generation_overrides": staticmethod(lambda **kwargs: None),
                    "set_response_length_mode": staticmethod(lambda _mode: None),
                },
            )()
            self.load_calls = []

        def load_model(self, n_gpu_layers=None, ctx_size=None):
            self.load_calls.append({"n_gpu_layers": n_gpu_layers, "ctx_size": ctx_size})

        def generate_companion_turn(self, user_input, session_name=None, restore_latest=True):
            return type("Result", (), {"response": f"ok:{user_input}"})()

    fake_app = _FakeApp()
    monkeypatch.setattr(launcher, "build_app", lambda args: fake_app)

    exit_code = launcher.main([
        "--model-path",
        "model.gguf",
        "--no-isolation",
        "--gpu-layers",
        "12",
        "--ctx-size",
        "8192",
        "companion",
        "--message",
        "hello",
    ])

    assert exit_code == 0
    assert fake_app.load_calls == [{"n_gpu_layers": 12, "ctx_size": 8192}]


def test_launcher_applies_response_length_override(monkeypatch) -> None:
    class _FakeInferenceEngine:
        def __init__(self) -> None:
            self.response_length_modes = []

        def set_response_length_mode(self, mode):
            self.response_length_modes.append(mode)

        def set_generation_overrides(self, **_kwargs):
            return None

    class _FakeApp:
        def __init__(self):
            self.inference_engine = _FakeInferenceEngine()
            self.load_calls = []

        def load_model(self, n_gpu_layers=None, ctx_size=None):
            self.load_calls.append({"n_gpu_layers": n_gpu_layers, "ctx_size": ctx_size})

        def generate_companion_turn(self, user_input, session_name=None, restore_latest=True):
            return type("Result", (), {"response": f"ok:{user_input}"})()

    fake_app = _FakeApp()
    monkeypatch.setattr(launcher, "build_app", lambda args: fake_app)

    exit_code = launcher.main([
        "--model-path",
        "model.gguf",
        "--no-isolation",
        "--response-length",
        "long",
        "companion",
        "--message",
        "hello",
    ])

    assert exit_code == 0
    assert fake_app.inference_engine.response_length_modes == ["long"]