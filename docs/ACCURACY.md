# Improving answers without assuming Internet fixes them

APRIL's desktop can be connected to the Internet while the model itself has no browsing capability. The current application sends the latest transcript and a short system instruction to local Ollama. It does not search the web, retrieve desktop files, query Navidrome, or include earlier conversational turns. Those capabilities must be implemented explicitly. Normal conversation can remain offline.

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
