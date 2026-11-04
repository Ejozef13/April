# Improving answers without assuming Internet fixes them

APRIL sends the latest question to local Ollama; earlier dialogue is not included automatically. Spoken time now routes to the real clock. Opt-in Brave Search, approved-folder retrieval and read-only Gmail adapters supply bounded excerpts when explicitly configured; they are not automatically connected to personal accounts. Navidrome and arbitrary desktop control remain unimplemented. Normal conversation can remain offline. See [INTEGRATIONS.md](INTEGRATIONS.md).

## Diagnose before replacing the model

Collect 2–3 inaccurate examples containing the intended question, visible transcript, exact answer, and expected answer with its source. Keep private examples out of public Git by default.

| Observation | Likely next investigation |
|---|---|
| Transcript differs from the spoken question | Microphone levels, recording clarity and STT; web access cannot repair an already misrecognized name reliably |
| Follow-up relies on earlier dialogue | Current requests are single-turn; consider a bounded, optional in-memory context with clear/reset controls, separate from persistent memory |
| Correct transcript, wrong stable fact | Evaluate model answers against a small sourced question set, then compare model/settings on accuracy and latency |
| Question asks about news/current availability | Add an explicit authenticated/configured search or data-source tool and show its sources and date |
| Question concerns personal files, music or the home server | Use narrowly configured read-only integrations, with source paths/API results; the model cannot infer your private system state |
| Reply ends abruptly | Inspect generation termination and final-answer budget before assuming more connectivity will help |

The current prompt asks April to admit uncertainty, but that is not a factual guarantee. No measured accuracy score or confirmed cause of Enrique's reported errors is available yet. Increasing model size or reasoning effort can increase latency and is not automatically a fix.

## Grounded tools later

For online answers, a search/retrieval tool must actually fetch results before April claims to have checked them. Retain citations/source dates, distinguish retrieved facts from generated advice, and report unavailable or conflicting results. Treat downloaded pages and documents as untrusted data, never instructions to execute commands or expose credentials. Keep the same UI and offline fallback when the service is unavailable.

Start with one useful source and a small evaluation set. Do not enable unrestricted browser/system access or connect the Pi to a public command endpoint. Navidrome should use its supported API and an explicitly chosen playback device; it does not require general-purpose web browsing.

## Near-term priorities

1. Review actual wrong-answer examples; finish real timing exports, cancellation/retry observations and a short live walkthrough.
2. Implement/evaluate the smallest missing context or grounded-data capability supported by those examples.
3. Verify the Pi OS/hardware and benchmark small local models with speech active, then add authenticated desktop acceleration. Offline Pi usefulness remains a requirement.


## Text-only baseline

Stop APRIL’s voice server for this run; do not stop shared Ollama or AM. This isolates model output from capture/recognition/synthesis and does not invoke the retrieval coordinator:

```bash
.venv/bin/python -m april.evaluate --output artifacts/accuracy-baseline.jsonl
```

Six public test cases cover stable facts, programming and honest capability limits. Each saved final answer remains **unreviewed** until a person compares it with the rubric/reference. A completed HTTP request is not a passing answer. The runner records failed/unrun cases, never emits an accuracy score, excludes reasoning and audio, refuses simulation, and never overwrites a report. It stops early on an unavailable/rejected service rather than retrying the same failure. Output is deliberately retained locally and ignored by Git. Use a new output filename for another run.

Reference links are reviewer starting points, not a claim that pages were freshly fetched during the baseline. Times include any model loading and exclude speech; loading conditions default to unknown. Keep actual failure examples separate from this standard test set. No real accuracy results have been measured by adding the runner.
