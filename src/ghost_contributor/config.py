from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import SafeStop

BLOCKED = {".git", ".env", ".venv", "venv", "node_modules", "vendor", "vendors", "dist", "build", "generated", "__pycache__", "secrets", "credentials"}
SECRET = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{16,}|(?:AKIA|ASIA)[A-Z0-9]{16}|(?i:(?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"])[^'\"\s]{8,}")


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def no_secret(value: str) -> None:
    if SECRET.search(value):
        raise SafeStop("secret_detected", "Potential secret detected; context was not sent or logged.")


def relative_path(value: str) -> str:
    p = PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts or "\\" in value or ":" in value or any(ord(c) < 32 for c in value) or value != p.as_posix():
        raise SafeStop("path_rejected", "Expected a normalized repository-relative path.")
    return value


def allowed(path: str, include: list[str], exclude: list[str]) -> bool:
    relative_path(path)
    p = PurePosixPath(path)
    if any(part.lower() in BLOCKED or part.startswith(".") for part in p.parts):
        return False
    if p.suffix not in {".py", ".md"} or re.search(r"(?:secret|credential|\.min\.|\.lock)", path, re.I):
        return False
    return any(fnmatch.fnmatchcase(path, x) for x in include) and not any(fnmatch.fnmatchcase(path, x) for x in exclude)


def safe_path(root: Path, path: str) -> Path:
    relative_path(path)
    p = root
    for part in PurePosixPath(path).parts:
        p = p / part
        if p.is_symlink():
            raise SafeStop("symlink", "Symlinks are not supported.")
    if not p.resolve().is_relative_to(root.resolve()) or not p.is_file():
        raise SafeStop("path_rejected", "Target is not a regular file inside the registered repository.")
    return p


@dataclass
class RepoPolicy:
    name: str
    path: str
    base_branch: str = "main"
    model: str = "qwen2.5-coder:1.5b"
    host: str = "http://127.0.0.1:11434"
    include: list[str] = field(default_factory=lambda: ["*.py", "README.md", "docs/*.md"])
    exclude: list[str] = field(default_factory=lambda: ["tests/*", "test_*", "*_pb2.py"])
    timezone: str = "Asia/Kolkata"
    at: str = "10:00"
    quiet_start: str = "22:00"
    quiet_end: str = "08:00"
    mode: str = "review"
    allow_push: bool = False
    remote: str = "origin"
    branch_prefix: str = "ghost/"
    timeout: int = 90
    max_context_chars: int = 10000
    num_ctx: int = 8192
    max_file_bytes: int = 100000
    checks: list[list[str]] = field(default_factory=list)
    check_timeout: int = 60
    backlog: list[dict] = field(default_factory=list)
    local_only_confirmed: bool = False

    def validate(self) -> "RepoPolicy":
        strings = ["name", "path", "base_branch", "model", "host", "timezone", "at", "quiet_start", "quiet_end", "mode", "remote", "branch_prefix"]
        integers = ["timeout", "max_context_chars", "num_ctx", "max_file_bytes", "check_timeout"]
        if any(type(getattr(self, key)) is not str for key in strings) or any(type(getattr(self, key)) is not int for key in integers) or type(self.allow_push) is not bool or type(self.local_only_confirmed) is not bool:
            raise SafeStop("config", "Policy fields must use their declared string, integer or boolean types.")
        if any(not isinstance(getattr(self, key), list) or not all(isinstance(v, str) and v for v in getattr(self, key)) for key in ["include", "exclude"]) or not isinstance(self.checks, list) or not isinstance(self.backlog, list) or not all(isinstance(v, dict) for v in self.backlog):
            raise SafeStop("config", "Invalid policy list fields.")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", self.name):
            raise SafeStop("config", "Repository name must use letters, digits, underscores or hyphens.")
        self.path = str(Path(self.path).expanduser().resolve(strict=True))
        if self.mode not in {"review", "auto_commit"}:
            raise SafeStop("config", "Mode must be review or auto_commit (local branch only).")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:+-]{0,199}", self.model) or "cloud" in self.model.lower():
            raise SafeStop("config", "Choose an exact installed local model name from ghost models, not a cloud model.")
        if not re.fullmatch(r"ghost/[a-zA-Z0-9_/-]*", self.branch_prefix) or "//" in self.branch_prefix:
            raise SafeStop("config", "Automation branch prefix must start with ghost/.")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.remote):
            raise SafeStop("config", "Use a configured remote name, not a URL.")
        if not self.base_branch or self.base_branch.startswith("-"):
            raise SafeStop("config", "Invalid base branch.")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise SafeStop("config", "Unknown IANA timezone; install tzdata on Windows.") from exc
        for value in [self.at, self.quiet_start, self.quiet_end]:
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
                raise SafeStop("config", "Schedule times must be HH:MM.")
        if not (1 <= self.timeout <= 300 and 1 <= self.check_timeout <= 300 and 1024 <= self.max_context_chars <= 24000 and 4096 <= self.num_ctx <= 32768 and 1000 <= self.max_file_bytes <= 500000):
            raise SafeStop("config", "Timeout, context or file limit is outside the supported bounds.")
        if not all(isinstance(x, list) and x and all(isinstance(v, str) and v and "\x00" not in v for v in x) for x in self.checks):
            raise SafeStop("config", "Checks must be nonempty argument arrays; shell strings are forbidden.")
        for target in self.backlog:
            if set(target) - {"path", "symbol", "section", "evidence_path"} or "path" not in target:
                raise SafeStop("config", "Backlog entries need a path plus symbol or section/evidence_path.")
            relative_path(target["path"])
            if "evidence_path" in target:
                relative_path(target["evidence_path"])
        return self

    @property
    def fingerprint(self) -> str:
        return digest(json.dumps(asdict(self), sort_keys=True))


def load_config(path: Path) -> list[RepoPolicy]:
    if not path.exists():
        raise SafeStop("config_missing", "Run ghost init, then ghost repo add PATH.")
    try:
        data = tomllib.loads(path.read_text("utf-8"))
        if set(data) - {"version", "repositories"} or data.get("version") != 1:
            raise ValueError("Unsupported configuration version")
        result = [RepoPolicy(**r).validate() for r in data.get("repositories", [])]
        if len({r.name for r in result}) != len(result) or len({r.path for r in result}) != len(result):
            raise ValueError("Duplicate repository")
        return result
    except (TypeError, ValueError, OSError) as exc:
        raise SafeStop("config", "Invalid configuration; check fields, TOML types, paths and duplicate repositories.") from exc


def save_config(path: Path, repos: list[RepoPolicy]) -> None:
    lines = ["version = 1", "# Configured checks and Git hooks execute trusted local code. Review before enabling."]
    for repo in repos:
        lines.append("\n[[repositories]]")
        values = asdict(repo)
        for key, value in values.items():
            if key == "backlog":
                continue
            lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
        for target in repo.backlog:
            lines.append("[[repositories.backlog]]")
            lines.extend(f"{key} = {json.dumps(value)}" for key, value in target.items())
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    from .state import atomic_write
    atomic_write(path, ("\n".join(lines) + "\n").encode(), mode=0o600)
