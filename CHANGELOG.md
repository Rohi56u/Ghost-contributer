# Changelog

## 0.2.1 — source citation prompt

- Send source text and original line numbers as separate JSON fields. Real-model trials revealed that inline numeric labels were being copied into evidence quotes.
- Explicitly request exact, unprefixed source quotations. Strict evidence checking remains unchanged.
- Add transport-contract assertions that preserve source bytes separately from citation metadata.

## 0.2.0 — existing-model setup

- `ghost models`: discover installed local models without downloading any.
- `ghost setup`: choose a model, confirm local-only server setup, verify metadata/capabilities and register a clean repository.
- Optional separate sample repository uses real inference on the first run, distinct from the fixed demo.
- Windows setup, local Ollama and subsequent dashboard launchers; detailed Hinglish guide.
- Model/timeout switching with `ghost policy`; clearer HTTP diagnostics and embedding-model refusal.
- Exact names returned by Ollama are accepted, including names whose API representation omits a colon tag.

Core edit/publication scope is unchanged. Real-model quality on the user's laptop remains to be measured.
