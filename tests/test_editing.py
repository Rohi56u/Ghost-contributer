import ast

import pytest

from ghost_contributor.editing import Target, decode, python_targets, transform, validate_prose
from ghost_contributor.errors import SafeStop
from conftest import SOURCE

PROSE = "Return a capped exponential delay after validating the attempt and limits."


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
@pytest.mark.parametrize("final_newline", [True, False])
def test_exact_insertion_preserves_bytes(newline, final_newline):
    raw = SOURCE.replace(b"\n", newline)
    if not final_newline:
        raw = raw.rstrip(b"\r\n")
    target = python_targets("retry.py", raw, 10000)[0]
    result = transform(raw, target, PROSE)
    added = b'    """' + PROSE.encode() + b'"""' + newline
    assert result.replace(added, b"", 1) == raw
    assert transform(result, target, PROSE) == result


@pytest.mark.parametrize("prefix", [b"# -*- coding: utf-8 -*-\n# cafe: caf\xc3\xa9\n", b"\xef\xbb\xbf", b"# coding: latin-1\n# caf\xe9\n", b"# Preserve this comment\n\n"])
def test_encodings_and_headers(prefix):
    raw = prefix + SOURCE
    target = python_targets("retry.py", raw, 10000)[0]
    result = transform(raw, target, PROSE)
    assert result.startswith(prefix)
    assert decode(result)[1] == decode(raw)[1]
    assert ast.get_docstring(ast.parse(result).body[0]) == PROSE


def test_tabs_and_leading_comment():
    raw = SOURCE.replace(b"    ", b"\t").replace(b"\tif", b"\t# keep this\n\tif")
    target = python_targets("retry.py", raw, 10000)[0]
    result = transform(raw, target, PROSE)
    assert result.replace(b'\t"""' + PROSE.encode() + b'"""\n', b"", 1) == raw


@pytest.mark.parametrize("text", ['"""\nimport os\nos.system("evil")', "import os\nexecute something harmful", "```python\nprint(1)\n```", "<script>alert(1)</script>", "tiny", "Token=\"ghp_abcdefghijklmnopqrstuvwxyz\""])
def test_prose_injection_refused(text):
    with pytest.raises(SafeStop):
        validate_prose(text)


def test_escaped_quotes_cannot_escape_string():
    prose = 'Return the value described as "safe" and keep the backslash \\ literal.'
    target = python_targets("retry.py", SOURCE, 10000)[0]
    after = transform(SOURCE, target, prose)
    assert ast.get_docstring(ast.parse(after).body[0]) == prose


def test_documented_and_one_line_functions_not_selected():
    raw = b'def a():\n    """Already explained."""\n    return 1\n\ndef b(): return 2\n'
    assert python_targets("x.py", raw, 10000) == []


def test_ambiguous_duplicate_symbol_not_selected():
    assert python_targets("retry.py", SOURCE + b"\n" + SOURCE, 10000) == []


def test_secret_source_refused():
    raw = SOURCE.replace(b"    if", b'    key = "ghp_abcdefghijklmnopqrstuvwxyz"\n    if', 1)
    with pytest.raises(SafeStop, match="secret"):
        python_targets("retry.py", raw, 10000)


def test_mixed_newlines_refused():
    with pytest.raises(SafeStop):
        decode(SOURCE.replace(b"\n", b"\r\n", 1))


def test_markdown_exact_region_and_repeat():
    before = b"# Readme\r\n\r\n<!-- ghost:retry:start -->\r\n<!-- ghost:retry:end -->\r\nKEEP\r\n"
    target = Target("README.md", "markdown", "retry", 1, SOURCE.decode(), "retry.py", 1, 4, "retry")
    after = transform(before, target, PROSE)
    assert after.startswith(b"# Readme\r\n\r\n<!-- ghost:retry:start -->")
    assert after.endswith(b"<!-- ghost:retry:end -->\r\nKEEP\r\n")
    assert transform(after, target, PROSE) == after
    with pytest.raises(SafeStop):
        transform(after, target, "A different paragraph would overwrite existing prose.")
