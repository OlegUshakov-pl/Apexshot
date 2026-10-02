# Project: ApexShot (AI Snapshot Search)

## 1. Problem Description
Modern search (on the web and in corporate databases) suffers from **noise** and **fragmentation**.
*   **User problem:** To find a precise technical detail, setting, or document, a person has to open dozens of pages and wade through navigation, ads, and boilerplate text. The search process is slow, exhausting, and often imprecise.
*   **Developer/business problem:** Manually indexing websites and documentation requires enormous resources. Traditional full-text indexes (HTML/PDF) are heavy, take up gigabytes of disk space, and are poorly suited to semantic analysis.
*   **Core pain point:** Information is scattered. To get an answer, a person is forced to "dig" manually.

## 2. Proposed Solution
**ApexShot** is a centralized semantic search system built on **AI snapshots** (JSON Snapshots).

The system transforms any input content (text, document, code) into a **compact, structured JSON snapshot file** (1–20 KB in size).

These JSON snapshots accumulate on a central server. The search engine works not with megabytes of raw text, but with small, cleaned, structured JSON objects.

**Result:**
*   **For the user:** Instant, precise search. The system understands the *meaning* of a query (via the generated `summary` and `entities`), not just a hard keyword match.
*   **For content owners:** Simple API integration. Content is automatically turned into a "digital footprint" that is easy to find.
*   **For the infrastructure:** Minimal storage and bandwidth costs (JSON is lighter and faster to process than raw HTML).

## 3. Core Operating Principle
The system works on the model **"Text Upload → AI Analysis → JSON Storage → Search"**.

1.  **Generation (Client-Side / Uploader):**
    *   The user (or an automated script) sends raw text (content) to the server via the API.
    *   The user chooses a provider: **Ollama** (local), **LM Studio** (local), or a **cloud provider** (via API key).
    *   The server passes the text to the chosen model.
    *   The model analyzes the text and produces a **JSON snapshot** with a strict schema:
        *   `summary`: a concise gist of the text.
        *   `facts`: key statements with quotes from the source text (for verification).
        *   `entities`: topics, organizations, technologies, names.
        *   `metadata`: source (url), date, model version, provider.
    *   *Validation:* The server automatically checks that the quotes in `facts` actually appear in the original text (a guard against LLM hallucinations).

2.  **Storage (Server-Side):**
    *   The valid JSON file is saved on the server's disk (or in object storage).
    *   The server extracts the metadata (`title`, `url`, `entities`, `summary`) and stores it in a relational DB (PostgreSQL/SQLite) for fast access.
    *   *Note:* In the current MVP version, search is performed by direct matching on metadata fields and the `facts` text. Vector search (embeddings) will be added in future versions.

3.  **Search:**
    *   The user enters a query in the web interface or via the API.
    *   The server searches the stored metadata and snapshot text (e.g., via PostgreSQL full-text search `tsvector` or a simple `ILIKE`).
    *   Results are returned to the user with the source (URL), a short description (`summary`), and the key facts (`facts`).

## 4. Architecture

```
[Client / Uploader]
       │
       │ 1. POST /upload { content: "...", provider: "ollama", model: "llama3" }
       ▼
[FastAPI Server]
       │
       ├─► Step 1: Call LLM (via Ollama API / LM Studio / Cloud API)
       │    │
       │    └─► LLM returns JSON snapshot
       │
       ├─► Step 2: Validation
       │    │
       │    └─► Check if 'facts' quotes exist in original 'content'
       │         (If mismatch -> reject or flag)
       │
       ├─► Step 3: Save JSON File
       │    │
       │    └─► Save to local FS / MinIO: /snapshots/{uuid}.json
       │
       └─► Step 4: Index Metadata
            │
            └─► Insert into DB (PostgreSQL/SQLite)
                 - id
                 - url
                 - title
                 - summary
                 - entities (JSON array)
                 - provider (ollama, lmstudio, cloud)
                 - model_name
                 - created_at

[Search Query]
       │
       │ 1. GET /search?q="query"
       ▼
[FastAPI Server]
       │
       └─► Query DB (Full-text search on title, summary, entities)
            │
            └─► Fetch corresponding JSON files from Storage
                 │
                 ▼
            [Response: List of Snapshots with summary & facts]
```

**Components:**
*   **Backend:** FastAPI (Python) — the only interface for the user.
*   **Database:** PostgreSQL or SQLite for storing metadata.
*   **Storage:** File system (or MinIO/S3) for storing JSON files.
*   **LLM Providers:**
    *   **Ollama:** local model inference (e.g., `llama3.2:3b`, `mistral:7b`).
    *   **LM Studio:** local model inference.
    *   **Cloud Providers:** OpenAI, Anthropic, Mistral, etc. (via API keys passed by the client).

## 5. User Interaction with the System

The user interacts with the system through a **Web UI** (or CLI/API), without installing browser extensions.

1.  **Provider setup:**
    *   The user opens the ApexShot web interface.
    *   In the settings section they choose the intelligence source:
        *   *Local:* Ollama (specify IP:Port, e.g., `localhost:11434`).
        *   *Local:* LM Studio (specify IP:Port).
        *   *Cloud:* paste an API key (OpenAI/Anthropic/Mistral) and pick a model.

2.  **Content upload (Snapshot Creation):**
    *   The user pastes text (code, article, document) into the upload form.
    *   They click the "Create Snapshot" button.
    *   The server sends the text to the chosen LLM.
    *   The user sees the processing status.
    *   After successful validation the user sees a preview: `Summary`, `Entities`, `Facts`. They can edit these (if allowed) or confirm saving.

3.  **Search:**
    *   The user enters a query in the search bar (e.g., "CORS configuration in FastAPI").
    *   The system searches `title`, `summary`, and `entities` in the database.
    *   Results are displayed as cards:
        *   Title.
        *   Short description (`summary`).
        *   Key facts (`facts`).
        *   Link to the source.
    *   Clicking a card opens the full JSON snapshot (expanded view), where the user sees all the details.

4.  **Business model (for content owners):**
    *   *Free Tier:* a limited number of uploads per month.
    *   *Pro Tier (billing via BLIK):* unlimited uploads, priority processing, data export.

---

**Key differences from classic search:**
1.  **Cleaning at the input:** We do not index "junk" (menus, scripts). We index *meaning*.
2.  **Lightweight data:** JSON snapshots are orders of magnitude lighter than raw pages.
3.  **LLM flexibility:** the user decides which intelligence to use (local for privacy/free of charge, or cloud for quality).
4.  **Privacy:** the ability to use local models (Ollama/LM Studio) means that sensitive data (engineering details, internal documentation) does not leave the local network if the user configures the system that way.


Date: 02.10.2026
