# PRD coverage and release boundaries

This table distinguishes implemented behavior from the broader proposal. The original PRD is not rewritten or treated as a completed implementation.

| Requirement area | v0.2 behavior | Status |
|---|---|---|
| Explicit repositories, canonical roots, include/exclude paths | Registered root is the approved boundary; tracked regular files only | Implemented |
| Existing local models and first-run setup | Installed-model selector, isolated sample repository, editable-source Windows launchers | Implemented; Windows execution pending |
| Model, timezone, schedule, checks, publish policy per repo | Strict TOML fields; exact tag; daily time; quiet hours; argument arrays | Implemented |
| Default dry-run/review | Registration starts in review with push disabled | Implemented |
| Bare/detached/dirty/in-progress/unexpected branch gate | Fails closed; hidden index flags also rejected | Implemented |
| Isolated worktree | Generation checks and approval use disposable/dedicated worktrees | Implemented |
| No-op, one focused change per run | No activity padding; handled target suppression | Implemented |
| User backlog | Explicit Python symbol or Markdown section/evidence file | Implemented |
| Minimal local inference and exact model metadata | Literal loopback, tags/show checks, bounded schema response, digest recorded | Implemented; one real 7B integration run verified, broad quality unmeasured |
| Python docstrings and comments | Missing docstring insertion only | Partial: inline comments and existing docstrings deferred |
| Markdown correction | Empty marked regions only | Partial: arbitrary correction/replacement deferred |
| Exact diff, rationale, attribution | CLI + local UI; commit attribution | Implemented |
| CST/AST/compile/idempotence validation | Exact insertion and unchanged executable AST outside docstrings | Implemented within supported surface |
| Configured checks | Bounded trusted command execution in worktree; unexpected edits rejected | Implemented; not an OS sandbox |
| Atomic write and recoverable original | Same-directory atomic replacement in isolated checkout; original retained in SQLite | Implemented |
| Precise staged files, dedicated branches, no force push | Exact candidate bytes compared with index and resulting commit | Implemented |
| User-approved local commits | UI or explicit CLI approval | Implemented |
| Unattended publication | Opt-in local commits; remote push always explicit CLI | Deliberately narrower than PRD |
| PR creation | None | Deferred P1 |
| Push failure reconciliation | Remote identity and exact SHA inspected before retry | Implemented |
| Append-only audit metadata | SQLite insert-only table plus hash chain | Implemented; not externally anchored |
| Fixed schedule, timezone, quiet hours, coalescing, locking | Daily slots with tested DST semantics | Implemented |
| Capped exponential retry/backoff | Fail closed; next daily slot or explicit manual retry | Deferred; no implicit side-effect retry |
| Pause/resume/kill switch | Durable flags checked at action boundaries | Implemented; not instant process preemption |
| OS-native timer integration | Foreground daemon + systemd example | Example supplied; not installed or tested on user machine |
| Configurable data retention | Manual archive guidance | Deferred |
| Cross-platform compatibility | Portable code + CI matrix | Linux tested locally; Windows/macOS CI pending |
| Model license/quality registry | Catalog sources, exact live identity, evaluation protocol | License documented; hardware/quality benchmark pending |

## Original acceptance criteria mapping

1. Dirty worktree stops: automated tests cover staged, unstaged and untracked changes.
2. Model cannot expand target/commands/policy: application-level schema, target and path tests cover this boundary. This is not a claim to detect every misleading natural-language instruction.
3. Supported prose changes preserve bytes: LF/CRLF, BOM, encoding-cookie, tabs, comments and final-newline golden checks.
4. Invalid targets/JSON/parsing fail closed: schema, evidence, secret, parser and scope tests.
5. Same task period does not repeat: unique database key, OS lock and handled-target history.
6. Push restricted to configured topic branch: tests use local bare remotes and refuse ambiguous/default destinations or conflicts.
7. Timeout reconciles before retry: simulated timeout after remote acceptance and missing confirmation tests.
8. No direct model request to non-loopback: address, proxy bypass, redirect and remote-model-metadata tests. Ollama server egress is separately configured.
9. Transparent commit attribution: commit message and Git identity tests; no synthetic timestamp configuration.
10. No-op creates no commit: candidate/no-op tests and branch inspection.

Do not describe this release as every P0/P1 feature implemented or as production certified. The core maintenance loop is runnable; the above boundaries are part of the release contract.
