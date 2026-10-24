from __future__ import annotations

import ast
import difflib
import io
import re
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from .config import RepoPolicy, allowed, no_secret
from .errors import SafeStop
from .gitops import read_tracked, tracked


@dataclass
class Target:
    path: str
    kind: str
    symbol: str
    line: int
    context: str
    evidence_path: str
    evidence_start: int
    evidence_end: int
    section: str = ""

    def to_dict(self):
        return asdict(self)


def decode(data: bytes) -> tuple[str, str]:
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
        if encoding.lower().replace("_", "-") not in {"utf-8", "utf-8-sig", "ascii", "iso-8859-1", "latin-1"}:
            raise ValueError("encoding")
        value = data.decode(encoding)
        if "\r" in value.replace("\r\n", "") or ("\r\n" in value and "\n" in value.replace("\r\n", "")):
            raise ValueError("mixed newlines")
        return value, encoding
    except (SyntaxError, UnicodeError, ValueError) as exc:
        raise SafeStop("encoding", "Unsupported encoding or mixed newlines; file was skipped.") from exc


def functions(tree: ast.AST, prefix: str = ""):
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            name = f"{prefix}.{node.name}" if prefix else node.name
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield name, node
            yield from functions(node, name)


def python_targets(path: str, data: bytes, maximum: int, symbol: str | None = None) -> list[Target]:
    source, _ = decode(data)
    tree = ast.parse(source)
    lines = source.splitlines()
    entries = list(functions(tree))
    found = []
    for name, node in entries:
        if symbol and name != symbol:
            continue
        if not symbol and any(x.startswith("_") for x in name.split(".")):
            continue
        if sum(n == name for n, _ in entries) != 1 or ast.get_docstring(node) is not None or node.decorator_list or len(node.body) < 2 or node.body[0].lineno == node.lineno:
            continue
        excerpt = "\n".join(lines[node.lineno - 1:node.end_lineno])
        if len(excerpt) > maximum or len(excerpt) < 60 or re.search(r"(?i)generated|do not edit", "\n".join(lines[:8])):
            continue
        no_secret(excerpt)
        found.append(Target(path, "python_docstring", name, node.lineno, excerpt, path, node.lineno, node.end_lineno))
    return found


def markdown_region(source: str, section: str) -> tuple[int, int]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", section):
        raise SafeStop("section", "Markdown section IDs must use letters, digits, underscores or hyphens.")
    start, end = f"<!-- ghost:{section}:start -->", f"<!-- ghost:{section}:end -->"
    if source.count(start) != 1 or source.count(end) != 1:
        raise SafeStop("section", "Markdown needs exactly one matching start/end marker pair.")
    a, b = source.index(start) + len(start), source.index(end)
    if a >= b or source[a:b].strip() or not source[:a].splitlines()[-1] == start:
        raise SafeStop("section", "Only empty, standalone explicitly marked Markdown sections are supported in v0.1.")
    return a, b


def select(policy: RepoPolicy, skip: set[tuple[str, str]] | None = None) -> tuple[Target, bytes] | None:
    root = Path(policy.path)
    files = tracked(root)
    if len(files) > 10000:
        raise SafeStop("repo_limit", "Repository exceeds the v0.1 10,000-file scan limit.")
    requests = policy.backlog or [{"path": path} for path in files if path.endswith(".py")]
    for request in requests:
        path = request["path"]
        if path not in files or not allowed(path, policy.include, policy.exclude):
            continue
        try:
            raw = read_tracked(root, path, policy.max_file_bytes)
            if path.endswith(".py"):
                candidates = [t for t in python_targets(path, raw, policy.max_context_chars, request.get("symbol")) if (t.path, t.symbol) not in (skip or set())]
                if candidates:
                    return candidates[0], raw
            elif path.endswith(".md") and "section" in request and "evidence_path" in request:
                if (path, request["section"]) in (skip or set()):
                    continue
                source, _ = decode(raw)
                markdown_region(source, request["section"])
                evidence_path = request["evidence_path"]
                if evidence_path not in files or not allowed(evidence_path, policy.include, policy.exclude):
                    continue
                evidence, _ = decode(read_tracked(root, evidence_path, policy.max_file_bytes))
                if len(evidence) > policy.max_context_chars:
                    continue
                no_secret(evidence)
                return Target(path, "markdown", request["section"], 1, evidence, evidence_path, 1, len(evidence.splitlines()), request["section"]), raw
        except (SafeStop, SyntaxError):
            # One unsupported file is not permission to expand scope or invent a task.
            continue
    return None


