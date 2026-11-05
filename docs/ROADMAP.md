# APRIL roadmap: Pi-first companion with desktop acceleration

## Updated goals: personal 3D companion

The latest preview implements managed on/off with private Ollama ownership,
model-only 3D wake popup/click-to-expand, explicit screen OCR, approved Python
file review/execution, a VS Code extension preview and dedicated CalDAV
read/reviewed-write/briefing paths. Read [ASSISTANT.md](ASSISTANT.md) for setup
and evidence. It is not a completed desktop/account acceptance claim.

Immediate goals:
1. Configure the existing readable model store and verify start/Goodbye/stop,
   off-until-manual-start behavior and actual login startup.
2. Accept the 3D popup on KDE/AMD; personalize the included Blender source or
   replace its GLB. Verify wake detection, microphone pause and cancellation.
3. Complete Google Desktop OAuth, initialize the private Radicale calendar and
   test bounded weekly/email/internship recaps plus reviewed event edits.
4. Accept explicit screen sharing, source-line diagnostics, constrained container
   execution and the optional VS Code debugger flow. Continuous screen monitoring,
   broad multi-language support and autonomous source edits are not implemented.
5. Then move always-on coordination/calendar to the Pi/home server, benchmark
   standalone inference, and add authenticated desktop acceleration/failure retry.

## Earlier desktop release foundation

The desktop proves the interaction architecture before hardware migration. Keep the photo-inspired 2D face and current local stack. Finish real timing/walkthrough evidence and physical Stop/retry acceptance; freeze optional features. Existing code is a loopback desktop server with a browser client and an optional native Qt tray/wake client. Native wake/hardware/login acceptance is pending; see WIDGET.md. It does not implement the future mode routing described below.

## Next: desktop acceptance and a useful daily briefing

Physically test the native wake/widget path, microphone pause, cancellation/retry
and actual desktop-login launch. Capture real walkthrough and timing evidence.
The optional widget's Qt and audio fixtures passed; that is not physical wake
acceptance. See [WIDGET.md](WIDGET.md) and [PROGRESS.md](PROGRESS.md).

Approved-folder retrieval and one desktop web lookup have been confirmed by
Enrique. Complete real Gmail consent/query acceptance, then implement read-only
Calendar access and one source-backed “brief me on my day” interaction. CalDAV/briefing code and authenticated calendar fixtures are now implemented;
personal OAuth/calendar acceptance and explicit editable memory remain pending.
Keep later write actions reviewable; do not grant arbitrary model shell access.

## Then: establish standalone Pi viability

Verify the actual Raspberry Pi OS 64-bit installation, storage, active cooling, microphone/output compatibility, power and available resources. Do not infer performance from 16 GB RAM alone. Measure small quantized CPU models with speech workloads running, increasing model size only when memory and latency permit. Reuse the current face and audio interface. One complete local spoken turn must work without desktop or Internet after model setup.

## After standalone viability: authenticated desktop acceleration

Move coordination to the Pi and add explicit local/desktop inference selection. Authenticate the desktop service, keep external exposure closed and show the selected mode. At turn start choose exactly one backend; never submit duplicate turns. If the desktop disappears mid-turn, report it and offer a local retry. Desktop-only actions remain unavailable offline. Test startup, shutdown, cancellation and connection loss before describing automatic fallback as working.

## Read-only grounding foundation; then useful bounded tools

The new opt-in foundation implements approved-folder lexical RAG, local SearXNG search, read-only Gmail OAuth, and spoken clock routing. Enrique confirmed approved-folder retrieval and a desktop web lookup; real Gmail authentication/mailbox acceptance remains pending. Keep initial file scope at `~/Documents/aprilfiles`; follow INTEGRATIONS.md for approved integrations. Treat file contents as untrusted data; exclude credential stores by default. Add Navidrome through its supported API after identifying the actual server, authentication and intended playback endpoint. File changes, deletion and other consequential operations require reviewable proposals/confirmation initially. No unrestricted root agent or arbitrary model-generated shell execution.

## Finally: robot appliance and physical presentation

Reliable startup/reconnect, device selection, full-screen face, graceful shutdown and explicit hardware controls come before enclosure polish. Use existing hardware for early tests; screen/USB audio/microphone purchases remain user decisions after compatibility checks. Movement is a separate later controller with limits and a stop mechanism. The model must not directly drive unbounded actuators.

PI.md documents the older authenticated browser-client tunnel experiment. It remains useful as an intermediate test, but a desktop-dependent tunnel is not the final standalone Pi design. Neither all-Pi GPT-OSS performance nor effortless hardware migration is promised.
