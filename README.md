# Intelli Library

Literary **full-text search and discovery** for **Project Gutenberg–style** corpora. The system combines a **Django** HTTP API, a **SQLite** retrieval index, and a **React (TypeScript, Vite)** client. **OpenAI-compatible** HTTP APIs power server-side explanations and chat when credentials are supplied. **Supabase** backs reader authentication and cross-device **saved titles** when the SPA is configured with project keys.

---

## Overview

| Component | Responsibility |
|-----------|----------------|
| **API** | JSON endpoints for search, recommendations, index health, and AI routes (`library/`). |
| **Index** | Inverted list with TF-IDF weights, document–document similarity graph, and precomputed centrality scores (single SQLite file). |
| **Client** | Search UI, curated shelves, related-title panels, AI surfaces; `Rank by` maps to the `order` query parameter on `/api/search`. |

---

## Capabilities

### Retrieval and ranking

- **Keywords** — Inverted index (`terms`, `postings` with `tf`, `tfidf`). Ranking mixes **normalized TF-IDF** and **normalized graph centrality** (70% / 30%) in `SearchService`.
- **Regex** — Same TF-IDF + centrality blend in `RegexSearchService`.
- **Title** — Substring / token constraints on `Book.title`, **match-quality tiers** (exact, phrase, prefix, containment), plus centrality **without** TF-IDF.
- **Author** — Token overlap on `Book.authors` with a **70% / 30%** blend of match strength and centrality.

Implementation references: `library/corpus/backend/search_service.py`, `regex_search_service.py`.

### Search index and ranking (SQLite)

All structures below reside in `library/db_index.sqlite3` after a successful build.

| Layer | Tables | Role |
|--------|--------|------|
| **Lexical** | `terms`, `postings` | Term → document postings; **`tfidf`** supplies per-hit weights for keyword and regex ranking. |
| **Graph** | `document_graph` | Weighted edges from cosine similarity of document vectors; feeds related-title retrieval and centrality inputs. |
| **Centrality** | `document_scores` | Per-book **`popularity`** (degree), **`closeness`**, **`betweenness`**, **`pagerank`**, and composite **`total`**. Populated by `compute_centrality` after `build_doc_graph`. |

**`order` / Rank by** selects the centrality column for the non-TF-IDF leg (where applicable): `default` → **`total`**; `pagerank`, `closeness`, `betweenness`; keyword and regex also support `degree` → **`popularity`**.

**Empty `document_scores`** — If graph metrics have not been computed, centrality contributes nothing meaningful; keyword and regex results align primarily with TF-IDF; title and author modes rely on text match alone beyond baseline scores. Run `build_doc_graph` and `compute_centrality` after indexing.

**Related titles** — `RecommendationService` ranks neighbours on `document_graph` by **edge similarity**, using **`document_scores.total`** as a secondary key.

### Web client

Single-page application: search flows, **Rank by** control, curated rails, similarity-style recommendations, saved-title UX when Supabase env vars are present, and AI brief / chat when the backend LLM configuration is active.

### LLM endpoints

