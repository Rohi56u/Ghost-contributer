from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from .config import RepoPolicy, digest, safe_path
from .errors import SafeStop


def git(root: Path, *args: str, timeout: int = 30, ok: tuple[int, ...] = (0,)) -> bytes:
    env = os.environ.copy()
    # Do not inherit index/worktree overrides or synthetic author timestamps.
    for key in list(env):
        if key.startswith("GIT_") and key not in {"GIT_SSH_COMMAND", "GIT_SSH", "GIT_ASKPASS"}:
            env.pop(key)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=root, env=env, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise SafeStop("git_timeout", "Git timed out; no automatic retry was attempted.") from exc
    except OSError as exc:
        raise SafeStop("git_unavailable", "Git is unavailable or the repository cannot be accessed.") from exc
    if result.returncode not in ok:
        # stderr can contain URLs, tokens or source from user hooks. Never persist it.
        raise SafeStop("git_failed", f"Git {args[0] if args else 'command'} failed; inspect locally with your Git client.")
    return result.stdout


def text(root: Path, *args: str, **kwargs) -> str:
    return git(root, *args, **kwargs).decode("utf-8", errors="strict").strip()


def branch(root: Path) -> str:
    return text(root, "symbolic-ref", "--quiet", "--short", "HEAD")


def head(root: Path) -> str:
    return text(root, "rev-parse", "HEAD")


def preflight(policy: RepoPolicy, expected: str | None = None) -> str:
    root = Path(policy.path)
    if text(root, "rev-parse", "--is-bare-repository") != "false":
        raise SafeStop("bare", "Bare repositories cannot be scanned.")
    if Path(text(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise SafeStop("repo_root", "Register the repository root, not a subdirectory.")
    try:
        current = branch(root)
    except SafeStop as exc:
        raise SafeStop("detached", "Detached HEAD is not supported.") from exc
    if current != policy.base_branch:
        raise SafeStop("branch_changed", "Switch to the registered base branch before running Ghost.")
    gitdir = Path(text(root, "rev-parse", "--absolute-git-dir"))
    for operation in ["MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-merge", "rebase-apply", "sequencer", "index.lock"]:
        if (gitdir / operation).exists():
            raise SafeStop("git_operation", "Finish the in-progress Git operation first.")
    if git(root, "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"):
        raise SafeStop("dirty_tree", "Repository has staged, unstaged or untracked changes; no source was changed.")
    flags = git(root, "ls-files", "-v", "-z").split(b"\0")
    if any(item and (item[:1].islower() or item[:1] == b"S") for item in flags):
        raise SafeStop("hidden_index", "Sparse checkout and assume-unchanged index flags are unsupported.")
    commit = head(root)
    if expected and commit != expected:
        raise SafeStop("stale", "Base revision changed; reject this proposal and generate a fresh one.")
    return commit


def tracked(root: Path) -> list[str]:
    result = []
    for record in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        mode, _, stage = metadata.split()
        if mode in {b"100644", b"100755"} and stage == b"0":
            result.append(path.decode("utf-8"))
    return sorted(result)


def read_tracked(root: Path, path: str, max_bytes: int) -> bytes:
    resolved = safe_path(root, path)
    if resolved.stat().st_size > max_bytes:
        raise SafeStop("file_limit", "File exceeds the configured size limit.")
    if git(root, "check-ignore", "--no-index", "--", path, ok=(0, 1)):
        raise SafeStop("ignored", "Ignored files are never sent to a model.")
    blob = git(root, "show", f"HEAD:{path}")
    if len(blob) > max_bytes or b"\0" in blob or resolved.read_bytes() != blob:
        raise SafeStop("unsupported_bytes", "File bytes differ from Git or are binary; normalize line endings/filters explicitly first.")
    return blob


def remote_identity(policy: RepoPolicy) -> str:
    root = Path(policy.path)
    urls = text(root, "remote", "get-url", "--push", "--all", policy.remote).splitlines()
    if len(urls) != 1:
        raise SafeStop("remote", "Exactly one push destination is required.")
    url = urls[0]
    fetch_urls = text(root, "remote", "get-url", "--all", policy.remote).splitlines()
    if fetch_urls != urls:
        raise SafeStop("split_remote", "Different fetch and push destinations are unsupported; reconciliation must inspect the exact push destination.")
    parsed = urlsplit(url)
    if parsed.password or (parsed.scheme in {"http", "https"} and parsed.username):
        raise SafeStop("credentials", "Use Git credential helpers; credentials in remote URLs are forbidden.")
    if "ext::" in url or "\n" in url:
        raise SafeStop("remote", "Unsupported remote transport.")
    return digest(url)


def validate_destination(policy: RepoPolicy, destination: str):
    if not destination.startswith("ghost/") or not destination.startswith(policy.branch_prefix) or destination == policy.base_branch:
        raise SafeStop("destination", "Only a dedicated ghost/ topic branch can be pushed.")
    git(Path(policy.path), "check-ref-format", "refs/heads/" + destination)
    advertised = text(Path(policy.path), "ls-remote", "--symref", policy.remote, "HEAD", timeout=60)
    if not any(row.startswith("ref: refs/heads/") and row.endswith("\tHEAD") for row in advertised.splitlines()):
        raise SafeStop("default_branch_unknown", "Remote default branch cannot be resolved. Initialize its base branch and inspect remote HEAD before publishing.")
    if f"ref: refs/heads/{destination}\tHEAD" in advertised:
        raise SafeStop("default_branch", "The destination is the remote default branch; push refused.")


def remote_sha(policy: RepoPolicy, destination: str) -> str | None:
    raw = text(Path(policy.path), "ls-remote", "--refs", policy.remote, f"refs/heads/{destination}", timeout=60)
    if not raw:
        return None
    rows = [row.split("\t") for row in raw.splitlines()]
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != f"refs/heads/{destination}":
        raise SafeStop("remote_unknown", "Remote ref lookup was ambiguous; inspect it manually.")
    return rows[0][0]


def push_exact(policy: RepoPolicy, sha: str, destination: str):
    if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        raise SafeStop("sha", "Invalid commit ID.")
    git(Path(policy.path), "push", "--porcelain", policy.remote, f"{sha}:refs/heads/{destination}", timeout=60)
