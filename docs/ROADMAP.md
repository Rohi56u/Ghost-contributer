# Roadmap to a useful developer tool

## Phase 1: usable, inspectable core — included

Local inference adapter, narrow deterministic edits, exact review receipts, safe local commits, opt-in explicit push, scheduler, local dashboard, audit trail and failure-focused tests. Ship with explicit limitations and a short installation path.

## Phase 2: trust and onboarding — next release gate

- Run the real-model benchmark in MODEL-EVALUATION.md and publish the results.
- Run the CI matrix on Linux, Windows and macOS; test Git line-ending filters and native credential helpers.
- Add a recover command for interrupted commit states and a deliberate proposal-retention policy.
- Add a structured “skip reason” panel for candidate discovery; current no-op categories are coarse.
- Implement a guided policy editor and opt-in reminders entirely on the local machine.
- Add short-lived network retry backoff only for operations with explicit idempotency and verified outcomes.
- Review dependency provenance, repository hook assumptions and local server threat boundaries before public release.

Gate: no safety regression on golden fixtures; no unexplained source edits; install on clean test machines; at least five developers complete a real review flow.

## Phase 3: more useful work

- Existing-docstring corrections with span fingerprints and explicit source-of-truth evidence.
- Safe Markdown replacement blocks, not only empty regions.
- Relevant test/configuration retrieval within a strict context budget.
- Rejection reasons and a curated backlog so the tool learns preferences without training on private source by default.
- Optional draft-PR creation through GitHub CLI/App, explicit opt-in, existing auth and branch protections.

Gate: useful changes retained after one week; lower measured review effort than manual maintenance; no increase in maintainer cleanup work.

## Phase 4: language adapters and team policy

Tested TypeScript/JavaScript doc-comment adapters, editor integration, signed policy profiles, encrypted local state options and optional team controls. Keep source inference local by default. Add one language only after its parser/span/no-op fixture suite is complete.

## Community launch

Write a concise README with a truthful 90-second demonstration, reproducible setup and visible supported/unsupported scope. Publish the source, license and CI results. Invite maintainers to test on their own small repos, collect concrete rejection reasons, and prioritize saved review effort over stars or commit counts. Do not auto-open issues, PRs or outreach messages on third-party projects.

Differentiation to test: “the smallest useful change with enough evidence to approve quickly.” The claim is a product hypothesis. Validate it with usage and measured retention; do not call it a unique invention or guaranteed contest winner.
