import argparse
import sys
from pathlib import Path
from typing import Callable, Sequence

from core.app import AuraNexusApp
from core.hardware import probe_hardware_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AuraNexus local launcher")
    parser.add_argument("--model-path", default=None, help="Path to the GGUF model file.")
    parser.add_argument("--config-path", default=None, help="Optional inference config path.")
    parser.add_argument(
        "--cpu-fast",
        action="store_true",
        help="CPU-optimized profile: lower context/token defaults for faster local turnaround.",
    )
    parser.add_argument(
        "--gpu-layers",
        type=int,
        default=None,
        help="Override llama.cpp n_gpu_layers. Use 0 for CPU-only or -1 for full offload attempt.",
    )
    parser.add_argument(
        "--ctx-size",
        type=int,
        default=None,
        help="Override llama.cpp context size (n_ctx).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Override generation max_tokens for all turns in this process.",
    )
    parser.add_argument(
        "--response-length",
        choices=("short", "normal", "long"),
        default="normal",
        help="Select the default response-length preset.",
    )
    parser.add_argument("--workspace-dir", default="sandbox_workspace", help="Sandbox workspace root.")
    parser.add_argument("--aura-name", default="Aura", help="Assistant display name.")
    parser.add_argument("--user-name", default="User", help="User display name.")
    parser.add_argument(
        "--allow-command",
        action="append",
        default=None,
        help="Bare binary name allowed for sandbox command execution. Repeat to add more than one.",
    )
    parser.add_argument(
        "--no-isolation",
        action="store_true",
        help="Disable hard isolation checks. Intended only for controlled local debugging.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    companion = subparsers.add_parser("companion", help="Run companion mode.")
    companion.add_argument("--message", default=None, help="One-shot companion input.")
    companion.add_argument("--session-name", default=None, help="Optional companion session name.")
    companion.add_argument(
        "--no-restore-latest",
        action="store_true",
        help="Start a fresh companion session instead of reusing the latest saved session.",
    )

    story = subparsers.add_parser("story", help="Run storyteller mode.")
    story.add_argument("--message", default=None, help="One-shot story input.")
    story.add_argument("--session-id", default=None, help="Existing story session ID to resume.")
    story.add_argument("--title", default=None, help="Story title when starting a new session.")
    story.add_argument("--genre", default=None, help="Story genre when starting a new session.")
    story.add_argument("--tone", default=None, help="Story tone when starting a new session.")
    story.add_argument("--setting", default=None, help="Story setting when starting a new session.")
    story.add_argument("--player-name", default=None, help="Player character name when starting a new session.")
    story.add_argument("--player-desc", default="", help="Optional player character description.")

    subparsers.add_parser("list-chat-sessions", help="List persisted companion sessions.")
    subparsers.add_parser("list-story-sessions", help="List persisted story sessions.")
    subparsers.add_parser("doctor", help="Run local readiness checks without generating text.")
    install_demo = subparsers.add_parser("install-demo-skill", help="Install a safe demo OpenClaw skill.")
    install_demo.add_argument("--replace", action="store_true", help="Reserved compatibility flag.")
    run_demo = subparsers.add_parser("run-demo-skill", help="Execute the installed demo skill.")
    run_demo.add_argument("--text", required=True, help="Input text to pass to the demo skill.")
    run_demo.add_argument("--timeout", type=int, default=30, help="Execution timeout in seconds.")

    serve = subparsers.add_parser("serve", help="Start the AuraNexus web server and browser UI.")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    serve.add_argument("--port", type=int, default=7860, help="Bind port (default: 7860).")
    serve.add_argument("--open", action="store_true", help="Open the browser automatically on start.")
    # These mirror the global flags so they can be passed after 'serve' naturally.
    serve.add_argument("--model-path", default=None, dest="serve_model_path",
                       help="Path to the GGUF model file.")
    serve.add_argument("--gpu-layers", type=int, default=None, dest="serve_gpu_layers",
                       help="Override llama.cpp n_gpu_layers.")
    serve.add_argument("--ctx-size", type=int, default=None, dest="serve_ctx_size",
                       help="Override llama.cpp context size.")
    serve.add_argument("--max-tokens", type=int, default=None, dest="serve_max_tokens",
                       help="Override generation max_tokens.")
    serve.add_argument("--response-length", choices=("short", "normal", "long"), default=None,
                       dest="serve_response_length", help="Override the response-length preset.")
    serve.add_argument("--cpu-fast", action="store_true", dest="serve_cpu_fast",
                       help="CPU-optimised profile (lower ctx/tokens, no GPU offload).")
    return parser


def build_app(args: argparse.Namespace) -> AuraNexusApp:
    model_path = args.model_path
    if not model_path:
        model_path = str(Path(args.workspace_dir) / "models" / "placeholder.gguf")

    return AuraNexusApp(
        model_path=model_path,
        config_path=args.config_path,
        workspace_dir=args.workspace_dir,
        aura_name=args.aura_name,
        user_name=args.user_name,
        allowed_commands=args.allow_command,
        require_isolation=not args.no_isolation,
    )


def run_serve_command(
    args: argparse.Namespace,
    *,
    output_fn: Callable[[str], None] = print,
) -> int:
    """Launch the FastAPI web server with the full browser UI."""
    import importlib
    try:
        server_mod = importlib.import_module("server")
    except ImportError as exc:
        output_fn(f"[FAIL] Cannot import server module: {exc}")
        output_fn("  Make sure fastapi and uvicorn are installed: pip install fastapi 'uvicorn[standard]'")
        return 1

    # Subcommand-local flags override global flags so that
    # `launcher.py serve --model-path X` works without needing
    # the flag before the subcommand name.
    effective_model_path = getattr(args, "serve_model_path", None) or args.model_path
    effective_gpu_layers = getattr(args, "serve_gpu_layers", None)
    if effective_gpu_layers is None:
        effective_gpu_layers = args.gpu_layers
    effective_ctx_size = getattr(args, "serve_ctx_size", None)
    if effective_ctx_size is None:
        effective_ctx_size = args.ctx_size
    effective_max_tokens = getattr(args, "serve_max_tokens", None)
    if effective_max_tokens is None:
        effective_max_tokens = args.max_tokens
    effective_response_length = getattr(args, "serve_response_length", None) or args.response_length
    effective_cpu_fast = getattr(args, "serve_cpu_fast", False) or args.cpu_fast

    resolved_gpu_layers = effective_gpu_layers
    resolved_ctx_size = effective_ctx_size
    resolved_max_tokens = effective_max_tokens
    if effective_cpu_fast:
        if resolved_gpu_layers is None:
            resolved_gpu_layers = 0
        if resolved_ctx_size is None:
            resolved_ctx_size = 2048
        if resolved_max_tokens is None:
            resolved_max_tokens = 160

    if args.open:
        import threading, webbrowser, time
        def _open_browser():
            time.sleep(1.8)
            webbrowser.open(f"http://{args.host}:{args.port}")
        threading.Thread(target=_open_browser, daemon=True).start()

    output_fn(f"[AuraNexus] Starting web server at http://{args.host}:{args.port}")
    if not effective_model_path:
        output_fn("[WARN] No --model-path provided. Inference will be unavailable. UI and memory features will work.")

    server_mod.start_server(
        host=args.host,
        port=args.port,
        model=effective_model_path,
        workspace=args.workspace_dir,
        aura_name=args.aura_name,
        user_name=args.user_name,
        gpu_layers=resolved_gpu_layers,
        ctx_size=resolved_ctx_size,
        max_tokens=resolved_max_tokens,
        response_length=effective_response_length,
        cpu_fast=effective_cpu_fast,
    )
    return 0


def command_requires_model_load(command: str) -> bool:
    return command in {"companion", "story"}


def command_requires_explicit_model_path(command: str) -> bool:
    return command in {"companion", "story"}


def print_session_listing(items: list[dict[str, str]], primary_field: str, output_fn: Callable[[str], None]) -> None:
    if not items:
        output_fn("No sessions found.")
        return

    for item in items:
        output_fn(f"{item['session_id']} | {item[primary_field]} | {item['created_at']}")


def run_doctor_command(
    app: AuraNexusApp,
    args: argparse.Namespace,
    *,
    output_fn: Callable[[str], None] = print,
) -> int:
    checks: list[tuple[str, str, bool, str]] = []
    hardware = probe_hardware_profile()

    model_path = Path(args.model_path) if args.model_path else None
    checks.append(
        (
            "fail",
            "sandbox_root",
            app.sandbox.base_path.exists(),
            str(app.sandbox.base_path),
        )
    )
    checks.append(
        (
            "fail",
            "bootstrap_manifest",
            app.bootstrap_path.exists(),
            str(app.bootstrap_path),
        )
    )
    checks.append(
        (
            "fail",
            "world_state",
            app.world_state.data_path.exists(),
            str(app.world_state.data_path),
        )
    )
    lore_path = app.lorebook.data_path
    checks.append(
        (
            "fail",
            "lorebook",
            lore_path is not None and lore_path.exists(),
            str(lore_path) if lore_path is not None else "unconfigured",
        )
    )
    checks.append(
        (
            "fail",
            "tool_registry_count",
            len(app.tool_registry.get_tool_schemas()) >= 1,
            str(len(app.tool_registry.get_tool_schemas())),
        )
    )
    checks.append(
        (
            "fail",
            "python3_allowlisted",
            "python3" in app.tool_registry.allowed_commands,
            "python3" if "python3" in app.tool_registry.allowed_commands else "missing",
        )
    )

    if model_path is None:
        checks.append(("warn", "model_path", False, "not provided"))
    else:
        checks.append(("warn", "model_path", model_path.exists(), str(model_path)))

    gpu_support = hardware.get("llama_cpp_gpu_offload_support")
    checks.append(
        (
            "warn",
            "llama_cpp_gpu_offload_support",
            gpu_support is True,
            str(gpu_support),
        )
    )
    if args.gpu_layers is not None and args.gpu_layers > 0:
        checks.append(
            (
                "warn",
                "gpu_layers_requested_supported",
                gpu_support is True,
                f"requested={args.gpu_layers}, supported={gpu_support}",
            )
        )

    failed = 0
    warnings = 0
    for severity, name, ok, detail in checks:
        status = "PASS" if ok else "WARN"
        if not ok:
            if severity == "fail":
                failed += 1
                status = "FAIL"
            else:
                warnings += 1
                status = "WARN"
        output_fn(f"[{status}] {name}: {detail}")

    detected_gpus = hardware.get("nvidia_devices") or []
    output_fn(
        "[INFO] hardware_profile: "
        f"platform={hardware.get('platform')}, "
        f"cpu={hardware.get('cpu_logical_cores')} threads, "
        f"ram={hardware.get('ram_total_gb')}GB, "
        f"detected_gpus={len(detected_gpus)}"
    )
    if detected_gpus:
        for index, device in enumerate(detected_gpus, start=1):
            output_fn(
                f"[INFO] gpu_{index}: {device.get('name', 'unknown')} "
                f"({device.get('memory', 'unknown')})"
            )
    output_fn(f"[INFO] recommended_profile: {hardware.get('recommended_profile')}")
    if hardware.get("recommended_profile") == "cpu-fast":
        output_fn("[INFO] recommendation: use --cpu-fast (or --gpu-layers 0) for stable local performance.")
    elif hardware.get("recommended_profile") == "gpu":
        output_fn("[INFO] recommendation: start with --gpu-layers 10 and increase gradually while monitoring VRAM.")

    if failed == 0 and warnings == 0:
        output_fn("Doctor result: ready")
        return 0

    if failed == 0:
        output_fn("Doctor result: ready with warnings")
        return 0

    output_fn("Doctor result: attention needed")
    return 1


def run_install_demo_skill_command(
    app: AuraNexusApp,
    args: argparse.Namespace,
    *,
    output_fn: Callable[[str], None] = print,
) -> int:
    details = app.ensure_demo_skill()
    output_fn(f"Installed demo skill: {details['skill_name']}")
    output_fn(f"Schema: {details['schema_path']}")
    output_fn(f"Script: {details['script_path']}")
    return 0


def run_demo_skill_command(
    app: AuraNexusApp,
    args: argparse.Namespace,
    *,
    output_fn: Callable[[str], None] = print,
) -> int:
    result = app.run_demo_skill(text=args.text, timeout=max(1, int(args.timeout)))
    if not isinstance(result, dict):
        output_fn("[FAIL] demo_skill: unexpected result format")
        output_fn(str(result))
        return 1

    if not result.get("success", False):
        output_fn("[FAIL] demo_skill: router execution failed")
        output_fn(str(result))
        return 1

    inner = result.get("result", {})
    if not isinstance(inner, dict) or not inner.get("success", False):
        output_fn("[FAIL] demo_skill: sandbox command failed")
        output_fn(str(result))
        return 1

    stdout_raw = str(inner.get("stdout", "")).strip()
    parsed = None
    if stdout_raw:
        try:
            import json

            parsed = json.loads(stdout_raw)
        except Exception:
            parsed = None

    output_fn("[PASS] demo_skill: execution successful")
    if isinstance(parsed, dict):
        skill_name = str(parsed.get("skill", "demo_echo"))
        received_text = str(parsed.get("received_text", ""))
        length_value = parsed.get("length", "")
        output_fn(f"skill: {skill_name}")
        output_fn(f"received_text: {received_text}")
        output_fn(f"length: {length_value}")
    else:
        output_fn(f"stdout: {stdout_raw}")

    return 0


def run_companion_command(
    app: AuraNexusApp,
    args: argparse.Namespace,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> int:
    restore_latest = not args.no_restore_latest
    if args.message is not None:
        # One-shot invocations should be deterministic and avoid inheriting old chat transcripts.
        if args.session_name is None and not args.no_restore_latest:
            restore_latest = False
        result = app.generate_companion_turn(
            args.message,
            session_name=args.session_name,
            restore_latest=restore_latest,
        )
        output_fn(result.response)
        return 0

    output_fn("Companion mode. Type /exit to quit.")
    while True:
        user_input = input_fn(f"{args.user_name}> ").strip()
        if user_input in {"/exit", "/quit"}:
            return 0
        if not user_input:
            continue
        result = app.generate_companion_turn(
            user_input,
            session_name=args.session_name,
            restore_latest=restore_latest,
        )
        output_fn(result.response)


def ensure_story_session(app: AuraNexusApp, args: argparse.Namespace) -> None:
    if args.session_id:
        app.runtime.load_story_session(args.session_id)
        return

    required = {
        "title": args.title,
        "genre": args.genre,
        "tone": args.tone,
        "setting": args.setting,
        "player_name": args.player_name,
    }
    missing = [field for field, value in required.items() if not value]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(
            f"Starting a new story requires: {missing_text}. Provide them or use --session-id to resume."
        )

    app.start_story(
        title=args.title,
        genre=args.genre,
        tone=args.tone,
        setting=args.setting,
        player_name=args.player_name,
        player_desc=args.player_desc,
    )


def run_story_command(
    app: AuraNexusApp,
    args: argparse.Namespace,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> int:
    ensure_story_session(app, args)

    if args.message is not None:
        result = app.generate_story_turn(args.message)
        output_fn(result.response)
        return 0

    output_fn("Storyteller mode. Type /exit to quit.")
    while True:
        user_input = input_fn(f"{args.user_name}> ").strip()
        if user_input in {"/exit", "/quit"}:
            return 0
        if not user_input:
            continue
        result = app.generate_story_turn(user_input)
        output_fn(result.response)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "serve":
            return run_serve_command(args)

        if command_requires_explicit_model_path(args.command) and not args.model_path:
            raise ValueError("--model-path is required for companion and story commands.")

        app = build_app(args)
        if command_requires_model_load(args.command):
            resolved_gpu_layers = args.gpu_layers
            resolved_ctx_size = args.ctx_size
            if args.cpu_fast:
                if resolved_gpu_layers is None:
                    resolved_gpu_layers = 0
                if resolved_ctx_size is None:
                    resolved_ctx_size = 2048

            has_model_overrides = (
                args.cpu_fast
                or args.gpu_layers is not None
                or args.ctx_size is not None
            )
            if has_model_overrides:
                app.load_model(n_gpu_layers=resolved_gpu_layers, ctx_size=resolved_ctx_size)
            else:
                app.load_model()

            if args.cpu_fast and hasattr(app, "inference_engine"):
                app.inference_engine.set_generation_overrides(max_tokens=160)
            if hasattr(app, "inference_engine") and hasattr(app.inference_engine, "set_response_length_mode"):
                app.inference_engine.set_response_length_mode(args.response_length)
            if args.max_tokens is not None and hasattr(app, "inference_engine"):
                app.inference_engine.set_generation_overrides(max_tokens=args.max_tokens)

        if args.command == "companion":
            return run_companion_command(app, args)
        if args.command == "story":
            return run_story_command(app, args)
        if args.command == "list-chat-sessions":
            print_session_listing(app.runtime.list_chat_sessions(), "name", print)
            return 0
        if args.command == "list-story-sessions":
            print_session_listing(app.runtime.list_story_sessions(), "title", print)
            return 0
        if args.command == "doctor":
            return run_doctor_command(app, args)
        if args.command == "install-demo-skill":
            return run_install_demo_skill_command(app, args)
        if args.command == "run-demo-skill":
            return run_demo_skill_command(app, args)
    except Exception as exc:
        print(f"AuraNexus launcher error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


def main_serve_shortcut(argv: Sequence[str] | None = None) -> int:
    """Direct entry-point for 'serve' without requiring a subcommand prefix."""
    parser = build_parser()
    args = parser.parse_args(["serve"] + list(argv or []))
    return run_serve_command(args)


if __name__ == "__main__":
    raise SystemExit(main())