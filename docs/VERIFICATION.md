# Verification record

Release: 0.2.1. Build date: October 22, 2026. Runtime: Python 3.12.14, Git 2.51.1, Linux.

## Executed

- Automated Python tests after the 0.2.1 prompt fix: **93 passed in 5.53s**.
- Real temporary Git repositories: scan, proposal, review, dedicated-worktree commit, unchanged developer branch, duplicate suppression and no-op.
- Temporary bare Git remotes: explicit ref push, default/ambiguous branch rejection, conflict refusal, timeout-after-acceptance reconciliation and indeterminate-remote handling.
- Local HTTP fixtures: Ollama request schema, evidence validation, proxy bypass, redirect rejection and cloud-model metadata refusal. These are contract tests, not real model inference.
- Seven-model synthetic inventory: wizard selection, real HTTP client against a local fixture, sample creation, review/commit, duplicate protection, model switching, embedding refusal and controlled errors. No weights are loaded by these fixtures.
- Local dashboard HTTP: authentication, Host/Origin restrictions, CSP, status API and pause mutation; remote publication is not exposed in the UI.
- Python formatting fixtures: LF/CRLF, BOM, Latin-1 cookie, tabs, comments, final-newline behavior, malicious output and exact insertion checks.
- Real Ollama 0.40.8 with local `qwen2.5-coder:7b`: one sample repository produced a validated proposal in 47.633 seconds measured around the dashboard run action. The browser displayed the diff/evidence, accepted explicit approval and created a real `ghost/…` branch commit. The original `main` branch stayed unchanged; no remote push occurred. See [the run record](REAL-RUN.md).
- Headless Chromium visual inspection of the dashboard, proposal evidence, approval dialog and committed history, with screenshots of the actual successful flow.
- Windows and Unix installation instructions and declared CI matrix supplied.

## Not established

- General model quality, hallucination rate, hardware compatibility or representative latency. The one real-model sample above is an integration demonstration, not a benchmark or evidence that all installed models will produce acceptable prose.
- Broad responsive/accessibility/browser coverage. The recorded Chromium desktop flow is the browser coverage completed here.
- Windows/macOS execution: the CI configuration is supplied but has not run in the user's GitHub repository.
- Live GitHub authentication, branch protections, Internet push or pull-request creation. Push logic was exercised against local bare remotes.
- Production-scale reliability, OS sandboxing, encrypted data retention or externally anchored audit integrity.

Run the actual model benchmark and cross-platform CI before a public stable release. No passing test here should be read as a substitute for semantic review of generated prose.