With `OPENAI_API_KEY` (and compatible base URL / model if not using the default host), Django exposes result explanation and conversational routes; behaviour is documented under [AI integration](#ai-integration-rag-tools-memory-mcp).

### Authentication and saved titles

Email **magic link** and **password** flows use Supabase Auth. Persisted shelves are stored in Supabase per the schema under `supabase/sql/`. The application operates without Supabase when those variables are omitted.

---

## Stack

| Layer | Details |
|--------|---------|
| **Backend** | Django project root `library/`; SQLite index path `library/db_index.sqlite3` (excluded from Git — rebuild or restore locally). |
| **Frontend** | React, TypeScript, Vite under `frontend/`. |
| **Corpus** | HTML collection directory `books_html_kept/` (Gitignored; populate after clone). |

---

## Repository layout

```
library/           Django project, retrieval services, management commands
frontend/          Vite SPA
data/              Metadata CSVs (`selected_meta.csv`; `pg_catalog.csv` when used)
analysis/          Offline statistics plots and CSV exports (`export_index_stats`, etc.)
scripts/           Corpus pipeline, index backup / restore utilities
supabase/sql/      SQL definitions for saved titles and related Supabase objects
```

---

## Requirements

- **Python 3.10+** (`library/requirements.txt`)
- **Node.js** current LTS (`frontend/package.json`)

A **built or restored** SQLite index is required for non-empty search results; the API process starts without it.

---

## Local operation

### Backend

```bash
cd library
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

- `GET /` — service metadata JSON  
- `GET http://127.0.0.1:8000/api/health` — expect `{"status":"ok"}`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Use the dev server URL from the console (commonly `http://127.0.0.1:5173`). Vite proxies `/api` to the Django origin in development.

### Initial index build

With corpus layout and metadata paths resolved, materialize `library/db_index.sqlite3` via:

- `scripts/build_index_pipeline.py`
- `library/index_full_build.sh` (Unix-like environments)
- Django commands: `index_*`, `build_doc_*`, `compute_centrality`

Command order and flags depend on corpus size. On Windows, use UTF-8 console encoding when logs contain non-ASCII text.

### Curated shelf versus searchable set

The **Classic masterpieces** rail lists curated Project Gutenberg identifiers. **On-site search** returns only volumes present in `books` and the inverted index; `corpus/curated_classics.py` is the canonical ID list for that rail.

Place normalized HTML (and optionally pass `--meta` to point at CSV metadata) under `books_html_kept/`, then:

**A — Incremental add (preserves existing postings)**

```bash
cd library
python manage.py ingest_curated_classics --dir ../books_html_kept --meta ../data/selected_meta.csv
python manage.py index_append_curated_classics --dir ../books_html_kept
python manage.py index_compute_tfidf
```

Refresh similarity and centrality (costly): `python manage.py build_doc_graph && python manage.py compute_centrality`.

**B — Full rebuild path**

```bash
cd library
python manage.py ingest_curated_classics --dir ../books_html_kept --meta ../data/selected_meta.csv
python manage.py index_build_fast --dir ../books_html_kept --meta ../data/selected_meta.csv
python manage.py index_compute_tfidf
python manage.py build_doc_graph
python manage.py compute_centrality
```

`ingest_curated_classics` skips volumes already present on disk or listed in the CSV (`--dry-run` for inspection). `index_append_curated_classics` skips books that already have postings unless `--force` is set. Respect [Project Gutenberg automated access policy](https://www.gutenberg.org/policy/robot_access.html).

`index_compute_tfidf` updates **all** posting rows and is CPU-intensive but typically less expensive than a full retokenization via `index_build_fast`.

### Moving the index between machines

`library/db_index.sqlite3` and `books_html_kept/` are **not** version-controlled. A clone alone does not restore search behaviour.

**Backup archive** — On a host with a working index:

```bash
python scripts/backup_index.py
```

Transfer `ibe-index-*.zip`, then on the target:

```bash
python scripts/restore_index.py path/to/ibe-index-....zip --force
```

Copy `books_html_kept/` and `data/selected_meta.csv` when rebuilding or when `Book.local_path` must align for RAG excerpts.

**Rebuild** — Install dependencies, restore corpus and metadata, run `scripts/build_index_pipeline.py` (as in [Initial index build](#initial-index-build)).

**Large binaries** — Prefer [Git LFS](https://git-lfs.com/) or release artefacts for index bundles; avoid multi–hundred MB commits on `main`.

---

## LLM provider configuration

Create `.env` at the repository root or under `library/`. **Do not commit secrets.**

```env
OPENAI_API_KEY=<secret>
OPENAI_MODEL=<model-id>
# Non-default host (example — DeepSeek-compatible base):
# OPENAI_BASE_URL=https://api.deepseek.com/v1
# OPENAI_MODEL=deepseek-chat
```

Restart Django after changes.

Providers implementing OpenAI-style **Chat Completions** work with the same variables: set `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` per vendor documentation. Endpoints `/api/ai/explain` and `/api/ai/chat` follow that contract; `/api/ai/chat` uses tool calling — disable tools in the client (`enable_tools: false`) if a provider rejects tool schemas.

---

## Backend environment variables

| Variable | Purpose |
|----------|---------|
| `DJANGO_SECRET_KEY` | Production requirement |
| `DJANGO_DEBUG` | `false` in production |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `CORS_ALLOWED_ORIGINS` | Permitted browser origins |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF with cross-site deployments |
| `OPENAI_API_KEY` | Required for `/api/ai/explain` and `/api/ai/chat` |
| `OPENAI_BASE_URL` | Base URL for OpenAI-compatible APIs; hosted OpenAI default when unset |
| `OPENAI_MODEL` | Chat model identifier |
| `CORPUS_ALLOWED_ROOT` | Comma-separated absolute directories allowed for RAG HTML reads |

---

## AI integration (RAG, tools, memory, MCP)

- **RAG** — `POST /api/ai/explain` accepts `book_ids`; excerpts load when `Book.local_path` resolves to HTML. `POST /api/ai/chat` injects keyword-search snippets from the latest user turn unless `inject_rag` is `false`.
- **Tools** — `/api/ai/chat` may invoke `search_catalog` and `similar_books_for_query` (`enable_tools: false` to turn off).
- **Session** — Stateless HTTP; clients send full `messages`. The SPA caches turns in `localStorage` (`ibe-ai-chat-v1`).
- **MCP** — `python scripts/mcp_intelli_book_server.py` from the repository root with Django reachable; dependency `mcp` in the active Python environment. Environment **`IBE_API_BASE`** (default `http://127.0.0.1:8000`) targets the API.

**Cursor** (`Settings → MCP → Add server`), project interpreter example:

```json
{
  "mcpServers": {
    "intelli-library": {
      "command": "C:/path/to/repo/library/.venv/Scripts/python.exe",
      "args": ["C:/path/to/repo/scripts/mcp_intelli_book_server.py"],
      "env": {
        "IBE_API_BASE": "http://127.0.0.1:8000"
      }
    }
  }
}
```

Adjust paths per operating system.

---

## Frontend environment (`frontend/.env`)

Copy `frontend/.env.example` to `.env`.

| Variable | Purpose |
|----------|---------|
| `VITE_SUPABASE_URL` | Supabase project URL (no `/rest/v1` suffix) |
| `VITE_SUPABASE_ANON_KEY` | Publishable (anon) key |
| `VITE_API_BASE` | Public Django origin when the SPA is served from another host (no trailing slash) |

---

## Deployment

**Static client** — `npm run build`; deploy `dist/` with `VITE_*` injected by the host. In Supabase: **Site URL** and **Redirect URLs** must list the production HTTPS origin.

**Application server** — Gunicorn or uWSGI behind Nginx (or equivalent); `DEBUG` disabled; `ALLOWED_HOSTS`, CORS, and CSRF configured; filesystem access to `db_index.sqlite3`.

```bash
cd library
gunicorn library.wsgi:application --bind 127.0.0.1:8000
```

`render.yaml` documents a **Render** Docker deployment for the API; production frontends set `VITE_API_BASE` to that service URL. Ephemeral disks on free tiers reset on redeploy unless the SQLite file is embedded in the image or mounted on persistent storage — see inline comments in `render.yaml`.

---

## License

MIT — [`LICENSE`](LICENSE).
