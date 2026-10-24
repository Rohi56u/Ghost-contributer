# Contributing

Use Python 3.11–3.13. Install `python -m pip install -e ".[dev]"` and run `python -m pytest -q`. Open a focused issue before broadening edit permissions or adding external services.

Every language/editor change needs a failure-focused fixture proving what cannot change: exact source bytes outside the intended span, encoding/newline behavior, ambiguous target refusal, idempotence and adversarial model output. Git changes need temporary repository/remote tests and an explicit crash or timeout path.

Do not add automatic force-pushes, synthetic author timestamps, empty commits, unrequested repository scans, cloud inference fallbacks, default-branch publication or model-generated shell commands. Respect reviewers' time. Do not manufacture activity for contribution graphs.

Keep fixtures free of real secrets and private code. Report model results with exact tags/digests and hardware. Distinguish stub tests from real inference and planned compatibility from observed CI results.
