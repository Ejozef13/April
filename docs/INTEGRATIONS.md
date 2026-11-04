# Read-only web, April files and Gmail

These integrations are implemented as opt-in adapters. Temporary-file/API fixtures and browser tests exercise their boundaries; real Brave credentials, Google OAuth approval and Enrique’s private folder are not available in the cloud. Do not describe those accounts as connected until their actual operations pass on the desktop.

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

## 3. Web provider: SearXNG first, Brave optional

SearXNG is now the default, following Enrique's preference for no search API subscription. Follow [SEARXNG.md](SEARXNG.md) for the loopback-only Docker setup and real-query test. It needs no Brave key. Engine availability/quality and actual desktop search must still be verified. Provider selection is explicit; no paid fallback occurs.

To choose Brave later, run `.venv/bin/python -m april.integrations search-provider brave`, restart APRIL, then follow the optional steps below.

### Optional Brave setup

Brave Search API is separate from the Brave browser. It requires an API account/key; check the provider’s current plans, quotas and pricing before choosing one. No account, purchase or subscription is created by APRIL. Official setup reference: https://api-dashboard.search.brave.com/app/documentation/web-search/get-started

After obtaining your own search API key, enter it locally with hidden input:

```bash
.venv/bin/python -m april.integrations web-key
```

Never paste the key into chat, Git, a command-line argument or a screenshot. The helper creates a mode-600 file at `~/.config/april/brave-key`, outside the repository, and refuses to replace an existing key. A process environment variable named by `web_api_key_env` is an alternative; the default is `APRIL_BRAVE_API_KEY`. The key file is not encrypted; your local OS account controls access.

Restart APRIL and refresh the browser. Ask **“April, search the web for the current president of the United States”**, or use Search web with the typed question. A narrow set of current-fact phrases also routes to search, rather than falling back to stale model weights. This is deterministic routing, not an all-purpose intent classifier. Be explicit about country, date and subject.

The provider receives your search query, not document or Gmail excerpts. At most three result snippets are retrieved; URLs, snippets, retrieval timestamp and any supplied provider date accompany the local model’s evidence. APRIL does not fetch or independently verify full pages. Open the displayed sources and check dates. If the key/service is unavailable, APRIL reports that no current answer was verified; it does not invent a live lookup.

The `configured` indicator means a binding/file is present, not that authentication or search has passed. Run an actual query to verify. Private retrieval never automatically falls back to web search. Do not put private material into a web query unless you intend to send that query to the provider.

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
- Every search is initiated by a user action or an explicit recognized phrase. Retrieved pages/files/email are untrusted data, not executable tool instructions. The model cannot recursively browse, send mail or run commands from retrieved text.
- SearXNG uses the configured loopback JSON endpoint and its own upstream engines; Brave uses a fixed HTTPS API only when explicitly selected. Gmail uses fixed HTTPS Google endpoints. Local model requests remain loopback. TLS verification stays enabled.
- Gmail/Brave authentication has not passed until you complete actual queries with your local accounts. The cloud’s attempts to read the official documentation sites returned 403; the installed Google OAuth helper signatures and API contracts were checked, but the real OAuth flow remains pending.
- Earlier dialogue is still not supplied automatically. Conversation context, better semantic retrieval, Navidrome and Pi routing are later milestones; no all-knowing-assistant claim is made.
