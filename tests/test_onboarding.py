"""Onboarding contracts use synthetic model metadata/output, never real inference."""
import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from ghost_contributor import gitops, onboarding
from ghost_contributor.cli import execute, parser
from ghost_contributor.config import RepoPolicy
from ghost_contributor.editing import python_targets
from ghost_contributor.engine import Engine
from ghost_contributor.errors import SafeStop
from ghost_contributor.inference import DemoModel, Ollama


@pytest.fixture
def local_ollama():
    # Seven fictional installed names exercise discovery without assuming the
    # user's actual model inventory or downloading weights.
    names = [f"test-coder:{i}" for i in range(7, 0, -1)]
    seen = []
    target = python_targets("retry.py", onboarding.SAMPLE_SOURCE.encode(), 10000)[0]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, value):
            data = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            seen.append((self.path, None))
            assert self.path == "/api/tags"
            self.respond({"models": [
                {"name": name, "size": 1000000000, "digest": "test-digest",
                 "details": {"parameter_size": "test", "quantization_level": "test"}}
                for name in names
            ]})

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((self.path, data))
            assert data["model"] in names
            if self.path == "/api/show":
                self.respond({"model_info": {"general.architecture": "test"},
                              "capabilities": ["completion"], "license": "test fixture"})
            else:
                assert self.path == "/api/chat"
                self.respond({"message": {"content": json.dumps(DemoModel().generate(target))}})

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def answers(*values):
    iterator = iter(values)
    return lambda _: next(iterator)


def test_installed_model_setup_to_reviewed_commit(tmp_path, local_ollama):
    host, seen = local_ollama
    engine = Engine(tmp_path / "state")
    result = onboarding.setup(engine, host=host, ask=answers("4", "y", "", "sample"), tell=lambda _: None)
    policy = engine.policy("sample")
    root = Path(result["path"])
    assert result["model"] == policy.model == "test-coder:4"
    assert policy.mode == "review" and not policy.allow_push
    assert policy.local_only_confirmed and policy.timeout == 180
    assert policy.quiet_start == policy.quiet_end
    assert not result["fixture"] and not engine.state.has_pending("sample")
    assert all(path in {"/api/tags", "/api/show"} for path, _ in seen)
    assert (root / "retry.py").read_bytes() == onboarding.SAMPLE_SOURCE.encode()
    assert gitops.git(root, "show", "HEAD:retry.py") == (root / "retry.py").read_bytes()
    base = gitops.preflight(policy)

    # Exercise the real HTTP client against the explicit synthetic local server.
    proposal = engine.run("sample", dry_run=True)
    assert proposal["status"] == "pending"
    assert not proposal["fixture"] and proposal["model"]["tag"] == policy.model
    assert [path for path, _ in seen].count("/api/chat") == 1
    assert next(data for path, data in seen if path == "/api/chat")["model"] == policy.model
    approved = engine.approve(proposal["id"])
    assert approved["status"] == "committed"
    assert gitops.head(root) == base and gitops.branch(root) == "main"
    assert gitops.git(root, "show", f"{approved['branch']}:retry.py") != (root / "retry.py").read_bytes()


def test_setup_existing_repo_and_duplicate_preserves_config(project, local_ollama, tmp_path):
    root, _, _ = project
    host, _ = local_ollama
    engine = Engine(tmp_path / "new-state")
    base = gitops.head(root)
    onboarding.setup(engine, host=host, ask=answers("1", "yes", str(root), "mine"), tell=lambda _: None)
    original = engine.config.read_bytes()
    with pytest.raises(SafeStop, match="already registered"):
        onboarding.setup(engine, host=host, ask=answers("2", "y", str(root), "second"), tell=lambda _: None)
    assert engine.config.read_bytes() == original
    assert gitops.head(root) == base and not gitops.git(root, "status", "--porcelain")


def test_setup_without_local_confirmation_does_not_register(tmp_path, local_ollama):
    host, seen = local_ollama
    engine = Engine(tmp_path / "state")
    with pytest.raises(SafeStop, match="local-only"):
        onboarding.setup(engine, host=host, ask=answers("1", "n"), tell=lambda _: None)
    assert not engine.config.exists()
    assert not (engine.state.root / "playgrounds").exists()
    assert all(path == "/api/tags" for path, _ in seen)


def test_cloud_models_excluded_and_selection_retry():
    models = [{"name": "remote:cloud", "remote": True, "parameters": "?"},
              {"name": "my-local-model", "remote": False, "parameters": "test"}]
    shown = []
    assert onboarding.pick_model(models, answers("invalid", "2", "1"), shown.append) == "my-local-model"
    assert not any("remote:cloud" in line for line in shown)
    with pytest.raises(SafeStop, match="No installed local models"):
        onboarding.pick_model(models[:1], answers(), shown.append)


@pytest.mark.parametrize("payload", [{}, {"models": {}}, {"models": [None]}, {"models": [{"name": ""}]}])
def test_invalid_model_catalog_fails_closed(tmp_path, monkeypatch, payload):
    client = Ollama(RepoPolicy(name="test", path=str(tmp_path)))
    monkeypatch.setattr(client, "request", lambda *args: payload)
    with pytest.raises(SafeStop) as error:
        client.models()
    assert error.value.code == "model_list"


def test_embedding_model_rejected_without_generation(tmp_path, monkeypatch):
    policy = RepoPolicy(name="test", path=str(tmp_path), model="local-embedding", local_only_confirmed=True).validate()
    client = Ollama(policy)
    seen = []

    def request(path, data=None):
        seen.append(path)
        if path == "/api/tags":
            return {"models": [{"name": policy.model}]}
        return {"model_info": {"general.architecture": "test"}, "capabilities": ["embedding"]}

    monkeypatch.setattr(client, "request", request)
    with pytest.raises(SafeStop) as error:
        client.inspect()
    assert error.value.code == "model_capability" and "/api/chat" not in seen


def test_switch_model_preserves_review_and_invalid_timeout_is_atomic(project):
    _, _, engine = project
    execute(parser().parse_args(["--home", str(engine.state.root), "policy", "test",
                                "--model", "my-local-model", "--timeout", "180"]))
    updated = engine.policy("test")
    assert updated.model == "my-local-model" and updated.timeout == 180
    assert updated.mode == "review" and not updated.allow_push and not updated.local_only_confirmed
    original = engine.config.read_bytes()
    with pytest.raises(SafeStop):
        execute(parser().parse_args(["--home", str(engine.state.root), "policy", "test", "--timeout", "301"]))
    assert engine.config.read_bytes() == original


@pytest.mark.parametrize("status, expected", [(404, "not found"), (500, "RAM/VRAM"), (400, "structured-output")])
def test_http_failure_diagnostic_without_remote_body(tmp_path, monkeypatch, status, expected):
    client = Ollama(RepoPolicy(name="test", path=str(tmp_path)))

    def fail(*args, **kwargs):
        raise urllib.error.HTTPError(client.host, status, "sensitive-server-message", {}, None)

    monkeypatch.setattr(client.opener, "open", fail)
    with pytest.raises(SafeStop) as error:
        client.models()
    assert expected in str(error.value)
    assert "sensitive-server-message" not in str(error.value)
