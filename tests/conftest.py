from pathlib import Path

import pytest

from ghost_contributor import gitops
from ghost_contributor.config import RepoPolicy, save_config
from ghost_contributor.engine import Engine
from ghost_contributor.inference import DemoModel

SOURCE = b'''def retry_delay(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    if attempt < 0 or base <= 0 or cap <= 0:
        raise ValueError("attempt must be nonnegative; base and cap must be positive")
    return min(base * (2 ** attempt), cap)
'''


def commit(root, message="fixture"):
    gitops.git(root, "add", "--all")
    gitops.git(root, "-c", "user.name=Test", "-c", "user.email=test@localhost", "commit", "-m", message)


class FakeLocalModel(DemoModel):
    fixture = False
    identity = {"tag": "test-local:1", "digest": "test-only", "endpoint": "fake"}

    def generate(self, target):
        response = super().generate(target)
        response["uncertainty"] = "none"
        return response


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    gitops.git(root, "init", "-b", "main")
    gitops.git(root, "config", "core.autocrlf", "false")
    (root / "retry.py").write_bytes(SOURCE)
    commit(root)
    engine = Engine(tmp_path / "state", model_factory=lambda _: FakeLocalModel())
    policy = RepoPolicy(name="test", path=str(root), quiet_start="00:00", quiet_end="00:00").validate()
    save_config(engine.config, [policy])
    return root, policy, engine
