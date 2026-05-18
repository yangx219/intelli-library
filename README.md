# Intelli Book Engine

A book discovery stack with a **Django** JSON search API and a **React (Vite)** web UI. Optional **OpenAI** integration generates short explanations of search results; optional **Supabase** powers accounts and cloud-saved titles.

## Features

- **Search**: Full-text / TF-IDF–related retrieval plus a regex-based search engine (see `library/corpus/`).
- **Web UI**: Search, curated rails, and similarity-style flows; in development, Vite proxies `/api` to the local Django server.
- **Optional**: Server-side OpenAI calls; email magic links / password auth and saved lists via Supabase (`supabase/sql/`).

## Stack

| Layer | Details |
|--------|---------|
| Backend | Django in `library/`; search index is SQLite at `library/db_index.sqlite3` (not checked in—build locally). |
| Frontend | React + TypeScript + Vite in `frontend/`. |
| Corpus | HTML corpus under `books_html_kept/` (gitignored—generate or sync locally). |

## Repository layout

```
library/           Django project, retrieval logic, index management commands
frontend/          Vite SPA
data/              Shared CSV metadata (`selected_meta.csv`, optional `pg_catalog.csv`)
analysis/          Optional offline plots & CSV exports (`python manage.py export_index_stats`)
scripts/           Pipeline, corpus download, backup_index.py / restore_index.py
supabase/sql/      Example SQL for saved titles and related tables
```

## Prerequisites

- Python 3.10+ (match `library/requirements.txt`) and a current Node.js LTS (compatible with `frontend/package.json`).
- After cloning, you must **build the search index** (below); the API runs without it but returns empty search results.

## Local development

### 1. Backend

```bash
cd library
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

- `GET /` — API discovery JSON.
- `GET http://127.0.0.1:8000/api/health` — expect `{"status":"ok"}`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed in the terminal (typically `http://127.0.0.1:5173`). The dev server proxies `/api` to Django.

### 3. Build the search index (first-time)

With corpus and metadata in place, generate `library/db_index.sqlite3` using repo scripts and Django commands, for example:

- `scripts/build_index_pipeline.py`
- `library/index_full_build.sh` (Unix-like shells)
- `manage.py` commands such as `index_*`, `build_doc_*`, `compute_centrality`

Exact order and flags depend on dataset size; on Windows, use UTF-8 console settings if logs hit encoding issues.

### Classics shelf → searchable index

The **Classic masterpieces** row shows curated Project Gutenberg editions **for browsing**; site search only returns books that exist in your SQLite `books` table and inverted index (`corpus/curated_classics.py` is the canonical id list).

Pull plaintext into `books_html_kept/` (optional CSV rows via `--meta`), then choose:

**A — Already indexed thousands of books (incremental, avoids wiping postings)**

```bash
cd library
python manage.py ingest_curated_classics --dir ../books_html_kept --meta ../data/selected_meta.csv
python manage.py index_append_curated_classics --dir ../books_html_kept
python manage.py index_compute_tfidf
```

Then optionally refresh similarity ranks (slow): `python manage.py build_doc_graph && python manage.py compute_centrality`.

**B — Fresh corpus / full rebuild**

```bash
cd library
python manage.py ingest_curated_classics --dir ../books_html_kept --meta ../data/selected_meta.csv
python manage.py index_build_fast --dir ../books_html_kept --meta ../data/selected_meta.csv
python manage.py index_compute_tfidf
python manage.py build_doc_graph
python manage.py compute_centrality
```

