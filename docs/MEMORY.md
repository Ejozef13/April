# April's personality and private memory

April's conversational persona is a cheerful female Jack Russell: affectionate,
playful, loyal, and eager to make your day easier. Loyalty means honest help,
including gentle correction, rather than invented certainty or agreement with
everything. She does not claim consciousness, actual feelings, perfect recall,
or access/actions she has not been given. Natural follow-ups such as “tell me more” use actual recent context, including
previous source-backed answers, without launching an unrelated new web search.
Historical answers do not establish fresh external facts. This uses the existing pretrained
local model, not training or fine-tuning. The persona is defined in
`april/memory.py` and supplied by the Ollama adapter on every answer.

## Start using memory

Pull the update and restart April using your existing configured launcher:

```bash
cd ~/Projects/April
git pull --ff-only
bash april.sh start
```

If managed private Ollama has not been configured, finish the existing model-store
setup in [ASSISTANT.md](ASSISTANT.md) first. This update does not download models,
change your model store, connect Gmail or install Obsidian.

Memory is enabled by default in **live** mode; simulation never reads or writes
the personal vault. No new Python dependencies or embedding model are required.
Optional settings in ignored `april.local.toml`:

```toml
conversation_history_turns = 12
conversation_context_turns = 6
conversation_idle_minutes = 30
memory_max_notes = 500
memory_enabled = true
memory_vault = "~/.local/share/april/memory"
proactive_briefings = false
briefing_hour = 9
timezone = "America/New_York"
```

Edit existing keys rather than duplicating TOML keys. Restart after configuration
changes. `memory_enabled = false` disables recall, automatic extraction, memory
commands and memory notifications; it preserves existing notes. Explicitly clear
notes before disabling if you want them deleted.

Try:

- “April, remember this: I prefer hints before full coding solutions.”
- “What do you remember about me?”
- “Forget I prefer hints before full coding solutions.”
- “Don't remember this conversation.”
- “Start a new conversation.”
- “Remind me in 20 minutes to review my internship application.”

Forget matches a full saved summary or its ID; it never guesses which unrelated
note to delete. The **My memories** panel lists notes with their origin, date,
certainty and supporting user quote. Select a note to edit it, change its category,
review an inferred candidate or delete its ID. To approve an inferred note, select
it, change its category from Pending review to Profile/Preferences/Projects and
save. Explicitly saved/reviewed notes are protected from automatic replacement.
“Forget everything” or typing **FORGET ALL** in the panel removes all Markdown
notes in the managed category folders and refreshes the index.

The private-conversation control cancels queued extraction, clears short-term
context and removes notes associated with the current view's conversation ID,
including explicitly saved notes from that conversation. Subsequent turns in that
view neither recall nor save memories. Start a new conversation to resume.
This switch applies to the current connection; reopening the view/restarting
starts a new conversation. Other views have their own private switch. Memory is
for one trusted desktop user, not a multi-user account system.

## How automatic memory works

1. Successful plain and source-backed conversations retain up to 12 short
   user/assistant turn pairs in RAM, with up to six supplied as bounded context.
   After 30 minutes of inactivity, that recent RAM context expires. Turn pairs are not archived to disk. Retrieved snippets, message bodies and
   screen images themselves are not added to RAM history; only the visible
   question/answer is retained locally. A private conversation disables this too.
2. A conservative first-person/personal-statement filter selects turns that may
   contain lasting preferences, profile facts or project updates. Trivia,
   greetings and most questions do not trigger extraction.
3. After speech synthesis succeeds, a bounded background request asks the same
   **local Ollama** model for at most three short notes. It sees only that user
   statement, not the assistant's reply, web results, file/code context, screen
   OCR, Gmail or calendar excerpts. Explicit private/retrieval actions are excluded.
4. Category, length, ID, sensitive-data patterns and a verbatim supporting user
   quote are checked. Unsupported quotes are rejected. Inferred notes go to
   `pending/` and are never recalled until reviewed. Model-classified “stated”
   notes can still be wrong; the quote is provenance, not proof of semantic truth.
5. Stable topic IDs update previous automatic notes; exact duplicates are skipped.
   Explicit notes win over automatic updates. Different IDs can still conflict;
   inspect/edit/delete them in My memories rather than assuming perfect conflict
   resolution. A short recent summary is assembled only from saved user facts,
   not model-generated claims about what happened.
6. On a later question, the Markdown notes rebuild a small SQLite lexical index.
   Relevant project notes plus bounded profile/preferences/recent notes and
   recent RAM turns are attached as **untrusted personal context** to the local
   model. They do not authorize tool calls or replace current factual evidence.
   This is lexical retrieval, not semantic embedding search.

