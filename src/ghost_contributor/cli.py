from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from . import __version__, gitops
from .config import RepoPolicy, save_config
from .engine import Engine
from .errors import SafeStop
from .inference import DemoModel, Ollama


def terminal(value):
    text = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)
    return "".join(c if c in "\n\t" or ord(c) >= 32 and ord(c) != 127 else "?" for c in text)


def parser():
    p = argparse.ArgumentParser(prog="ghost", description="Small documentation chores. Local models. Human review.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--home", type=Path, default=Path(os.environ.get("GHOST_HOME", "~/.ghost-contributor")).expanduser())
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create a private local state directory and empty policy.")
    models = sub.add_parser("models", help="List your existing Ollama models; never downloads a model.")
    models.add_argument("--host", default="http://127.0.0.1:11434")
    setup = sub.add_parser("setup", help="Choose an installed model and register a repository interactively.")
    setup.add_argument("--host", default="http://127.0.0.1:11434")
    setup.add_argument("--timezone", default="Asia/Kolkata")
    repo = sub.add_parser("repo").add_subparsers(dest="repo_action", required=True)
    add = repo.add_parser("add")
    add.add_argument("path", type=Path)
    add.add_argument("--name")
    add.add_argument("--model", default="qwen2.5-coder:1.5b")
    add.add_argument("--timezone", default="Asia/Kolkata")
    repo.add_parser("list")
    policy = sub.add_parser("policy", help="Explicit opt-ins; all initial repositories start in review mode.")
    policy.add_argument("repo")
    policy.add_argument("--mode", choices=["review", "auto_commit"])
    policy.add_argument("--allow-push", choices=["true", "false"])
    policy.add_argument("--local-only-confirmed", choices=["true", "false"])
    policy.add_argument("--model", help="Exact name returned by ghost models; does not download models.")
    policy.add_argument("--timeout", type=int, help="Local request timeout in seconds, from 1 to 300.")
    run = sub.add_parser("run")
    run.add_argument("--repo", required=True)
    run.add_argument("--once", action="store_true", help="Explicit one-pass flag; runs are always one pass.")
    run.add_argument("--dry-run", action="store_true", help="Save a review proposal; suppress any auto_commit policy.")
    for cmd in ["review", "reject", "publish"]:
        s = sub.add_parser(cmd)
        s.add_argument("id", nargs="?", default="latest")
    approve = sub.add_parser("approve", help="Approve the exact proposal and create a local topic-branch commit.")
    approve.add_argument("id", nargs="?", default="latest")
    approve.add_argument("--yes", action="store_true", help="Approve without the interactive confirmation prompt.")
    for cmd in ["status", "pause", "resume", "stop", "daemon", "audit"]:
        sub.add_parser(cmd)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--repo", required=True)
    dashboard = sub.add_parser("dashboard")
    dashboard.add_argument("--port", type=int, default=8765)
    demo = sub.add_parser("demo", help="Create a labelled sample proposal without Ollama; no network calls.")
    demo.add_argument("--directory", type=Path, default=Path.cwd() / "ghost-demo")
    return p


def create_demo(directory: Path):
    directory = directory.resolve()
    if directory.exists():
        raise SafeStop("demo_exists", "Demo directory already exists; choose a new --directory.")
    repository, state = directory / "sample-repo", directory / "state"
    repository.mkdir(parents=True)
    source = '''def retry_delay(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    if attempt < 0 or base <= 0 or cap <= 0:
        raise ValueError("attempt must be nonnegative; base and cap must be positive")
    return min(base * (2 ** attempt), cap)
'''
    (repository / "retry.py").write_text(source, encoding="utf-8")
    gitops.git(repository, "init", "-b", "main")
    gitops.git(repository, "config", "core.autocrlf", "false")
    gitops.git(repository, "add", "--", "retry.py")
    gitops.git(repository, "-c", "user.name=Ghost Demo", "-c", "user.email=demo@localhost", "commit", "-m", "Add sample retry helper")
    engine = Engine(state, model_factory=lambda _: DemoModel())
    policy = RepoPolicy(name="sample-repo", path=str(repository), quiet_start="00:00", quiet_end="00:00").validate()
    save_config(engine.config, [policy])
    proposal = engine.run("sample-repo", dry_run=True)
    return {"status": "demo_fixture_created", "proposal": proposal["id"], "home": str(state), "next": f'ghost --home "{state}" dashboard', "note": "Fixed demonstration fixture. No AI inference performed; push disabled."}


