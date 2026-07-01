import argparse
import sys
from pathlib import Path
from typing import Callable, Sequence

from core.app import AuraNexusApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AuraNexus local launcher")
    parser.add_argument("--model-path", default=None, help="Path to the GGUF model file.")
    parser.add_argument("--config-path", default=None, help="Optional inference config path.")
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
    checks: list[tuple[str, bool, str]] = []

    model_path = Path(args.model_path) if args.model_path else None
    checks.append(
        (
            "sandbox_root",
            app.sandbox.base_path.exists(),
            str(app.sandbox.base_path),
        )
    )
    checks.append(
        (
            "bootstrap_manifest",
            app.bootstrap_path.exists(),
            str(app.bootstrap_path),
        )
    )
    checks.append(
        (
            "world_state",
            app.world_state.data_path.exists(),
            str(app.world_state.data_path),
        )
    )
    lore_path = app.lorebook.data_path
    checks.append(
        (
            "lorebook",
            lore_path is not None and lore_path.exists(),
            str(lore_path) if lore_path is not None else "unconfigured",
        )
    )
    checks.append(
        (
            "tool_registry_count",
            len(app.tool_registry.get_tool_schemas()) >= 1,
            str(len(app.tool_registry.get_tool_schemas())),
        )
    )
    checks.append(
        (
            "python3_allowlisted",
            "python3" in app.tool_registry.allowed_commands,
            "python3" if "python3" in app.tool_registry.allowed_commands else "missing",
        )
    )

    if model_path is None:
        checks.append(("model_path", False, "not provided"))
    else:
        checks.append(("model_path", model_path.exists(), str(model_path)))

    failed = 0
    for name, ok, detail in checks:
        status = "PASS" if ok else "WARN"
        if not ok:
            failed += 1
        output_fn(f"[{status}] {name}: {detail}")

    if failed == 0:
        output_fn("Doctor result: ready")
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
    output_fn(str(result))
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
        if command_requires_explicit_model_path(args.command) and not args.model_path:
            raise ValueError("--model-path is required for companion and story commands.")

        app = build_app(args)
        if command_requires_model_load(args.command):
            app.load_model()

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


if __name__ == "__main__":
    raise SystemExit(main())