# Desktop v0.1 release notes

## Result

APRIL is a local push-to-talk voice companion with an original dog interface, bounded serial requests, replaceable local speech/model adapters and recovery controls. Enrique reported a real desktop voice interaction followed by five successful sessions. It is a desktop prototype release, not a completed Pi robot or autonomous system.

## Changes in this release

- `bash april.sh` defaults to live mode and performs read-only prerequisites first. It preserves local configuration and never changes shared services. Explicit `--simulation` and `--check` modes prevent accidental canned replies.
- Missing speech files, unreachable Ollama, unlisted models, generation failures and Piper output failures have actionable explanations. Generated WAV files are checked before browser playback.
- A photo-inspired original SVG replaces the generic terrier: tan head, darker folded ears, white muzzle/chest, dark collar and paw tag. The reference photograph is not redistributed. Full-screen face controls, mobile layout, reduced motion and a real captured-signal meter improve presentation.
- Timing JSON can be downloaded deliberately without audio, transcript, remote error bodies or reasoning. It records mode/settings and playback result; synthetic results remain labeled.
- Browser regression tests cover actual WAV-tone playback, permission retry, cleanup races, media-error preservation and Stop/retry. Python tests cover state, bounds, cancellation, process cleanup, protocol handling, readiness and recovery. Fixture checks remain separate from physical observations.

## Evidence and limitations

Release validation: 24 Python tests passed; the expanded simulation UI and WAV playback browser harnesses passed; setup repeated successfully; the wheel built with its required modules/assets; dependency, JavaScript/shell syntax, local documentation-link and diff checks passed. The new launcher completed a functional same-origin WebSocket turn after clean restart. These are cloud/fixture checks, not additional physical desktop runs.

The cloud cannot access Enrique's desktop microphone, GPU or running Ollama. The latest backend failure has not been diagnosed directly on that desktop; the launcher and runtime errors now identify likely missing prerequisites rather than obscuring them with a generic failure. Successful recovery from stopped Ollama is verified using a controlled fixture, not a claim that the remote desktop has been repaired automatically.

The source screenshot/video assets show labeled simulation. A live screenshot was shared in chat; audible speech and five successful sessions were user-reported. Numerical five-run samples, a real walkthrough video, confirmation of physical cancellation and return to Idle remain pending. No performance figure or new real recording was fabricated. Use DESKTOP_ACCEPTANCE.md to finish those checks before claiming a fully accepted hardware release.

Mouth motion indicates speaking state and is not audio-amplitude or phoneme synchronization. Factual model output can be inaccurate. No persistent memory, arbitrary shell execution, file access, Navidrome integration, Pi fallback, wake word, enclosure or movement is implemented.

## Upgrade on Enrique's desktop

Stop only APRIL with Ctrl+C:

```bash
cd ~/Projects/April
git pull --ff-only
bash april.sh
```

Hard-refresh the browser after updating. If prerequisites fail, follow the named repair step and rerun. Existing model files and `april.local.toml` are not replaced. Do not rerun system-wide Python installation or stop AM.

For an explicit UI-only demo: `bash april.sh --simulation`.
