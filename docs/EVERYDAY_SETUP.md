# Everyday desktop companion: login, conversation, calendar and Gmail

This sequence applies the new settings **on Enrique's CachyOS desktop**. The
cloud development workspace cannot install a desktop-login entry, access his
model store or complete Google consent remotely. Existing Hey April and explicit
Obsidian memory were confirmed by Enrique; the managed sequence below and the
actual automatic-memory extraction quality still need desktop acceptance.

## 1. Prepare and register managed startup

Stop the old foreground widget with Ctrl+C in its terminal (or Quit from its
tray menu). If using managed April already, `bash april.sh stop --wait` stops
that owned runtime. Do not start a second website/widget alongside managed April.

```bash
cd ~/Projects/April
git pull --ff-only
bash scripts/setup_assistant.sh
sudo systemctl enable --now docker
sudo systemctl start ollama
bash april.sh setup --login
```

The setup command asks the existing local Ollama API for the configured model's
blob location and validates the containing `blobs/` + `manifests/` store. It
prepares private Ollama on port 11435, registers April's XDG login launcher and
preserves unrelated device/account/model/voice settings and TOML comments. No
model is downloaded, no shared Ollama/AM service is stopped, and no model-file
permissions are changed. Your existing shared Ollama is started here only to
inspect its installed model metadata; April owns a separate process at runtime.

If discovery fails, the setup stops rather than guessing. Check
`ollama show gpt-oss:20b --modelfile | rg '^FROM '` and give setup the actual
readable parent model store with `--model-store /actual/store`. Do not pass the
individual blob file or blindly change ownership of a shared service's files.

The desktop conversation preset enables memory, allows 25-second commands and
1.4-second pauses, retains 12 recent turn pairs in RAM, uses up to six recent
pairs within the prompt budget, clears them after 30 minutes of inactivity, and
allows 500 selected durable summaries. Existing memories are preserved. Only
these settings are intentionally adjusted. Model context is raised to 4096 if
smaller; a larger existing context is preserved.

Private Ollama keeps April's model warm for up to five idle minutes to make
follow-up conversation quicker. Off terminates that private process. Use
`private_ollama_keep_alive_seconds = 0` for immediate idle unloading, or adjust
within 0–3600 seconds. Keeping a model warm occupies VRAM; concurrent AM workloads
can still contend for the same GPU. No benchmarked latency guarantee is implied.

## 2. Initialize and verify your self-hosted calendar

The optional assistant dependencies installed above include Radicale and the
calendar libraries. Run:

```bash
.venv/bin/python -m april.calendar_setup setup
```

This generates private local credentials/config only if they do not already
exist, temporarily starts a loopback-only Radicale server, creates only the
missing dedicated `/april/assistant/` calendar, verifies an authenticated seven-day
read and stops the temporary server. Existing events and existing setup files
are preserved. If a configured server is already running it is verified in
place; the helper does not stop a process it did not create. Stop a manual
calendar server before managed April takes over its local port.

The calendar is self-hosted on this desktop for now. It remains inaccessible
while the desktop is off until a future Pi/home-server migration. The localhost
URL is not exposed to the Internet or automatically shared with the Pi.

## 3. Start, verify and switch fully off

```bash
bash april.sh start --wait
bash april.sh status
.venv/bin/python -m april.calendar_setup check
```

`start --wait` reports ready only after the owned local model endpoint, search
startup, configured authenticated calendar and native app HTTP endpoint have
started. This is runtime readiness, not proof of model inference, mic operation
or Internet engine access. `status` shows startup phases and distinguishes
Starting, Running, Stopping and Off. Failure details remain in the bounded private
`artifacts/power.log`; never paste credentials or token files into chat.

On the physical desktop:

1. Say “Hey April,” pause for the popup and say “How was your day?” Check that she
   replies conversationally instead of doing a web lookup.
2. Ask a public factual question, then say Hey April again and “Tell me more.”
   The follow-up should continue the prior topic using local RAM context.
3. Say “Goodbye April” while idle. Wait for the tray/window to close. Check
   `bash april.sh status`: it should report Off and login startup paused.
4. Log out/back in or reboot. April should remain off after Goodbye. Start her
   manually with `bash april.sh start --wait`; that clears the off marker.
5. On a later normal login without Goodbye/Off, April should launch automatically.

