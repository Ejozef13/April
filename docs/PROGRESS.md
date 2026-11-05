# APRIL development progression

This record follows the repository's commits, not an invented release schedule.
It separates implementation, automated fixtures and Enrique's real desktop
observations. The current README is the entry point; [VALIDATION.md](VALIDATION.md)
contains the detailed evidence and limits.

## 1. First complete desktop slice

**[a6736c3](https://github.com/Ejozef13/April/commit/a6736c3)** —
local backend adapters, explicit simulation and the first companion prototype.

- Established the Python coordinator, loopback browser interface and dog face.
- Separated recording, speech recognition, model access, synthesis, state and
  configuration so each stage could be understood and replaced.
- Added distinct idle/listening/transcribing/thinking/speaking/error states,
  bounded jobs, one active interaction, cancellation and failure recovery.
- Used labeled simulation for UI work without claiming real audio/model output.

**[16b71c7](https://github.com/Ejozef13/April/commit/16b71c7)** —
a GPT-OSS desktop profile and configurable reasoning/generation budget.

The desktop choice became CPU whisper.cpp and Piper with the already-available
GPT-OSS 20B through Ollama. This avoided assuming CUDA on the AMD machine and
kept speech off the GPU. A desktop screenshot showed GPU placement; it did not
establish driver certification or performance under concurrent workloads.

## 2. Real voice interaction and playback recovery

**[c67dcf7](https://github.com/Ejozef13/April/commit/c67dcf7)** —
fixed playback-cleanup races and added explicit audio retry.

A mounted audio element, invalidated stale playback promises and actual playback
acknowledgments keep the face aligned with I/O. Blocked autoplay can be retried
without regenerating the reply. Stop/retry and injected playback faults are
covered by browser fixtures.

**[f0ab74f](https://github.com/Ejozef13/April/commit/f0ab74f)** —
recorded the successful desktop demo and prepared evidence collection.

Enrique reported five successful real spoken sessions. That supports a working
desktop voice pipeline; the five timing JSON samples, real walkthrough recording
and separately measured physical cancellation were not supplied. Simulation
media remains explicitly labeled.

## 3. Desktop release foundation

**[f5ce84f](https://github.com/Ejozef13/April/commit/f5ce84f)** —
photo-inspired April, checked startup and actionable recovery; the existing
**v0.1.0** tag points to this milestone.

The one-command launcher preserves local settings and checks speech binaries,
model files and configured Ollama availability. Clear errors distinguish
missing/unavailable components. Timing export excludes transcripts/audio and
marks unknown loading conditions honestly. Setup, architecture, troubleshooting,
hardware limits, acceptance and interview documentation were added.

The tag predates later retrieval and widget features. It is not moved to imply
that those features were already part of the original release.

## 4. April's visual identity and animation iterations

The interface changed to match the supplied AM reference and real dog photos:
tan forehead, dark folded ears, white muzzle/chest, purple collar, animated
green circuit traces and a short brown tail with a white tip. The source photos
were not bundled, and the artwork remains code-rendered SVG/CSS.

| Commit | Design progression |
|---|---|
| [282c97e](https://github.com/Ejozef13/April/commit/282c97e) | AM circuit theme and purple-collar portrait proportions |
| [e88bbed](https://github.com/Ejozef13/April/commit/e88bbed) | Plain white chest and input/playback-driven white-tipped tail |
| [e8dceb1](https://github.com/Ejozef13/April/commit/e8dceb1) | Shorter, lower, fur-edged tail |
| [9233be8](https://github.com/Ejozef13/April/commit/9233be8) | Upright reference silhouette with brown base |
| [e80a10c](https://github.com/Ejozef13/April/commit/e80a10c) | Final shorter tip with angled top, preserving width |

The tongue appears during listening/thinking; idle uses a closed mouth. Tail
motion follows input level or actual reply playback and respects reduced motion.
Neither facial expressions nor animations expose a model's internal reasoning.

[Browser simulation](evidence/simulation-idle.png) ·
[Face view](evidence/simulation-face-view.png) ·
[Simulation walkthrough](evidence/simulation-walkthrough.webm)

## 5. From stale answers to bounded, read-only retrieval

**[12a9cb2](https://github.com/Ejozef13/April/commit/12a9cb2)** —
spoken clock routing, document RAG and read-only web/Gmail foundations.

This addressed two reported problems: a stale presidential answer and inability
to state the time. Recognized clock requests now call the actual clock.
Approved-folder retrieval uses SQLite FTS5 over bounded text chunks. It is lexical
RAG over pretrained-model inputs, not embedding training or fine-tuning.

The document boundary excludes symlinks, hidden files, obvious credential stores
and unsupported formats. A private local index stores excerpts only from approved
roots; source documents are not modified. Enrique confirmed that retrieval could
access his approved `~/Documents/aprilfiles` folder.

Read-only Gmail uses local Desktop OAuth, PKCE/state and bounded message reads.
Its fixtures passed; personal Google consent and real mailbox queries remain
pending. No sending/deleting, attachments, background mailbox crawl, arbitrary
shell execution or unrestricted desktop-file access were added.

## 6. Subscription-free web search and honest lookup status

**[835611d](https://github.com/Ejozef13/April/commit/835611d)** —
introduced a pinned, private SearXNG service.

The dedicated container publishes only on loopback, runs with limited CPU/RAM
and privileges, and has no GPU, mailbox, approved-document or Docker-socket mount.
Helpers preserve existing search settings and operate only on APRIL Search.

**[f792d5f](https://github.com/Ejozef13/April/commit/f792d5f)** —
automatic web lookup for ordinary live questions and visible retrieval status.

The router recognizes “check on the internet” as well as explicit search phrases.
Clock and private requests retain dedicated routes. Actual excerpts and sources
are displayed separately from the model answer. Failed/empty searches do not
silently fall back to unsupported model facts. Common private cues suppress
automatic web lookup; this is a heuristic, not a universal secret detector.

**[35c0043](https://github.com/Ejozef13/April/commit/35c0043)** —
removed the retired paid search adapter, key settings and setup commands; added
`bash april.sh --with-search`.

SearXNG is now the only web adapter. Its working public-engine selection was
preserved. Ordinary question text can go to upstream engines; private retrieval
excerpts are not automatically sent as search queries.

**Real desktop evidence:** after resolving Docker startup/socket access and
starting Ollama, Enrique supplied a screenshot showing three League of Legends
sources and a reply citing them. That establishes a successful lookup, not a
general factual-accuracy score. A later request timed out despite local health;
Enrique identified his campus/Cisco network as a possible cause, but controlled
confirmation was not recorded. Health alone never guarantees upstream access.

## 7. Optional “Hey April” native companion

**[06d77c7](https://github.com/Ejozef13/April/commit/06d77c7)** —
tray widget, CPU wake-phrase listener and opt-in desktop-login startup.

- QtWebEngine reuses the existing face, request states and audio playback path.
- A constrained Vosk recognizer listens locally for configured wake phrases;
  command transcription still uses Whisper.
- Native capture has silence/no-speech/max-length bounds. Capture pauses during
  processing/playback and rearms after a cooldown.
- Generation checks reject stale audio. Native input level drives the tail.
- Manual Record, microphone pause, dismiss/restore and quit remain accessible.
- An explicit installer writes only APRIL's managed XDG autostart entry.
  It does not modify the user's actual PC from the cloud.

[Actual native simulation capture](evidence/widget-simulation.png) ·
[Installation, licenses, controls and acceptance](WIDGET.md)

**Evidence boundary:** the Qt client and bridge passed real offscreen-window
tests. Audio-worker tests used fake PortAudio/Vosk. The official wake-model site
returned 403 in the cloud, and native hardware was unavailable. Physical wake
accuracy, missed/false activations, microphone compatibility, output, KDE
focus/tray and actual login startup are still pending.

Vosk is an older pretrained streaming recognizer used for constrained phrase
matching; no new wake model was trained or benchmarked.

## 8. Native shutdown and restart reliability

**[aae9d90](https://github.com/Ejozef13/April/commit/aae9d90)** —
clean terminal/login termination and reproducible lifecycle checks.

Explicit Quit exits rather than following close-to-tray behavior. Signal handlers
defer GUI exit to a normal Qt callback. Cleanup stops the owned microphone/server
and leaves shared Ollama/Docker/search services intact. The port probe permits
immediate restart after an earlier server closes.

Actual simulation launcher processes exited with status 0 on both SIGINT and
SIGTERM, and their owned servers became unreachable afterwards.
`scripts/widget_lifecycle_check.py` reproduces this check.

## Current evidence inventory

| Evidence | Scope |
|---|---|
| Five successful voice sessions reported by Enrique | Real desktop interaction; repeated numeric timing samples absent |
| GPT-OSS GPU-placement screenshot | Reported placement on the supplied desktop; no performance certification |
| Approved-folder retrieval confirmation | User-reported access to the configured folder |
| Three retrieved web sources and cited reply | One real desktop lookup; no overall accuracy claim |
| 58 unit tests | Latest recorded full run; deterministic fixtures, including optional native worker tests |
| Chromium regression checks | WAV-tone playback, autoplay retry, stale promises, error preservation, cancellation/retry and source rendering |
| Actual Qt simulation checks | Native window, compact face, simulated reply, WAV bridge, stale-audio rejection, level animation and dismiss/restore |
| Actual launcher lifecycle checks | SIGINT/SIGTERM shutdown and owned-server release in simulation |
| Bundled screenshots/video | Clearly labeled simulation; no personal photos, email or indexed documents |
| Hardware benchmarks and real walkthrough | Pending; templates are not measurements |

The optional worker test is skipped if native dependencies are absent. Install
`requirements-desktop.lock` to reproduce the full native fixture coverage.
Counts are historical validation results, not a claim of a configured GitHub
Actions pipeline.

## Next, with explicit completion criteria

1. **Accept the widget on the desktop.** Check ten intentional wakes, five minutes
   of background sound, native audio routing, dismiss/Stop followed by retry,
   microphone pause and real login startup. Record failures as well as successes.
2. **Complete portfolio evidence.** Capture a real walkthrough and timing JSON
   samples with documented hardware/loading conditions. Publish only reviewed,
   non-private artifacts.
3. **Read-only personal assistant.** Complete Gmail consent/query acceptance;
   implement Calendar read access and a source-backed daily briefing. Explicit
   editable memory and reviewable write actions are later work.
4. **Standalone Pi viability.** Verify the actual OS, power, cooling, storage and
   audio; benchmark smaller local models with speech running. RAM alone does not
   establish responsiveness.
5. **Authenticated desktop acceleration.** Choose one inference backend per turn,
   expose no public unauthenticated endpoints, and test desktop loss/retry.
   Mark desktop-only tools/files unavailable while the PC is off.
6. **Robot integration.** Reuse existing peripherals first. Screen, USB audio,
   enclosure and any physical motion require compatibility checks and separate
   bounded controllers.

[ROADMAP.md](ROADMAP.md) explains the target architecture; [PI.md](PI.md) describes
only the earlier tunnel experiment. Neither is evidence that Pi inference,
automatic fallback, Calendar, personal memory or Navidrome already works.
