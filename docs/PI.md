# Pi browser client and desktop server

This is an intermediate client/tunnel experiment. The revised final goal is standalone Pi inference plus authenticated desktop acceleration; see ROADMAP.md. That routing/fallback is future work, not a capability of this desktop release.

**Physical Pi validation is pending.** Its OS, 64-bit architecture, browser, audio stack, SSH client and connected hardware have not been observed. The user-provided 16 GB specification does not establish any of these. No dedicated display or audio purchase is required: start on the desktop, then use existing monitor/headphones only if the Pi actually supports them.

The client is the existing static browser UI; no heavy models run on the Pi. Verify on the Pi with `cat /etc/os-release`, `uname -m`, `command -v chromium`, and the OS audio-device listing (`wpctl status` on PipeWire, otherwise `arecord -l` / `aplay -l` when available). Do not assume the Pi has analog microphone input. A 3.5 mm adapter without a sound interface cannot add one.

1. Keep APRIL and Ollama bound to loopback on the desktop. Configure and test the complete live workflow there first.
2. Use an existing secured desktop SSH account with a key. Verify its host fingerprint independently; do not disable host-key checking. Do not add passwords or private keys to APRIL configuration.
3. From the Pi, replace `desktop-user` and `desktop-host` with your actual account and desktop LAN hostname:

   ```bash
   ssh -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
     -L 127.0.0.1:8765:127.0.0.1:8765 desktop-user@desktop-host
   ```

4. In the Pi browser, open its own loopback port 8765. The SSH tunnel authenticates and encrypts the hop. The browser sees localhost, which permits microphone access; plain HTTP to a LAN IP would not. Permit microphone access and select actual Pi input/output hardware. Do not forward Ollama or expose APRIL on `0.0.0.0`.
5. Verify a spoken turn, cancellation, mute, permission denial, tunnel loss and recovery. Confirm raw recordings and transcripts are not retained. Measure additional transport latency separately from server timing.

Restrict desktop SSH to the trusted LAN and authorized account using existing firewall/admin policy. This document does not configure a public listener, install SSH, create users, alter firewalls or weaken existing authentication. Verify no unwanted public port forwarding exists. If SSH is unavailable, that is a prerequisite to resolve explicitly, not a reason to remove authentication.

The SVG view scales to the browser viewport and can later be replaced with custom assets. Kiosk autostart, reconnect behavior, OS packaging and display/audio acceptance remain pending until the Pi OS and available devices are known.