The new login entry replaces only an APRIL-managed entry. It starts after GUI
login, not before login. The terminal can be closed after managed start returns.
The root Docker daemon remains a shared service; only April's dedicated search
container, calendar process, private Ollama, native UI and server are stopped.
An independently launched IDE debugger remains user work and is preserved.
A microphone pause or Dismiss is not Off. Voice detection is half-duplex; use
the Off button or `bash april.sh stop --wait` while April is speaking.

## 4. Accept automatic memory and privacy controls

Explicit Remember this already works on this desktop. Test automatic extraction
separately with an ordinary statement, for example:

> “I usually study Python in the evenings, and I prefer small practice problems.”

After April replies, watch the memory status line and inspect My memories or
Obsidian. The local model may select a short preference/profile/project note.
Inferred notes stay in Pending review until approved. Ask “What do you know
about my study preferences?” and check recall after restarting the app.
A supporting quote is provenance, not proof the model summarized correctly.

Then test:

> “Don't remember this conversation.”

The current conversation's queued/saved notes and shared recent RAM context are
cleared, and further turns in that view neither save nor recall memory. Say
“Start a new conversation” to resume, or start a new connection. Private mode is
per view, not a system-wide multi-user privacy boundary. “Forget everything”
clears the managed note folders; do not use it unless that is what you intend.

Automatic extraction sees only selected plain user statements. Web snippets,
Gmail/calendar excerpts and screen/code data are excluded from durable extraction.
Visible source-backed answers may remain in bounded local RAM for follow-up
conversation, with provenance marked as historical context; they are not fresh
verification or automatic action permission. Nothing here archives whole chats
or trains the model. See [MEMORY.md](MEMORY.md) for limits and Obsidian editing.

## 5. Complete Google consent on your desktop

This is an OAuth **reader**, not sending/deleting mail. Google browser consent
cannot be performed by this repository or the cloud assistant for you.

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create or
   select a dedicated APRIL project.
2. Under APIs & Services, enable **Gmail API** for that project.
3. Open **Google Auth Platform / OAuth consent screen**. Use the app name APRIL
   and your own support/contact email. For a personal Gmail account, choose
   External, keep the app in Testing and add your own Gmail address as a test
   user. Workspace users may have organization/admin restrictions.
4. In Data access/Scopes, configure only
   `https://www.googleapis.com/auth/gmail.readonly`. No Gmail send/modify scope is
   needed. Do not confuse this with the separate self-hosted CalDAV calendar.
5. Under Clients/Credentials, create an **OAuth client ID → Desktop app**, name it
   APRIL Desktop and download the JSON. A web-app client is not the expected type.
6. In your file manager, move the downloaded JSON outside Git and aprilfiles,
   to `~/.config/april/google-client.json`. Do not upload its contents to chat.

Then, from the desktop terminal in `~/Projects/April`:

```bash
chmod 600 ~/.config/april/google-client.json
.venv/bin/python -m april.gmail connect --client ~/.config/april/google-client.json
```

The command opens Google's browser consent using an ephemeral loopback callback
and PKCE. Select your own test account and review/approve the read-only grant.
If consent is blocked, check the chosen project, test user, Gmail API enablement
and account policy instead of broadening scopes or sharing credentials.
Testing-mode grants may require reauthorization later.

Verify:

```bash
.venv/bin/python -m april.gmail check
```

This checks authenticated profile metadata without printing your address or
reading message bodies. The token stays in private local storage outside Git.
To test actual useful retrieval, ask April “Summarize my emails,” then “What do
I have planned today?” or use Calendar + email recap. Searches are bounded, not
an exhaustive inbox audit. Calendar writes require the separate review UI. Mail
is never automatically sent, deleted or turned into permanent memories.

Disconnect with `python -m april.gmail disconnect`, and revoke the grant in your
Google account too if you want it invalidated remotely.

## Verification evidence and limits

The full automated suite plus actual owned-process lifecycle and authenticated
Radicale fixtures exercise this implementation. Fixtures use fake model/widget/
search services and public temporary calendar data; they do not install anything
on Enrique's desktop or establish personal Gmail consent. Actual login/reboot,
microphone/Goodbye, automatic memory accuracy, private GPU inference and the
personal-account recap remain acceptance checks above. Pi synchronization and
offline inference are separate later milestones.
