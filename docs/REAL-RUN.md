# Real local model run — October 22, 2026

This is an integration record for one small sample, not a model benchmark.

| Item | Observed value |
|---|---|
| Application | Ghost Contributor 0.2.1 |
| Runtime | Linux, Python 3.12.14, Git 2.51.1 |
| Ollama | 0.40.8; local loopback API; cloud features disabled |
| Selected model | `qwen2.5-coder:7b`, Q4_K_M, 7.6B metadata |
| Model digest | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |
| Target | A missing docstring for `retry_delay` in a newly created sample Git repository |
| Dashboard run action | 47.633 seconds, including local generation and validation |
| Proposal | `2cadff97ef6e49d6` |
| Approved topic branch | `ghost/2cadff97ef6e49d6` |
| Resulting commit | `03d0d04fcaf0d3e791424783a5053c8f230bf039` |
| Original branch | `main`; original commit and source unchanged |
| Remote push | None |

The dashboard called the real local model, displayed its exact diff and evidence,
and completed explicit approval through the browser. Git branch/commit inspection
confirmed the result. The capture harness recorded the raw model response; it did
not substitute a fixture. The source, generated text, quotes, diff and identifiers
are included in `real-run-evidence.json`.

## Fix found during the run

Earlier trials copied display line-number prefixes into evidence quotes. Ghost
rejected those responses. In 0.2.1, prompt source lines carry separate
`line_number` and exact `text` fields, with explicit quoting instructions. Exact
source validation remains strict. The successful 7B response quoted four original
source lines correctly. The automated suite passed all 93 tests after the fix.

The generated paragraph accurately describes capped exponential retry delay for
this sample. One example does not establish the model's reliability on arbitrary
repositories. The user's seven installed models and Windows laptop were not
accessed or tested.

## Product film

The 45-second motion film uses screenshots from this successful run. The roughly
48-second generation wait is compressed and labelled "edited for time". Scene
transitions, branch graphics and emphasis are editorial animation. The narration
is synthetic Hinglish speech; no person was cloned. The music and interface
sounds were synthesized for this film. No remote publication occurred.
