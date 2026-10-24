import dataclasses
import json
from pathlib import Path

import pytest

from ghost_contributor import gitops
from ghost_contributor.config import allowed, relative_path, safe_path, save_config
from ghost_contributor.editing import python_targets
from ghost_contributor.errors import SafeStop
from ghost_contributor.inference import DemoModel, local_host, validate_output
from ghost_contributor.state import process_lock
from conftest import SOURCE, commit


@pytest.mark.parametrize("path", ["../escape.py", "/tmp/x.py", "C:\\x.py", "a/../../x.py", "x\n.py", "./x.py"])
def test_path_traversal(path):
    with pytest.raises(SafeStop):
        relative_path(path)


@pytest.mark.parametrize("path", [".env", "secrets/key.py", "vendor/a.py", "node_modules/x.py", "credentials.py", ".github/code.py", "a.min.js"])
def test_permanent_excludes(path):
    assert not allowed(path, ["*"], [])


def test_symlink_rejected(tmp_path):
    outside = tmp_path / "external.py"
    outside.write_bytes(SOURCE)
    root = tmp_path / "repo"
    root.mkdir()
    try:
        (root / "alias.py").symlink_to(outside)
    except OSError:
        pytest.skip("symlink privilege unavailable")
    with pytest.raises(SafeStop):
        safe_path(root, "alias.py")


@pytest.mark.parametrize("url", ["https://api.example.com", "http://127.0.0.1.evil.com", "http://0.0.0.0:11434", "http://user:pass@localhost:11434", "http://localhost:11434/evil", "http://localhost:11434?redirect=evil"])
def test_remote_inference_rejected(url):
    with pytest.raises(SafeStop):
        local_host(url)


def test_localhost_pinned():
    assert local_host("http://localhost:11434") == "http://127.0.0.1:11434"


def test_model_cannot_expand_scope_or_invent_evidence():
    target = python_targets("retry.py", SOURCE, 10000)[0]
    original = DemoModel().generate(target)
    variants = []
    for change in [{"target":"../../other.py"}, {"command":"rm -rf ."}, {"evidence":[{"path":"retry.py","start_line":1,"end_line":4,"quote":"This does not occur in the source."}]}]:
        variants.append({**original, **change})
    for value in variants:
        with pytest.raises(SafeStop):
            validate_output(value, target)


@pytest.mark.parametrize("dirty", ["unstaged", "staged", "untracked"])
def test_dirty_tree_never_touches_source(project, dirty):
    root, policy, engine = project
    if dirty == "untracked":
        (root / "notes.txt").write_text("keep me")
    else:
        (root / "retry.py").write_bytes(SOURCE + b"# user's work\n")
        if dirty == "staged":
            gitops.git(root, "add", "--", "retry.py")
    before = (root / "retry.py").read_bytes()
    with pytest.raises(SafeStop, match="changes"):
        engine.run("test")
    assert (root / "retry.py").read_bytes() == before
    assert engine.state.runs()[0]["status"] == "blocked"


def test_pause_stops_and_resume_is_explicit(project):
    _, _, engine = project
    engine.state.set_flag("killed", True)
    with pytest.raises(SafeStop):
        engine.run("test")
    engine.state.set_flag("killed", False)
    assert engine.run("test")["status"] == "pending"


def test_lock_excludes_second_operation(tmp_path):
    path = tmp_path / "lock"
    with process_lock(path):
        with pytest.raises(SafeStop):
            with process_lock(path):
                pass


def test_policy_change_invalidates_approval(project):
    _, policy, engine = project
    p = engine.run("test")
    policy.model = "another-model:1"
    save_config(engine.config, [policy])
    with pytest.raises(SafeStop, match="Policy changed"):
        engine.approve(p["id"])


def test_revision_change_invalidates_approval(project):
    root, _, engine = project
    p = engine.run("test")
    (root / "other.txt").write_text("another commit")
    commit(root)
    with pytest.raises(SafeStop, match="revision changed"):
        engine.approve(p["id"])


def test_invalid_json_logged_without_secrets(project):
    _, _, engine = project
    class Broken:
        def generate(self, target):
            raise SafeStop("model_json", "sensitive text intentionally not persisted")
    engine.model_factory = lambda _: Broken()
    with pytest.raises(SafeStop):
        engine.run("test")
    assert "sensitive text" not in json.dumps(engine.state.events())
    assert engine.state.verify_audit() >= 1


def test_assume_unchanged_and_detached_rejected(project):
    root, policy, _ = project
    gitops.git(root, "update-index", "--assume-unchanged", "retry.py")
    with pytest.raises(SafeStop, match="index flags"):
        gitops.preflight(policy)
    gitops.git(root, "update-index", "--no-assume-unchanged", "retry.py")
    gitops.git(root, "checkout", "--detach")
    with pytest.raises(SafeStop, match="Detached"):
        gitops.preflight(policy)


@pytest.mark.parametrize("field,value", [("allow_push", "false"), ("local_only_confirmed", "false"), ("timeout", True), ("include", "*")])
def test_policy_types_fail_closed(project, field, value):
    _, policy, _ = project
    setattr(policy, field, value)
    with pytest.raises(SafeStop):
        policy.validate()
