# Model evaluation and reproducibility

Release 0.2.1 includes one successful real `qwen2.5-coder:7b` integration run on Linux, through dashboard review and a local Git commit; see [the run record](REAL-RUN.md). This is not a quality benchmark. Automated tests additionally use a clearly labelled deterministic sample generator and a local HTTP fixture implementing the Ollama response contract. Those fixtures test application behavior, not model reasoning or hallucination rate.

## Model choices to evaluate

| Exact tag | Catalog license | Catalog download size | Role |
|---|---|---|---|
| `qwen2.5-coder:1.5b` | Apache-2.0 | About 986 MB | Default small-model starting point |
| `qwen2.5-coder:7b` | Apache-2.0 | About 4.7 GB | Larger candidate for quality comparison |

Sources checked October 22, 2026: [1.5B tag](https://ollama.com/library/qwen2.5-coder:1.5b), [7B tag](https://ollama.com/library/qwen2.5-coder:7b). Download size is not total RAM/VRAM use. Context size, quantization, concurrency and system overhead affect memory. These are available choices, not a measured performance ranking.

The 3B family member displays a Qwen research license; do not assume every variant has the same terms. Record the actual `/api/show` license for any replacement tag. Application MIT licensing does not relicense model weights.

## First real-model evaluation

1. Configure Ollama local-only, install the exact model, run `ghost doctor`.
2. Create a scratch copy of 20 small functions you understand: validation, optional returns, async operations, exceptions, side effects and an intentionally ambiguous case. Keep repository/fixture licenses and provenance.
3. Run review-only proposals. Save actual model tag, digest, quantization, context budget, hardware, generation duration, prompt schema version and result.
4. Score each proposal with two independent human reviewers if possible. A source citation passing the application is not automatically a correct claim.
5. Publish the raw aggregate counts and evaluation procedure, including failures. Do not replace failed outputs or silently change the test set.

| Metric | Definition | Release target (not observed) |
|---|---|---|
| Schema acceptance | Valid response / all attempts | At least 95% on the chosen fixture set |
| Factual acceptance | No unsupported claims / reviewed outputs | At least 90% before broader rollout |
| Editing safety | Verified bounded transformations / accepted candidates | 100%; any unexpected executable edit blocks release |
| Review effort | Median human review seconds | Compare against writing the same docstring manually |
| Useful-change retention | Accepted changes still retained after 7 days | Report denominator and removals honestly |
| Latency | Median and p95 on declared hardware | Measure locally; do not infer from download size |

Use review mode for public projects until this evaluation is complete. For the challenge video, clearly distinguish a real Ollama run from the bundled fixture demo. If only the fixture is shown, label it honestly and do not claim the AI integration has been validated end to end.
