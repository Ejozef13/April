# APRIL roadmap: Pi-first companion with desktop acceleration

## Current: stabilize Desktop v0.1

The desktop proves the interaction architecture before hardware migration. Keep the photo-inspired 2D face and current local stack. Finish real timing/walkthrough evidence and physical Stop/retry acceptance; freeze optional features. Existing code is a loopback desktop server with a browser client. It does not implement the future mode routing described below.

## Next: establish standalone Pi viability

Verify the actual Raspberry Pi OS 64-bit installation, storage, active cooling, microphone/output compatibility, power and available resources. Do not infer performance from 16 GB RAM alone. Measure small quantized CPU models with speech workloads running, increasing model size only when memory and latency permit. Reuse the current face and audio interface. One complete local spoken turn must work without desktop or Internet after model setup.

## Then: authenticated desktop acceleration

Move coordination to the Pi and add explicit local/desktop inference selection. Authenticate the desktop service, keep external exposure closed and show the selected mode. At turn start choose exactly one backend; never submit duplicate turns. If the desktop disappears mid-turn, report it and offer a local retry. Desktop-only actions remain unavailable offline. Test startup, shutdown, cancellation and connection loss before describing automatic fallback as working.

## Read-only grounding foundation; then useful bounded tools

The new opt-in foundation implements approved-folder lexical RAG, selected SearXNG with optional Brave Search, read-only Gmail OAuth, and spoken clock routing. Fixture checks are separate from real authentication/private-data acceptance, which remains pending. Start live acceptance with only `~/Documents/aprilfiles`, then configured web/Gmail queries as described in INTEGRATIONS.md. Treat file contents as untrusted data; exclude credential stores by default. Add Navidrome through its supported API after identifying the actual server, authentication and intended playback endpoint. File changes, deletion and other consequential operations require reviewable proposals/confirmation initially. No unrestricted root agent or arbitrary model-generated shell execution.

## Finally: robot appliance and physical presentation

Reliable startup/reconnect, device selection, full-screen face, graceful shutdown and explicit hardware controls come before enclosure polish. Use existing hardware for early tests; screen/USB audio/microphone purchases remain user decisions after compatibility checks. Movement is a separate later controller with limits and a stop mechanism. The model must not directly drive unbounded actuators.

PI.md documents the older authenticated browser-client tunnel experiment. It remains useful as an intermediate test, but a desktop-dependent tunnel is not the final standalone Pi design. Neither all-Pi GPT-OSS performance nor effortless hardware migration is promised.
