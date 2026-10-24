# Trust boundaries and recovery

## Threat model

Repository text and model output are untrusted. Local policy, configured validation programs, Git hooks, installed Ollama and the operating-system account are trusted. Ghost is a maintenance assistant, not a sandbox for hostile repositories.

| Risk | Implemented control | Remaining limit |
|---|---|---|
| Source sent to a remote model | Literal loopback endpoint, proxy bypass, no redirects, reject remote model metadata, explicit local-only setup acknowledgement | The client cannot prove a separately installed local server never forwards data. Configure Ollama itself. |
| Prompt injection | Model cannot choose commands or expand target; schema and exact quote validation outside model | Prose can still be misleading. Review it. |
| Sensitive source | Allowed paths, secret-like path excludes and pattern checks before generation | Regexes cannot detect every secret. User-selected repo scope still matters. |
| Hidden worktree changes | Clean status, no sparse/assume-unchanged index flags, HEAD blob versus disk comparison | Filesystem races against an actively malicious local process are not in scope. |
| Executable edits | CST insertion, one added physical line, AST/compile comparison | `__doc__` is intentionally observable; semantic accuracy remains a human task. |
| Browser attack against localhost | Token authentication, strict Host and Origin, no CORS, CSP, textContent rendering | Protect your OS account and keep the printed capability URL private. |
| Accidental remote publication | Explicit CLI command and opt-in, verified topic branch, exact refspec, no force | Configured hooks and credential helpers are trusted executables. |
| Crash during commit or push | Persistent intermediate state, preserved worktree, SHA reconciliation | Recovery may require manual Git inspection. |

`ghost stop` sets durable stop and pause flags. It does not terminate an already-running Git process, hook or local inference request mid-instruction. It prevents the next gated action; timeouts bound most waits. Use your process manager if a trusted check or hook needs immediate termination. On Windows, terminating a check process does not guarantee every descendant process exits; use controlled checks.

The HTTP server binds only to `127.0.0.1`. Do not reverse-proxy it, expose its port, embed it in a public site or use it as a multi-user service. The standard-library server is intentionally scoped to a single local operator.

## Inspect a failed commit

1. Run `ghost stop` and `ghost status`. Find the proposal ID, recorded worktree path and topic branch.
2. Inspect that worktree with `git status`, `git log -3 --oneline` and `git diff`. Do not re-run `approve` on the same uncertain record.
3. Compare the topic commit to the saved proposal using `ghost review ID` and `git show BRANCH`.
4. Preserve anything useful before removing a retained worktree or branch. Ghost does not automatically reset or delete failed work.
5. For v0.2, use a new state directory for a clean registration after archiving the old one if you cannot safely reconcile the record. Keep the audit database. Do not edit audit events or fabricate a successful state.

This conservative recovery path is an MVP limitation. A structured `recover` command is on the roadmap.

## Inspect an uncertain push

`ghost publish ID` first verifies the configured remote identity and reads the exact remote ref. If it already equals the saved commit SHA, it marks the operation confirmed without pushing again. If another SHA is present, it stops. If the remote remains inaccessible, it preserves uncertainty. No force-push or automatic retry is used.

## Local data

The state directory contains policy, SQLite database/journal, locks and any retained worktrees. Proposal payloads include source snapshots and evidence. Audit events intentionally omit source text and raw command output. On POSIX, state is created with restrictive permissions; on Windows, protect the containing directory with account ACLs. Data is not encrypted by this application. Use OS disk encryption if required.

Resolved-proposal retention is currently manual. Stop all Ghost processes before archiving the entire state directory. Keep it intact while an uncertain commit or push exists. Deleting state loses duplicate suppression and audit history. Do not delete unrelated repository data.

## Reporting

Until a project-specific private security contact is published, avoid posting secrets or private repository content in public issues. The project owner should configure GitHub private vulnerability reporting before a public release. See ROADMAP.md for the release gate.
