# AI-snapshot

A local web application that turns local directories into small machine-readable
JSON snapshots using local LLMs (**Ollama** or **LM Studio**) and provides search over this library.

- FastAPI + Jinja2 + Tailwind CSS 4 (CDN) + Alpine.js (CDN)
- SQLite + FTS5 (with `LIKE` fallback)
- generation: file collection → text cleaning → chunking → LLM → JSON → quote verification → saving
- no snapshot versions: one directory + one type = one snapshot (replacement without history)
- no Meilisearch / Docker / cloud — everything runs locally
- trilingual UI: **English** (default), **Polski**, **Русский** — can be switched on the “Settings” page

## Run

**Windows:** `install.bat` — install only (`.venv` + dependencies), `start.bat` — install if needed and start the server.

Manual run:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

App: <http://127.0.0.1:8000>

## Pages

| Route | Purpose |
|---|---|
| `/` | Home: statistics, provider status, recent snapshots |
| `/create` | Snapshot creation with progress and replacement of the existing one |
| `/templates` | Template CRUD, enabling, default, prompt testing |
| `/search` | Search and filters (type, provider, model, template, confidence, age) |
| `/snapshots/{id}` | Details: Overview / Facts / Highlights / Entities / Metadata / Raw JSON |
| `/settings` | Provider, generation parameters, active templates per type |

## API

```
GET    /api/health
GET    /api/stats
GET    /api/meta
GET    /api/settings            PUT /api/settings
POST   /api/providers/test
GET    /api/models
GET    /api/templates           POST /api/templates
GET    /api/templates/{id}      PUT /api/templates/{id}    DELETE /api/templates/{id}
POST   /api/templates/{id}/default
POST   /api/templates/{id}/enabled?enabled=true
POST   /api/templates/{id}/test
POST   /api/snapshots
GET    /api/snapshots/exists?directory=&snapshot_type=
GET    /api/snapshots?query=&type=&provider=&model=&template_id=&min_confidence=&max_age_days=&limit=&offset=
GET    /api/snapshots/{id}      GET /api/snapshots/{id}/raw   DELETE /api/snapshots/{id}
GET    /api/jobs/{job_id}
GET    /api/files?directory=
```

## Data

```
data/
  snapshots.db        # settings, templates, snapshots, jobs, snapshots_fts
  snapshots/*.json    # snapshots themselves (usually 1–10 KB)
```

The directory can be moved with the `SHOT_DATA_DIR` environment variable.

## Configuration

Before the first run, open **Settings**: select `ollama` (`http://localhost:11434`) or
`lmstudio` (`http://localhost:1234/v1`), specify the model, and test the connection.

In the **“Interface language”** block you can switch the UI language: `English` / `Polski` / `Русский`
(English by default, the value is stored in the `settings` table).

Six built-in templates (article / documentation / news / forum / notes / general)
are created automatically on first launch.

## Tests

```bash
pip install pytest
pytest -q
```
