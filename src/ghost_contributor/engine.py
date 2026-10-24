from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path

from . import gitops
from .config import RepoPolicy, allowed, digest, load_config, safe_path
from .editing import Target, diff, select, transform
from .errors import SafeStop
from .inference import DemoModel, Ollama, validate_output
from .scheduler import quiet
from .state import State, atomic_write, process_lock


class Engine:
    def __init__(self, home: Path, model_factory=None):
        self.state = State(home)
        self.config = self.state.root / "policy.toml"
        self.model_factory = model_factory or Ollama

    def policies(self) -> list[RepoPolicy]:
        return load_config(self.config)

    def policy(self, name: str) -> RepoPolicy:
        for p in self.policies():
            if p.name == name:
                if self.state.root.is_relative_to(Path(p.path)):
                    raise SafeStop("state_location", "Ghost state must be outside the registered repository.")
                return p
        raise SafeStop("repo_missing", "Repository is not registered.")

    def repo_lock(self, policy: RepoPolicy):
        common = gitops.text(Path(policy.path), "rev-parse", "--path-format=absolute", "--git-common-dir")
        return process_lock(Path.home() / ".ghost-contributor-locks" / (digest(common) + ".lock"))

    def run(self, name: str, task_period: str | None = None, dry_run: bool = False) -> dict:
        policy = self.policy(name)
        with self.state.lock(), self.repo_lock(policy):
            self.state.guard()
            if quiet(policy):
                return {"status": "quiet_hours", "repo": name}
            if self.state.has_pending(name):
                return {"status": "pending_exists", "repo": name}
            run_id = uuid.uuid4().hex[:16]
            key = task_period or "manual:" + run_id
            if not self.state.reserve_run(run_id, name, key):
                return {"status": "already_ran", "repo": name}
            try:
                base = gitops.preflight(policy)
                selected = select(policy, self.state.handled_targets(name, base))
                if not selected:
                    self.state.finish_run(run_id, "noop", "no_supported_gap")
                    return {"status": "noop", "repo": name}
                target, before = selected
                provider = self.model_factory(policy)
                response = validate_output(provider.generate(target), target)
                after = transform(before, target, response["replacement_text"])
                if after == before:
                    self.state.finish_run(run_id, "noop", "unchanged")
                    return {"status": "noop", "repo": name}
                if transform(after, target, response["replacement_text"]) != after:
                    raise SafeStop("idempotence", "Repeated transformation changed the candidate.")
                self.state.guard()
                gitops.preflight(policy, base)
                validations = ["target_allowlist", "exact_source_snapshot", "structured_schema", "evidence_quotes_match", "syntax_and_span", "idempotence"]
                if policy.checks:
                    self.validate_in_worktree(policy, base, target.path, before, after)
                    validations.append("configured_checks")
                patch = diff(before, after, target.path)
                p = {"id": run_id, "repo": name, "base_sha": base, "policy_hash": policy.fingerprint,
                     "target": target.to_dict(), "response": response, "model": provider.identity,
                     "fixture": provider.fixture, "diff": patch, "diff_digest": digest(patch),
                     "before": base64.b64encode(before).decode(), "after": base64.b64encode(after).decode(),
                     "validations": validations, "branch": policy.branch_prefix.rstrip("/") + "/" + run_id}
                p["review_digest"] = digest(base + policy.fingerprint + digest(after))
                self.state.put(p)
                self.state.audit("proposal_created", id=run_id, repo=name, policy=policy.fingerprint, path=target.path,
                                 base=base, diff_digest=p["diff_digest"], model=provider.identity, validations=validations, fixture=p["fixture"])
                self.state.finish_run(run_id, "pending", "awaiting_review")
            except SafeStop as exc:
                self.state.finish_run(run_id, "blocked", exc.code)
                raise
            except Exception as exc:
                self.state.finish_run(run_id, "blocked", "unexpected_error")
                raise SafeStop("unexpected_error", "Unexpected error; source was not published. Inspect with a local debugger.") from exc
        if policy.mode == "auto_commit" and not dry_run and response["uncertainty"].strip().lower() == "none" and not p["fixture"] and not quiet(policy):
            return self.approve(run_id, actor="policy:auto_commit")
        return self.state.get(run_id)

    def check_snapshot(self, policy: RepoPolicy, p: dict) -> tuple[bytes, bytes]:
        if p["policy_hash"] != policy.fingerprint:
            raise SafeStop("policy_changed", "Policy changed after generation. Reject and generate a fresh proposal.")
        gitops.preflight(policy, p["base_sha"])
        target = Target(**p["target"])
        if not allowed(target.path, policy.include, policy.exclude):
            raise SafeStop("scope", "Target is no longer allowed.")
        before, after = base64.b64decode(p["before"], validate=True), base64.b64decode(p["after"], validate=True)
        current = gitops.read_tracked(Path(policy.path), target.path, policy.max_file_bytes)
        if current != before or transform(before, target, p["response"]["replacement_text"]) != after:
            raise SafeStop("stale", "Reviewed source or candidate changed; regenerate the proposal.")
        if digest(p["base_sha"] + policy.fingerprint + digest(after)) != p["review_digest"] or digest(diff(before, after, target.path)) != p["diff_digest"]:
            raise SafeStop("digest", "Review digest does not match the candidate.")
        return before, after

    def workspace(self, policy: RepoPolicy, base: str, identifier: str, branch: str | None = None) -> Path:
        location = self.state.root / "worktrees" / identifier
        location.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        args = ["worktree", "add", "-b", branch, str(location), base] if branch else ["worktree", "add", "--detach", str(location), base]
        gitops.git(Path(policy.path), *args)
        return location

    def install_candidate(self, location: Path, target: str, before: bytes, after: bytes):
        file = safe_path(location, target)
        if file.read_bytes() != before:
            raise SafeStop("checkout_filter", "Worktree checkout changed source bytes; inspect Git filters or line-ending settings.")
        atomic_write(file, after, mode=file.stat().st_mode & 0o777)

    def run_checks(self, policy: RepoPolicy, location: Path, target: str, candidate: bytes):
        for command in policy.checks:
            self.state.guard()
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            with tempfile.TemporaryFile() as output:
                try:
                    proc = subprocess.Popen(command, cwd=location, env=env, stdout=output, stderr=output, start_new_session=os.name != "nt")
                    proc.wait(timeout=policy.check_timeout)
                except subprocess.TimeoutExpired as exc:
                    if os.name != "nt":
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                    proc.wait()
                    raise SafeStop("check_timeout", "Configured check timed out; candidate not committed.") from exc
                except OSError as exc:
                    raise SafeStop("check_missing", "Configured check executable was unavailable.") from exc
                if proc.returncode:
                    raise SafeStop("check_failed", "A configured check failed. Output is not logged because it can contain source or secrets.")
        if safe_path(location, target).read_bytes() != candidate:
            raise SafeStop("check_modified", "A configured check changed the approved bytes.")
        names = gitops.git(location, "diff", "--name-only", "-z").split(b"\0")
        if [n for n in names if n] != [target.encode()] or gitops.git(location, "diff", "--cached", "--name-only") or gitops.git(location, "ls-files", "--others", "--exclude-standard"):
            raise SafeStop("check_modified", "Unexpected file changes appeared in the isolated worktree.")

    def validate_in_worktree(self, policy, base, target, before, after):
        location = self.workspace(policy, base, "validate-" + uuid.uuid4().hex[:12])
        try:
            self.install_candidate(location, target, before, after)
            self.run_checks(policy, location, target, after)
        finally:
            # Force only deletes this disposable validation worktree, never pushes or branches.
            gitops.git(Path(policy.path), "worktree", "remove", "--force", str(location))

    def approve(self, proposal_id: str, actor: str = "cli") -> dict:
        with self.state.lock():
            self.state.guard()
            p = self.state.get(proposal_id)
            if p["status"] != "pending":
                raise SafeStop("state", "Only a pending proposal can be approved once.")
            policy = self.policy(p["repo"])
            with self.repo_lock(policy):
                before, after = self.check_snapshot(policy, p)
                if actor == "policy:auto_commit" and (policy.mode != "auto_commit" or p["fixture"] or p["response"]["uncertainty"].lower().strip() != "none"):
                    raise SafeStop("approval", "Unattended local commit is not permitted for this proposal.")
                self.state.audit("approved", id=p["id"], actor=actor, review_digest=p["review_digest"])
                location = self.state.root / "worktrees" / p["id"]
                self.state.update(p["id"], "committing", worktree=str(location))
                try:
                    location = self.workspace(policy, p["base_sha"], p["id"], p["branch"])
                    self.install_candidate(location, p["target"]["path"], before, after)
                    self.run_checks(policy, location, p["target"]["path"], after)
                    self.state.guard()
                    gitops.preflight(policy, p["base_sha"])
                    target = p["target"]["path"]
                    gitops.git(location, "add", "--", target)
                    if gitops.git(location, "diff", "--cached", "--name-only", "-z") != target.encode() + b"\0" or gitops.git(location, "show", f":{target}") != after:
                        raise SafeStop("index", "Staged content did not match the exact approved file.")
                    self.state.guard()
                    message = f"docs: document {p['target']['symbol']} (AI-assisted)\n\nGenerated with Ghost Contributor using {p['model']['tag']}.\nReviewed-by: {actor}\nGhost-Proposal: {p['id']}\nGhost-Review-Digest: {p['review_digest']}"
                    gitops.git(location, "-c", "user.name=Ghost Contributor", "-c", "user.email=ghost-contributor@localhost", "commit", "-m", message)
                    sha = gitops.head(location)
                    changed = gitops.git(location, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", sha)
                    if changed != target.encode() + b"\0" or gitops.git(location, "show", f"{sha}:{target}") != after or gitops.text(location, "rev-parse", "HEAD^") != p["base_sha"]:
                        raise SafeStop("hook_mutation", "A Git hook changed the commit; it was retained for inspection and will not be published.")
                    self.state.update(p["id"], "committed", commit_sha=sha, actor=actor)
                    self.state.audit("committed", id=p["id"], sha=sha, target_ref=p["branch"], actor=actor, diff_digest=p["diff_digest"])
                    # Do not discard modifications made by post-commit hooks.
                    if not gitops.git(location, "status", "--porcelain=v1", "--untracked-files=all"):
                        gitops.git(Path(policy.path), "worktree", "remove", str(location))
                except SafeStop as exc:
                    # A commit may exist after a hook/time-out failure; never blindly retry.
                    self.state.update(p["id"], "commit_failed", failure=exc.code)
                    self.state.audit("commit_stopped", id=p["id"], reason=exc.code)
                    raise
        return self.state.get(p["id"])

    def reject(self, proposal_id: str) -> dict:
        with self.state.lock():
            p = self.state.get(proposal_id)
            if p["status"] != "pending":
                raise SafeStop("state", "Only a pending proposal can be rejected.")
            self.state.update(p["id"], "rejected")
            self.state.audit("rejected", id=p["id"], actor="local_user")
            return self.state.get(p["id"])

    def publish(self, proposal_id: str) -> dict:
        with self.state.lock():
            self.state.guard()
            p = self.state.get(proposal_id)
            policy = self.policy(p["repo"])
            if not policy.allow_push or p["fixture"]:
                raise SafeStop("push_disabled", "Push requires allow_push=true; demo fixtures cannot be pushed.")
            if p["status"] not in {"committed", "push_unknown", "push_failed", "pushed"}:
                raise SafeStop("state", "Only a verified local commit can be pushed.")
            with self.repo_lock(policy):
                # No write to the developer's tree, but refuse ambiguous Git operations.
                gitops.preflight(policy)
                remote = gitops.remote_identity(policy)
                if p.get("remote_identity") and p["remote_identity"] != remote:
                    raise SafeStop("remote_changed", "Push destination changed; inspect the original remote before recovery.")
                destination, sha = p["branch"], p["commit_sha"]
                gitops.validate_destination(policy, destination)
                if gitops.text(Path(policy.path), "rev-parse", f"refs/heads/{destination}") != sha:
                    raise SafeStop("branch_moved", "Automation branch changed after review; push refused.")
                observed = gitops.remote_sha(policy, destination)
                if observed == sha:
                    self.state.update(p["id"], "pushed", remote_identity=remote)
                    self.state.audit("push_reconciled", id=p["id"], sha=sha, result="confirmed")
                    return self.state.get(p["id"])
                if observed is not None:
                    raise SafeStop("remote_conflict", "Remote topic branch has a different commit; no overwrite attempted.")
                self.state.guard()
                self.state.update(p["id"], "push_unknown", remote_identity=remote)
                self.state.audit("push_started", id=p["id"], sha=sha, target_ref=destination, remote=policy.remote)
                try:
                    gitops.push_exact(policy, sha, destination)
                    observed = gitops.remote_sha(policy, destination)
                    if observed != sha:
                        raise SafeStop("push_unknown", "Remote commit could not be confirmed; use ghost publish again to reconcile.")
                except SafeStop as exc:
                    try:
                        observed = gitops.remote_sha(policy, destination)
                    except SafeStop:
                        observed = "unknown"
                    status = "pushed" if observed == sha else "push_failed" if observed is None and exc.code != "git_timeout" else "push_unknown"
                    self.state.update(p["id"], status)
                    self.state.audit("push_result", id=p["id"], result=status, reason=exc.code)
                    if status != "pushed":
                        raise SafeStop(status, "Push was not confirmed. No automatic retry; inspect remote or run publish again to reconcile.") from exc
                else:
                    self.state.update(p["id"], "pushed")
                    self.state.audit("push_result", id=p["id"], result="confirmed", sha=sha)
                return self.state.get(p["id"])

    def status(self) -> dict:
        proposals = self.state.list_proposals()
        public = []
        for p in proposals:
            public.append({k: v for k, v in p.items() if k not in {"before", "after"}})
        return {"paused": self.state.flag("paused"), "killed": self.state.flag("killed"),
                "repositories": [{"name": p.name, "path": p.path, "model": p.model, "timezone": p.timezone, "at": p.at, "mode": p.mode, "allow_push": p.allow_push} for p in self.policies()],
                "proposals": public, "runs": self.state.runs(), "events": self.state.events()}