def execute(args):
    if args.command == "demo":
        return create_demo(args.directory)
    if args.command == "models":
        from .onboarding import model_catalog
        return model_catalog(args.host)
    engine = Engine(args.home)
    if args.command == "setup":
        if not sys.stdin.isatty():
            raise SafeStop("interactive_setup", "Run ghost setup in an interactive terminal, or use the documented manual commands.")
        from .onboarding import setup
        return setup(engine, host=args.host, timezone=args.timezone)
    if args.command == "init":
        if not engine.config.exists():
            save_config(engine.config, [])
        return {"status": "initialized", "policy": str(engine.config), "next": "ghost repo add /absolute/path/to/repository"}
    if args.command == "repo":
        repos = engine.policies()
        if args.repo_action == "list":
            return [{"name": r.name, "path": r.path, "mode": r.mode} for r in repos]
        root = args.path.expanduser().resolve(strict=True)
        name = args.name or re.sub(r"[^A-Za-z0-9_-]", "-", root.name)
        policy = RepoPolicy(name=name, path=str(root), base_branch=gitops.branch(root), model=args.model, timezone=args.timezone).validate()
        gitops.preflight(policy)
        if any(r.name == name or r.path == str(root) for r in repos) or engine.state.root.is_relative_to(root):
            raise SafeStop("registration", "Duplicate repository or state directory inside the repository.")
        with engine.state.lock():
            save_config(engine.config, [*repos, policy])
            engine.state.audit("registered", repo=name, policy=policy.fingerprint)
        return {"status": "registered", "repo": name, "mode": "review", "push": False, "next": "Disable cloud in the Ollama server, then confirm local-only setup in the policy."}
    if args.command == "policy":
        with engine.state.lock():
            repos = engine.policies()
            selected = next((r for r in repos if r.name == args.repo), None)
            if selected is None:
                raise SafeStop("repo_missing", "Unknown repository.")
            for field in ["mode", "allow_push", "local_only_confirmed", "model", "timeout"]:
                value = getattr(args, field)
                if value is not None:
                    setattr(selected, field, value == "true" if field in {"allow_push", "local_only_confirmed"} else value)
            selected.validate()
            save_config(engine.config, repos)
            engine.state.audit("policy_updated", repo=args.repo, policy=selected.fingerprint, mode=selected.mode, allow_push=selected.allow_push)
        return {"status": "policy_updated", "policy": str(engine.config)}
    if args.command == "run":
        p = engine.run(args.repo, dry_run=args.dry_run)
        return {k: v for k, v in p.items() if k not in {"before", "after", "target"}}
    if args.command == "review":
        p = engine.state.get(args.id)
        return f"{p['id']} | {p['status']} | {p['repo']}\nModel: {p['model']['tag']} {'[DEMO FIXTURE]' if p['fixture'] else ''}\n\n{p['response']['rationale']}\nUncertainty: {p['response']['uncertainty']}\n\n{p['diff']}\nApproval creates a local commit on {p['branch']}; your current branch stays unchanged.\n"
    if args.command == "approve":
        p = engine.state.get(args.id)
        if not args.yes:
            print(terminal(p["diff"]))
            if not sys.stdin.isatty() or input("Approve this exact diff and create a local topic-branch commit? [y/N] ").lower() != "y":
                return {"status": "approval_cancelled"}
        result = engine.approve(p["id"])
        return {"status": result["status"], "branch": result["branch"], "commit": result["commit_sha"]}
    if args.command == "reject":
        return {"status": engine.reject(args.id)["status"]}
    if args.command == "publish":
        p = engine.publish(args.id)
        return {"status": p["status"], "branch": p["branch"], "commit": p.get("commit_sha")}
    if args.command in {"pause", "resume", "stop"}:
        engine.state.set_flag("paused", args.command != "resume")
        if args.command in {"stop", "resume"}:
            engine.state.set_flag("killed", args.command == "stop")
        return {"status": args.command}
    if args.command == "doctor":
        policy = engine.policy(args.repo)
        base = gitops.preflight(policy)
        return {"git": "clean", "base": base, "model": Ollama(policy).inspect(), "policy": policy.fingerprint}
    if args.command == "audit":
        return {"status": "verified", "events": engine.state.verify_audit(), "note": "Local hash chain; not proof against an attacker who controls this machine."}
    if args.command == "status":
        return engine.status()
    if args.command == "daemon":
        from .scheduler import serve
        return serve(engine)
    if args.command == "dashboard":
        from .dashboard import serve
        return serve(engine, args.port)


def main():
    try:
        result = execute(parser().parse_args())
        if result is not None:
            print(terminal(result))
    except SafeStop as exc:
        print(f"Safe stop [{exc.code}]: {terminal(str(exc))}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Stopped. Existing proposals and audit records remain available.", file=sys.stderr)
        return 130
    except EOFError:
        print("Setup input ended. Re-run setup in a terminal when ready.", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"Local setup error ({type(exc).__name__}). Check paths, permissions and configuration.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
