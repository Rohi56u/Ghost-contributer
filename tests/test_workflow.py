import json
import sys

import pytest

from ghost_contributor import gitops
from ghost_contributor.config import save_config
from ghost_contributor.errors import SafeStop
from conftest import SOURCE


def test_complete_local_flow_keeps_user_branch_untouched(project):
    root, _, engine = project
    original = gitops.head(root)
    proposal = engine.run("test", task_period="daily:one")
    assert proposal["status"] == "pending"
    assert (root / "retry.py").read_bytes() == SOURCE
    result = engine.approve(proposal["id"])
    assert result["status"] == "committed"
    assert gitops.head(root) == original
    assert gitops.branch(root) == "main"
    assert not gitops.git(root, "status", "--porcelain")
    assert b"AI-assisted" in gitops.git(root, "show", "-s", "--format=%B", result["commit_sha"])
    assert b'"""Return' in gitops.git(root, "show", result["branch"] + ":retry.py")
    assert engine.run("test", task_period="daily:one")["status"] == "already_ran"
    assert engine.run("test", task_period="daily:two")["status"] == "noop"
    with pytest.raises(SafeStop):
        engine.approve(proposal["id"])
    assert engine.state.verify_audit() >= 5


def test_rejection_does_not_generate_same_task_again(project):
    root, _, engine = project
    p = engine.run("test")
    engine.reject(p["id"])
    assert engine.run("test")["status"] == "noop"
    assert (root / "retry.py").read_bytes() == SOURCE


def test_auto_commit_is_explicit_and_dry_run_overrides(project):
    root, policy, engine = project
    policy.mode = "auto_commit"
    save_config(engine.config, [policy])
    result = engine.run("test", dry_run=True)
    assert result["status"] == "pending"
    assert gitops.branch(root) == "main"


def test_auto_commit_honors_policy(project):
    _, policy, engine = project
    policy.mode = "auto_commit"
    save_config(engine.config, [policy])
    assert engine.run("test")["status"] == "committed"


def test_bounded_check_failure_has_no_commit(project):
    root, policy, engine = project
    policy.checks = [[sys.executable, "-c", "raise SystemExit(1)"]]
    save_config(engine.config, [policy])
    with pytest.raises(SafeStop, match="check failed"):
        engine.run("test")
    assert (root / "retry.py").read_bytes() == SOURCE
    assert gitops.text(root, "branch", "--list", "ghost/*") == ""


def test_check_mutation_rejected(project):
    root, policy, engine = project
    policy.checks = [[sys.executable, "-c", "from pathlib import Path; Path('surprise.txt').write_text('unexpected')"]]
    save_config(engine.config, [policy])
    with pytest.raises(SafeStop, match="Unexpected file"):
        engine.run("test")
    assert not (root / "surprise.txt").exists()


def test_audit_database_rejects_mutation(project):
    _, _, engine = project
    import sqlite3
    engine.state.audit("test")
    with engine.state.connect() as db:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("DELETE FROM audit")
    assert engine.state.verify_audit() == 1


def make_remote(tmp_path, root, policy, engine):
    remote = tmp_path / "remote.git"
    remote.mkdir()
    gitops.git(remote, "init", "--bare", "--initial-branch=main")
    gitops.git(root, "remote", "add", "origin", str(remote))
    gitops.git(root, "push", "origin", "HEAD:refs/heads/main")
    policy.allow_push = True
    save_config(engine.config, [policy])
    p = engine.run("test")
    return remote, engine.approve(p["id"])


def test_push_is_opt_in(project):
    _, _, engine = project
    p = engine.run("test")
    p = engine.approve(p["id"])
    with pytest.raises(SafeStop, match="allow_push"):
        engine.publish(p["id"])