`ingest_curated_classics` skips ids already on disk / already listed in the CSV. Use `--dry-run` to preview. `index_append_curated_classics` skips ids that already have posting rows unless you pass `--force`. Follow [Project Gutenberg automated traffic guidance](https://www.gutenberg.org/policy/robot_access.html).

Note: `index_compute_tfidf` recomputes weights for **all** posting rows (still CPU-heavy), but it is usually far cheaper than re-tokenizing every document via `index_build_fast`.

### Moving to another PC (why `git pull` alone has no database)

`library/db_index.sqlite3` is **gitignored** (often hundreds of MB). **`books_html_kept/`** is also ignored. After cloning or pulling on a new machine you **must** either restore a backup or rebuild.

**Option A — backup bundle (fast)**

On the machine that already has a built index:

```bash
python scripts/backup_index.py
```

Copy the generated `ibe-index-*.zip` (USB / Drive / NAS). On the new clone:

```bash
python scripts/restore_index.py path/to/ibe-index-....zip --force
```

Optionally sync **`books_html_kept/`** and **`data/selected_meta.csv`** as well if you plan to rebuild or need identical local paths for RAG excerpts (`Book.local_path`).

**Option B — rebuild from corpus**

Install deps, place corpus under `books_html_kept/` with metadata CSV as documented, then run `scripts/build_index_pipeline.py` (same as section 3).

**Option C — Git LFS / CI artefact**

If you insist on storing the SQLite inside Git hosting, use [Git LFS](https://git-lfs.com/) or upload the zip as a **GitHub Release** asset — avoid committing hundreds of MB to plain `main` history.

### 4. Optional: AI backend (OpenAI, DeepSeek, or any OpenAI-compatible API)

Create a `.env` at the **repository root** or under `library/` (never commit secrets):

```env
OPENAI_API_KEY=<your-key>
OPENAI_MODEL=<optional-model-id>
# Optional — omit to use api.openai.com; use DeepSeek for example:
# OPENAI_BASE_URL=https://api.deepseek.com/v1
# OPENAI_MODEL=deepseek-chat
```

Restart Django after changing env vars.

**DeepSeek** exposes the same HTTP shape as OpenAI’s Chat Completions (`/v1/chat/completions`), so you only set **`OPENAI_BASE_URL`** to DeepSeek’s base URL and **`OPENAI_MODEL`** to a DeepSeek model id (see their docs). **`OPENAI_API_KEY`** is your DeepSeek key. **`/api/ai/explain`** works the same; **`/api/ai/chat`** uses tool calling — if a provider misbehaves with tools, disable tools from the client (`enable_tools: false`) or switch provider.

## Backend environment variables

| Variable | Purpose |
|----------|---------|
| `DJANGO_SECRET_KEY` | Required in production |
| `DJANGO_DEBUG` | Set `false` in production |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `CORS_ALLOWED_ORIGINS` | Allowed browser origins |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF when using cross-site setups |
| `OPENAI_API_KEY` | Enables `/api/ai/explain` and `/api/ai/chat` |
| `OPENAI_BASE_URL` | Optional; default OpenAI. Set e.g. `https://api.deepseek.com/v1` for DeepSeek |
| `OPENAI_MODEL` | Optional chat model id |
| `CORPUS_ALLOWED_ROOT` | Optional comma-separated absolute directories restricting HTML paths used for RAG excerpts |

## AI: RAG, tools, memory, MCP

- **RAG**: `POST /api/ai/explain` accepts `book_ids`; when `Book.local_path` HTML exists, excerpts are added. `POST /api/ai/chat` prepends keyword-search excerpts from the latest user message unless `inject_rag` is `false`.
- **Tools**: `/api/ai/chat` uses OpenAI tool calls for `search_catalog` and `similar_books_for_query` (same logic as `/api/search` and `/api/recommendations/query`). Set `enable_tools` to `false` to disable.
- **Memory**: Stateless API — send full `messages`. The SPA stores chat turns in `localStorage` (`ibe-ai-chat-v1`).
- **MCP**: Run `python scripts/mcp_intelli_book_server.py` from the repo root (Python env with `mcp` installed) while Django is up. Optional env `IBE_API_BASE` (default `http://127.0.0.1:8000`). Add the command to your MCP client configuration.

Example for **Cursor** (`Settings → MCP → Add server`), using the repo venv interpreter so `mcp` resolves:

```json
{
  "mcpServers": {
    "intelli-book-engine": {
      "command": "C:/path/to/repo/library/.venv/Scripts/python.exe",
      "args": ["C:/path/to/repo/scripts/mcp_intelli_book_server.py"],
      "env": {
        "IBE_API_BASE": "http://127.0.0.1:8000"
      }
    }
  }
}
```

Adjust paths for your machine (POSIX shells can use the same paths with forward slashes on Windows).

## Frontend environment variables (`frontend/.env`)

Copy `frontend/.env.example` to `.env` and set:

| Variable | Purpose |
|----------|---------|
| `VITE_SUPABASE_URL` | Supabase project URL (no `/rest/v1` suffix) |
| `VITE_SUPABASE_ANON_KEY` | Publishable anon key |
| `VITE_API_BASE` | Optional; Django origin when the SPA is on another domain (no trailing slash) |

## Production notes

**Frontend**: `npm run build`, deploy `dist/` to static hosting or behind a reverse proxy; configure `VITE_*` in the host environment. In Supabase, set **Site URL** and **Redirect URLs** to your production HTTPS frontend.

**Backend**: Run behind Gunicorn or uWSGI with Nginx (or equivalent), disable `DEBUG`, set `ALLOWED_HOSTS`, CORS, and CSRF. Ship the built `db_index.sqlite3` where the process can read it.

Example (after `pip install gunicorn` in the same venv as Django):

```bash
cd library
gunicorn library.wsgi:application --bind 127.0.0.1:8000
```

## License

Licensed under the MIT License — see [`LICENSE`](LICENSE).
