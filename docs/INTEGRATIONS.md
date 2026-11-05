# Read-only web, April files and Gmail

These integrations are implemented as opt-in adapters. Temporary-file/API fixtures and browser tests exercise their boundaries; personal Google OAuth credentials and files are not available in the cloud. Enrique has verified desktop folder retrieval and SearXNG web lookup; Gmail consent and mailbox queries remain pending.

## 1. Voice time works without Internet

“April, what time is it?” and “Tell me the time” now route to the deterministic clock after transcription. The visible transcript is preserved, no model answer is requested, and Piper speaks the actual clock/date in the configured timezone. The clock button still works. This is not a general timezone parser; change the trusted `timezone` setting for the desired local zone.

## 2. Approve only Documents/aprilfiles

Stop the APRIL application with Ctrl+C, leaving AM/Ollama intact. From the project root:

```bash
.venv/bin/python -m april.integrations documents --folder ~/Documents/aprilfiles
```

This creates the explicitly requested folder if necessary and appends its absolute path to `document_roots` in ignored `april.local.toml`. Existing settings are preserved; conflicting roots are not broadened or silently overwritten. If that setting already exists with other values, review it manually.

Copy a few documents you want APRIL to read into this folder, then index:

```bash
.venv/bin/python -m april.documents index
bash april.sh
```

Ask **“April, search my files for purple collar”**, using a phrase actually present in your own documents. Or type a query and choose **Search April files** in the search panel. Open Retrieved sources to review the filenames and excerpts supporting the generated response.

Supported initial formats are UTF-8 `.txt`, `.md`, `.rst`, `.csv`, `.json`, and `.py`. PDF, Word, images, archives and OCR are not supported. This is lexical retrieval with SQLite FTS5 and bounded overlapping text chunks, then local-model generation: a simple RAG system, not embedding search or model training. Retrieval can miss synonyms, and citations do not prove every generated claim.

Only configured folders are scanned. Hidden files/directories, symlinks, common build/cache folders, obvious credential filenames, private-key headers and selected credential JSON fields are skipped. These exclusions cannot identify every secret inside an ordinary text file: curate the folder first. Source files are never modified. The default limits are 1000 indexed files, 1 MB per file and 5000 chunks; queries retrieve at most three excerpts.

The index at ignored `artifacts/documents.sqlite3` persists private excerpts locally with file mode 600. It is not encrypted. Rebuild after edits/deletions; the index is a snapshot, not a file watcher. Changing/revoking approved roots blocks use of the old index until rebuilding. To remove access, clear `document_roots`, stop/restart APRIL, and remove your specific APRIL index file if you no longer want its stored excerpts. Deletion does not promise secure erasure from SSDs/backups. Never publish the index.

## 3. Web search with SearXNG

SearXNG is APRIL's only web search integration. It needs no search API account,
key or subscription. See [SEARXNG.md](SEARXNG.md) for local Docker setup.

```bash
bash april.sh --with-search
```

Ordinary live questions automatically retrieve up to three snippets before local
generation. Clock requests and private file/Gmail routes stay dedicated.
Common private cues suppress automatic web search; this heuristic cannot detect
every sensitive prompt. Never include secrets in an ordinary web question.

The search service sends queries to upstream engines. Retrieved document/Gmail
excerpts are never automatically forwarded as web queries. APRIL displays the
actual URLs/excerpts separately from generated prose. It does not independently
fetch full pages or guarantee that sources are correct or current. Failed or
empty searches do not fall back to an unsupported model answer.

Set `automatic_web_search = false` in ignored `april.local.toml` for local
conversation with explicit search controls; current-fact guards still require
retrieval. Restart after changing configuration. A configured endpoint is not
proof of successful search: verify a question and review Retrieved sources.

## 4. Connect Gmail with local OAuth

Use a dedicated Google Desktop OAuth client for APRIL, not a password or a copied session cookie. Official guide: https://developers.google.com/workspace/gmail/api/quickstart/python

1. In Google Cloud, select/create your own project and enable the Gmail API.
2. Configure Google Auth/consent branding and audience for your own account. If using an external app in testing, add your own address as an allowed test user. Workspace administrators may restrict access.
3. Create an OAuth client of type **Desktop app**. Download its JSON outside the repository and outside indexed folders, for example `~/.config/april/google-client.json`. Do not commit or share it.
4. Install the optional locked dependencies:

   ```bash
   .venv/bin/python -m pip install -r requirements-gmail.lock
   ```

5. On your desktop, run:

   ```bash
   .venv/bin/python -m april.gmail connect --client ~/.config/april/google-client.json
   ```

6. Review the Google browser consent screen. APRIL requests only `gmail.readonly`, not send, compose, delete or modify permissions. This still allows reading mailbox contents, so authorize only the account you intend. The code uses a loopback callback, OAuth state and PKCE. If the client or requested permissions differ from your setup, stop and investigate.

The command stores refresh/access credentials privately at `~/.local/share/april/gmail-token.json` with mode 600. It does not download messages during authorization. Tokens are not encrypted and must not be shared or placed in the index. Google testing-mode grants may expire; reconnect when required.

Restart/refresh the application, then ask **“April, search my emails for invoice”** or type a Gmail query such as `newer_than:7d` and press Search Gmail. Search is a Gmail API request, followed by at most three message reads. Only bounded text excerpts and headers go to the configured local model. No attachment download, background mailbox crawl, persistent email content index, message sending, deletion, read/unread marking, or account settings changes are implemented. Private results appear in this tab; avoid sharing its screenshots without review.

Stop APRIL before disconnecting, so no mail request or refresh is still active. Disconnect locally:

```bash
.venv/bin/python -m april.gmail disconnect
```

Also revoke APRIL’s grant through your Google account to invalidate it remotely. Removing a local file alone is not remote revocation. Never delete unrelated authentication files.

## Limits and verification

- Simulation disables private/external retrieval even when credentials exist. The clock remains deterministic. The mock backends are not live account tests.
- Searches follow ordinary live questions or explicit search requests. Retrieved pages/files/email are untrusted data, not executable tool instructions. The model cannot recursively browse, send mail or run commands from retrieved text.
- SearXNG uses the configured loopback JSON endpoint and its own upstream engines. Gmail uses fixed HTTPS Google endpoints. Local model requests remain loopback. TLS verification stays enabled.
- Gmail authentication has not passed until you complete actual mailbox queries with your local account. The cloud’s attempts to read the official documentation sites returned 403; the installed Google OAuth helper signatures and API contracts were checked, but the real OAuth flow remains pending.
- Earlier dialogue is still not supplied automatically. Conversation context, better semantic retrieval, Navidrome and Pi routing are later milestones; no all-knowing-assistant claim is made.
