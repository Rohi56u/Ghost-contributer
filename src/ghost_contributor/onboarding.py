"""Local, interactive onboarding using models that are already installed."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from . import gitops
from .config import RepoPolicy, save_config
from .errors import SafeStop
from .inference import Ollama


SAMPLE_SOURCE = '''def retry_delay(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    if attempt < 0 or base <= 0 or cap <= 0:
        raise ValueError("attempt must be nonnegative; base and cap must be positive")
    return min(base * (2 ** attempt), cap)
'''


def model_catalog(host: str = "http://127.0.0.1:11434") -> list[dict]:
    client = Ollama(RepoPolicy(name="model-list", path=str(Path.cwd()), host=host, timeout=15))
    result = []
    for model in client.models():
        details = model.get("details") if isinstance(model.get("details"), dict) else {}
        remote = bool(model.get("remote_host") or model.get("remote_model") or "cloud" in model["name"].lower())
        result.append({"name": model["name"], "size_bytes": model.get("size"),
                       "parameters": details.get("parameter_size", "unknown"),
                       "quantization": details.get("quantization_level", "unknown"),
                       "remote": remote, "digest": model.get("digest", "unknown")})
    return result


def pick_model(models: list[dict], ask=input, tell=print) -> str:
    candidates = [m for m in models if not m["remote"]]
    if not candidates:
        raise SafeStop("model_missing", "No installed local models were found. Check that this is the Ollama instance containing your models.")
    tell("\nYour installed local models (no download):")
    for i, model in enumerate(candidates, 1):
        size = model.get("size_bytes")
        size_text = f"{size / 1_000_000_000:.2f} GB download size" if isinstance(size, int) and size >= 0 else "size unknown"
        tell(f"  {i}. {model['name']}  |  {model['parameters']}  |  {size_text}")
    if len(candidates) != len(models):
        tell("Cloud/remote models were excluded from this local-only selection.")
    tell("Choose a coding/instruction text-generation model. Embedding-only models cannot draft text.")
    for _ in range(5):
        value = ask("Model number: ").strip()
        if value.isdecimal() and 1 <= int(value) <= len(candidates):
            return candidates[int(value) - 1]["name"]
        tell("Enter one of the model numbers shown above.")
    raise SafeStop("model_selection", "No valid model selected. Re-run setup when ready.")


def create_playground(state_root: Path) -> Path:
    root = state_root / "playgrounds" / ("sample-" + uuid.uuid4().hex[:8])
    root.mkdir(parents=True, mode=0o700)
    # Explicit bytes prevent Windows text-mode newline translation in this sample.
    (root / "retry.py").write_bytes(SAMPLE_SOURCE.encode("utf-8"))
    (root / ".gitattributes").write_bytes(b"* -text\n")
    gitops.git(root, "init", "-b", "main")
    gitops.git(root, "config", "core.autocrlf", "false")
    gitops.git(root, "add", "--", "retry.py", ".gitattributes")
    gitops.git(root, "-c", "user.name=Ghost Setup", "-c", "user.email=setup@localhost", "commit", "-m", "Add isolated sample for real local inference")
    return root


def setup(engine, host="http://127.0.0.1:11434", timezone="Asia/Kolkata", ask=input, tell=print) -> dict:
    tell("Ghost Contributor - real Ollama setup")
    tell("This reads installed models; it never downloads, deletes or rewrites your model files.")
    model = pick_model(model_catalog(host), ask, tell)
    tell("\nBefore inference, disable cloud features in the Ollama SERVER and restart it.")
    tell("Use OLLAMA_NO_CLOUD=1 or the server.json setting described in START-HERE-WINDOWS.md.")
    if ask("Have you restarted Ollama with cloud disabled? [y/N]: ").strip().lower() not in {"y", "yes"}:
        raise SafeStop("local_setup", "Finish Ollama local-only setup first, then rerun this wizard. No repository was registered.")
    selected = RepoPolicy(name="model-check", path=str(Path.cwd()), host=host, model=model, timeout=180, local_only_confirmed=True)
    identity = Ollama(selected).inspect()
    tell(f"Local model verified: {identity['tag']} (metadata check; generation will happen on your first run).")
    tell("\nPaste a clean local Git repository path, or press Enter to create a separate sample repository.")
    entered = ask("Repository path [Enter = isolated sample]: ").strip().strip('"')
    root = Path(entered).expanduser().resolve(strict=True) if entered else create_playground(engine.state.root)
    suggested = re.sub(r"[^A-Za-z0-9_-]", "-", root.name)[:64]
    name = ask(f"Repository name [{suggested}]: ").strip() or suggested
    policy = RepoPolicy(name=name, path=str(root), model=model, host=host,
                        base_branch=gitops.branch(root), timezone=timezone,
                        quiet_start="00:00", quiet_end="00:00", timeout=180,
                        mode="review", allow_push=False, local_only_confirmed=True).validate()
    gitops.preflight(policy)
    if engine.state.root.is_relative_to(root):
        raise SafeStop("state_location", "Choose a repository outside the Ghost state directory's ancestors.")
    with engine.state.lock():
        repos = engine.policies() if engine.config.exists() else []
        if any(p.path == policy.path or p.name == name for p in repos):
            raise SafeStop("registration", "Repository path or name is already registered. Open start-ghost.bat, or change its model using ghost policy REPO --model EXACT_NAME.")
        save_config(engine.config, [*repos, policy])
        engine.state.audit("registered", repo=name, policy=policy.fingerprint, source="setup_wizard", model=model)
    tell("\nSetup saved. Review mode is on; remote push is disabled.")
    tell("Quiet hours are disabled for your first test; daily schedule is 10:00 in " + timezone + ".")
    tell("Open the dashboard and click 'Find a small improvement' to call your selected real model.")
    return {"status": "ready_for_real_inference", "repo": name, "model": model,
            "path": str(root), "home": str(engine.state.root), "fixture": False,
            "next": f'ghost --home "{engine.state.root}" dashboard'}