def test_push_exact_branch_reconciles_without_duplicate(project, tmp_path):
    root, policy, engine = project
    remote, p = make_remote(tmp_path, root, policy, engine)
    result = engine.publish(p["id"])
    assert result["status"] == "pushed"
    assert gitops.text(remote, "rev-parse", p["branch"]) == p["commit_sha"]
    assert gitops.text(remote, "show-ref", "--heads", ok=(0,1)).count("refs/heads/") == 2
    assert engine.publish(p["id"])["status"] == "pushed"


def test_timeout_after_success_is_reconciled(project, tmp_path, monkeypatch):
    root, policy, engine = project
    remote, p = make_remote(tmp_path, root, policy, engine)
    original = gitops.push_exact
    def uncertain(*args):
        original(*args)
        raise SafeStop("git_timeout", "simulated timeout after remote accepted commit")
    monkeypatch.setattr(gitops, "push_exact", uncertain)
    assert engine.publish(p["id"])["status"] == "pushed"


def test_remote_conflict_is_not_overwritten(project, tmp_path):
    root, policy, engine = project
    remote, p = make_remote(tmp_path, root, policy, engine)
    gitops.git(root, "push", "origin", "HEAD:refs/heads/" + p["branch"])
    with pytest.raises(SafeStop, match="different commit"):
        engine.publish(p["id"])
    assert gitops.text(remote, "rev-parse", p["branch"]) == gitops.head(root)


def test_default_branch_push_refused(project, tmp_path):
    root, policy, engine = project
    remote, p = make_remote(tmp_path, root, policy, engine)
    gitops.git(remote, "symbolic-ref", "HEAD", "refs/heads/" + p["branch"])
    with pytest.raises(SafeStop, match="default branch"):
        engine.publish(p["id"])


def test_distinct_push_url_refused(project, tmp_path):
    root, policy, engine = project
    remote, p = make_remote(tmp_path, root, policy, engine)
    gitops.git(root, "remote", "set-url", "--push", "origin", str(tmp_path / "another-remote.git"))
    with pytest.raises(SafeStop, match="Different fetch and push"):
        engine.publish(p["id"])


def test_unreachable_reconciliation_preserves_unknown(project, tmp_path, monkeypatch):
    root, policy, engine = project
    remote, p = make_remote(tmp_path, root, policy, engine)
    calls = []
    original_lookup = gitops.remote_sha
    def push(*args):
        calls.append('push')
        raise SafeStop("git_timeout", "indeterminate")
    def lookup(*args):
        if calls:
            raise SafeStop("git_timeout", "remote unavailable")
        return original_lookup(*args)
    monkeypatch.setattr(gitops, "push_exact", push)
    monkeypatch.setattr(gitops, "remote_sha", lookup)
    with pytest.raises(SafeStop) as error:
        engine.publish(p["id"])
    assert error.value.code == "push_unknown"
    assert engine.state.get(p["id"])["status"] == "push_unknown"
    assert calls == ["push"]


def test_markdown_backlog_end_to_end(project):
    from conftest import commit, FakeLocalModel
    root, policy, engine = project
    (root / "README.md").write_text("# Example\n\n<!-- ghost:retry:start -->\n<!-- ghost:retry:end -->\n", encoding="utf-8")
    commit(root)
    policy.backlog = [{"path":"README.md", "section":"retry", "evidence_path":"retry.py"}]
    save_config(engine.config, [policy])
    class MarkdownModel(FakeLocalModel):
        def generate(self, target):
            return {"target":"README.md", "rationale":"Document the explicit retry helper in the requested empty section.", "replacement_text":"The retry delay increases exponentially and is capped at the configured limit.", "uncertainty":"none", "evidence":[{"path":"retry.py", "start_line":4, "end_line":4, "quote":"return min(base * (2 ** attempt), cap)"}]}
    engine.model_factory = lambda _: MarkdownModel()
    p = engine.run("test")
    result = engine.approve(p["id"])
    assert result["status"] == "committed"
    assert b"increases exponentially" in gitops.git(root, "show", result["branch"] + ":README.md")
    assert "increases exponentially" not in (root / "README.md").read_text()