Extraction is limited to two queued jobs, 25 seconds per job and 500 managed
notes by default. The local model serializes foreground and extraction requests; extraction
may add latency to the next turn, especially on a Pi. Queue pressure skips a
save rather than building an unbounded backlog. The memory status line shows context use and analysis progress; open My memories
to see the latest extraction failure/queue notice; use “Remember this” for reliable explicit
storage when automatic analysis fails. No live-model extraction accuracy or Pi
latency is claimed by the fixture tests.

For CachyOS installation, shared local agents and scoped cloud snapshots,
see [OBSIDIAN.md](OBSIDIAN.md).

## Obsidian and portable Markdown

Obsidian is an optional editor; it does not need to run. It is free for personal
use but is not open source. April reads/writes Markdown directly, so any text
editor works. First create/read the vault:

```bash
.venv/bin/python -m april.memory list
.venv/bin/python -m april.memory path
```

In Obsidian, choose **Open folder as vault** and select the printed directory.
Do not turn on third-party sync/plugins for personal notes without considering
where they send your data. The managed structure is:

```text
~/.local/share/april/memory/
  profile/        # Stable user facts
  preferences/    # How you like April to help
  projects/       # Ongoing work, tasks and optional timed reminders
  recent/         # Short supported personal-context summary
  pending/        # Inferences awaiting your review
  .index.sqlite3  # Disposable local index; not the source of truth
```

Each note has an APRIL metadata comment, a heading and a short summary. Edit the
summary below the heading while preserving the metadata comment and blank line.
The next retrieval or panel refresh sees edits/deletions and rebuilds the index.
Malformed/oversized/sensitive-pattern notes are excluded. Do not copy notes
between category folders without removing the old copy; duplicate IDs are ignored.
The app editor is the easiest way to change category safely. A pending note moved
to a recalled category is treated as your review; retain an accurate certainty
label in metadata, or use the app editor to mark it explicitly stated.

CLI alternatives (printed output is private):

```bash
.venv/bin/python -m april.memory remember 'I prefer concise Python examples.'
.venv/bin/python -m april.memory forget note-ID-FROM-THE-LIST
```

Use a real local directory outside Git; vault/folder/index symlinks are refused.
April creates a private directory and atomic private note files. The SQLite index
uses secure deletion when rebuilding. This is not disk encryption or guaranteed
forensic erasure: external copies, filesystem snapshots, backups, exported notes
and Obsidian sync are outside April's deletion control. Secrets are blocked by
conservative patterns, not a complete sensitive-data detector. Never store
passwords, credentials or highly sensitive records here. Memories are not uploaded
to GitHub, embedded in the application, or appended to public web queries.

## Briefings, reminders and follow-ups

Saving a note with an explicit timezone-aware reminder time opts that note into
local popup notifications. The relative voice command accepts minutes, hours or
days (one minute to one year). Use the panel for an exact timestamp. To complete
or cancel a reminder, clear its reminder time and save, or delete the note. A
notification is delivered once per note revision; editing a reminder makes it a
new revision.

Set `proactive_briefings = true` to enable a daily invitation to open your recap,
after `briefing_hour` in the configured timezone. The timer checks every 30 seconds
and waits until April is idle with a connected UI. A native widget is preferred;
otherwise a browser view receives the notice. It opens controls rather than
speaking private information aloud. Email/calendar are fetched **only when you
request** the existing recap, which still requires Gmail/CalDAV setup. Saved
project context can personalize that response; it does not prove an email arrived
or an event exists. A reminder is a local note, not a CalDAV event; calendar edits
still need their existing separate review.

Notifications work only while the April server and a UI are running. If April
was off at the due time, an overdue reminder appears after restart. This is not
an OS alarm clock, push service or autonomous background email watcher. Daily
and reminder delivery IDs persist locally to limit duplicates after restart.
Local notifications are user-requested follow-ups; arbitrary proactive agent
actions and automatic calendar/email writes are not enabled.

## Desktop and Pi continuity

The same Markdown format and SQLite/standard-library implementation can run on
both architectures. **Automatic authenticated desktop/Pi synchronization, shared
RAM history, conflict resolution between devices and offline offload remain next
milestones**, pending physical Pi setup. Do not concurrently sync the live SQLite
index. A future authenticated sync should transfer selected Markdown notes and
rebuild the index independently on each device, with deletion tombstones so
forgotten memories do not reappear from an offline device. No personal memories
were seeded from this development chat or committed to the repository.

## Validation

Run `python -m unittest discover -s tests` and, with Playwright/Chromium installed,
`python scripts/memory_browser_check.py`. The fixtures verify real local Markdown
and SQLite behavior, editing/restart recall, deletion, cancelled extraction,
pending inference exclusion, explicit-note priority, context bounds, local model
request structure, private-mode routing and once-only notification state. Browser
checks exercise actual save/reload/edit/delete and private/new controls using a
temporary vault and fixture voice/model. They are not personal-account, actual
Ollama inference, physical microphone or Pi acceptance results.