def validate_prose(text: str) -> None:
    if not isinstance(text, str) or not 15 <= len(text) <= 700 or any(ord(c) < 32 and c != "\n" for c in text):
        raise SafeStop("proposal_text", "Expected 15-700 characters of plain documentation.")
    if any(x in text for x in ['"""', "'''", "```", "<!--", "-->", "<script", "http://", "https://"]):
        raise SafeStop("proposal_text", "Code fences, HTML, links and triple-quote delimiters are outside the MVP prose policy.")
    if re.search(r"(?m)^\s*(?:import |from \w+ import |def |class |exec\(|eval\(|#!)", text):
        raise SafeStop("proposal_text", "Executable-looking content is outside the prose policy.")
    no_secret(text)


class AddDocstring(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, line: int, prose: str):
        self.line, self.prose, self.matches = line, prose, 0

    def leave_FunctionDef(self, original, updated):
        if self.get_metadata(PositionProvider, original).start.line != self.line:
            return updated
        self.matches += 1
        if not isinstance(updated.body, cst.IndentedBlock):
            raise SafeStop("one_line", "One-line function suites are unsupported.")
        if updated.get_docstring() is not None:
            return updated
        # One logical line keeps the insertion independently verifiable byte-for-byte.
        prose = " ".join(self.prose.split()).replace("\\", "\\\\").replace('"', '\\"')
        statement = cst.SimpleStatementLine(body=[cst.Expr(cst.SimpleString('"""' + prose + '"""'))])
        return updated.with_changes(body=updated.body.with_changes(body=[statement, *updated.body.body]))


class StripDocs(ast.NodeTransformer):
    def generic_visit(self, node):
        node = super().generic_visit(node)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body = node.body[1:]
        return node


def transform(raw: bytes, target: Target, prose: str) -> bytes:
    validate_prose(prose)
    source, encoding = decode(raw)
    if target.kind == "markdown":
        start_marker, end_marker = f"<!-- ghost:{target.section}:start -->", f"<!-- ghost:{target.section}:end -->"
        nl = "\r\n" if "\r\n" in source else "\n"
        replacement = nl + nl + prose.strip().replace("\r\n", "\n").replace("\n", nl) + nl + nl
        if source.count(start_marker) == 1 and source.count(end_marker) == 1:
            a, b = source.index(start_marker) + len(start_marker), source.index(end_marker)
            if source[a:b] == replacement:
                return raw
        a, b = markdown_region(source, target.section)
        return (source[:a] + replacement + source[b:]).encode(encoding)
    try:
        before = ast.parse(source)
        wrapper = MetadataWrapper(cst.parse_module(raw))
        editor = AddDocstring(target.line, prose)
        result = wrapper.visit(editor).bytes
        if editor.matches != 1:
            raise SafeStop("ambiguous", "Target did not match exactly one function.")
        if result == raw:
            return raw
        after = ast.parse(result)
        compile(after, target.path, "exec")
        if ast.dump(StripDocs().visit(before), include_attributes=False) != ast.dump(StripDocs().visit(after), include_attributes=False):
            raise SafeStop("semantics", "Executable syntax changed; candidate rejected.")
        # Removing the only added physical line must reconstruct the original bytes.
        old_lines, new_lines = raw.splitlines(keepends=True), result.splitlines(keepends=True)
        ops = [op for op in difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False).get_opcodes() if op[0] != "equal"]
        if len(ops) != 1 or ops[0][0] != "insert" or ops[0][4] - ops[0][3] != 1:
            raise SafeStop("span", "Change was not exactly one docstring-line insertion.")
        if decode(result)[1] != encoding:
            raise SafeStop("encoding", "Encoding changed.")
        return result
    except (cst.ParserSyntaxError, SyntaxError, UnicodeError) as exc:
        raise SafeStop("parse", "Parser rejected the candidate; no source was changed.") from exc


def diff(raw: bytes, candidate: bytes, path: str) -> str:
    before, _ = decode(raw)
    after, _ = decode(candidate)
    return "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile="a/" + path, tofile="b/" + path))
