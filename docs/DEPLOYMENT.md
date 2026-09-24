# FieldTrace deployment: Vercel + Railway

Prepared for a supervised hackathon deployment; nothing deploys automatically.
Vercel serves the static React/Vite frontend. A Railway Docker service runs FastAPI
and connects to Railway PostgreSQL with pgvector. Backend Root Directory is the
repository root; Vercel Root Directory is `frontend`. Do not deploy FastAPI to Vercel.

The prototype lacks authentication and tenant isolation. The production guard below
limits abuse but cannot identify authorized users. Use authorized demo data and
supervised access; this is not production security.

## Current deployed environment

The supervised ABB Accelerator demo is currently deployed:

- Frontend: https://fieldtrace-blush.vercel.app
- Backend health: https://fieldtrace-production.up.railway.app/health
- Railway project: `FieldTrace`
- Railway services: `fieldtrace` and `Postgres`
- PostgreSQL: 17 with pgvector 0.8.6
- Indexed corpus: 2 ABB manuals, 736 pages, 11,085 chunks
- Upload persistence: verified across redeployment
- Production CORS: configured for the Vercel frontend

A live smoke test verified equipment confirmation, same-session follow-up, and the actual fault-5091 citation on physical page 525. Model confidence can vary between runs, so the labeled replay remains the backup demo path.

## Public demo safety

Public backend endpoints can consume provider credits. **CORS is not authentication**:
direct HTTP clients can bypass browser origin checks. Never put a secret token or API
key in Vite / `VITE_*` variables; all provider credentials stay on the backend.

Set `APP_ENV=production` on Railway (also the Docker/cloud-launcher default). This:

- Disables `/docs`, `/redoc`, `/openapi.json`, public document ingestion and detailed
  run audits. Ingest through the service shell. Local development keeps these tools.
- Caps actual request bodies before multipart parsing: 12 MiB total for multipart,
  64 KiB otherwise, with 30 seconds to receive a body. Upload large photos one at a time.
  Existing JPEG/PNG/WEBP, 10 MiB per image, pixel and session-count checks still apply.
- Allows eight simultaneous requests and only one mutating request at a time.
  Global rolling limits default to 120 requests/minute, 60 mutations/hour and eight
  provider actions/hour. Healthchecks bypass rate budgets but not concurrency limits.
  All clients share these limits; forwarding headers cannot reset them. Attempts count
  even when they fail. HTTP 429 includes a retry hint; an hourly budget may need longer.
- Disables batch image analysis; use individual image analysis. Each admitted reasoning
  action still has the existing maximum of 48 LLM calls; one image can make two attempts.
  Eight actions is **not** a dollar budget or an eight-call limit.
- Caps stored uploads at 256 MiB, conservatively including the incoming multipart body.
  HTTP 507 requires operator cleanup/archival or a deliberate quota increase. No automatic
  data deletion occurs. Image filenames are generated and resolved within the session directory.
- Returns generic validation/service errors without exception text or input echoes.

Optional backend variables: `DEMO_REQUESTS_PER_MINUTE=120`,
`DEMO_WRITES_PER_HOUR=60`, `DEMO_PROVIDER_ACTIONS_PER_HOUR=8`,
`DEMO_UPLOAD_QUOTA_BYTES=268435456`. Run **one replica and one Uvicorn worker**;
the launcher pins one worker. Counters are in memory and reset on restart. They are
only prototype safeguards: an attacker can exhaust the shared budget, access a known
session ID, or consume credits within the limits. Do not store sensitive demo data.
The upload quota does not bound database growth, logs or model-cache size.

Use a restricted, low-budget provider project/key if possible, with provider-side
spending controls where available. Monitor usage during the demo. Remove or rotate
deployment credentials after the event if the public deployment is no longer needed.
Keep PostgreSQL on the private service network; do not advertise its connection URL.
Broader public use requires real access control and persistent, distributed limits.

## Part A — Railway backend and database

### 1. Create a Railway project

Create a FieldTrace project with backend and database in the same region. These are
instructions for a later authorized deployment. This task does not commit, push or
deploy; GitHub must eventually contain the reviewed files on your selected branch.

### 2. Add PostgreSQL with pgvector

Create a PostgreSQL service with persistent storage and pgvector binaries installed.
An ordinary PostgreSQL image may not contain the extension. For a new database,
choose a pgvector-capable image/template. See [Railway PostgreSQL](https://docs.railway.com/databases/postgresql)
and the [pgvector template](https://railway.com/deploy/pgvector-postgresql).
Do not replace a populated database or change its major version to follow this guide.

### 3. Enable the extension

Connect to the application database using its SQL client and run:

```sql
SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extversion FROM pg_extension WHERE extname = 'vector';
```

No rows from the first query means the image lacks pgvector binaries. SQL alone
cannot install them. Use a pgvector-capable service for the new empty database.
Permission errors require the database administrator. Do not drop tables or reset data.

### 4. Add the backend from GitHub

Add `ryanleem/fieldtrace` as a GitHub service, selecting the reviewed branch when ready.
Keep Root Directory at the repository root. Railway uses `Dockerfile` and `railway.json`.
The image installs CPU PyTorch, the existing pinned Python dependencies and OCR native
libraries. Local secrets, PDFs, uploads and model caches are excluded from its build
context. A successful Linux image build must still be verified on Railway; local
Python/frontend tests do not validate that build.

### 5. Set backend variables and attach storage

In the backend Variables panel:

| Variable | Setting |
| --- | --- |
| `APP_ENV` | `production`; enables the public-demo guard and hides developer surfaces. |
| `DATABASE_URL` | Reference the PostgreSQL service's private URL using Railway's variable picker. Never put it in Git or frontend variables. |
| `OPENAI_API_KEY` | Private funded key for reasoning and OpenAI vision. |
| `CORS_ALLOWED_ORIGINS` | Exact allowed frontend origins, comma-separated. No paths, trailing slashes or wildcard. Add the final Vercel origin in Part B. |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` |
| `EMBEDDING_REVISION` | `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, identical during ingestion and serving. |
| `VISION_PROVIDER` | `openai`, or explicitly select `gemini`. |
| `GEMINI_API_KEY` | Required only for Gemini vision. |
| `GEMINI_VISION_MODEL` | `gemini-2.5-flash` if using Gemini. |
| `UPLOAD_ROOT` | `/data/uploads`, with a backend volume mounted at `/data`. |
| `MODEL_CACHE` | Optional `/data/models` on the same volume to retain model downloads. |

Railway supplies `PORT`. Keep existing reasoning/vision defaults unless intentionally
configuring an adapter. `POSTGRES_PASSWORD` is unnecessary on the backend when an
explicit `DATABASE_URL` is set; it remains the local development fallback.

Attach a **backend** volume at `/data`. The database volume does not store uploaded
images. `UPLOAD_ROOT` takes precedence over the existing `UPLOADS_DIR` alias. Use one
backend replica with this filesystem-based prototype. Without a volume, redeploys can
lose images while their database metadata remains. A volume is not a backup. Do not
mount over `/app`, which would hide code and the manual manifest. See
[Railway volumes](https://docs.railway.com/volumes) for attachment and backup limitations.

### 6. Start the backend

The checked-in command is:

```text
python scripts/start_backend.py
```

It requires a cloud `DATABASE_URL`, validates `PORT` (default 8000), then launches
Uvicorn on `0.0.0.0` with that port and `--app-dir backend`. The local Windows command
remains unchanged:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Startup reuses the existing advisory-lock-protected, idempotent extension, table and
index initializers. No destructive reset or new migration system is introduced.
Startup does not ingest manuals. It loads the local embedding model, which can require
a cold download; allow suitable memory and startup time. Incompatible corpus/model
settings fail rather than mixing embedding spaces.

### 7. Confirm health

Generate a backend public HTTPS domain and open `/health`. `railway.json` configures
that healthcheck with a 300-second startup timeout. The endpoint queries PostgreSQL
and its vector extension; a database outage must not produce a healthy response.
HTTP 200 does not prove that manuals are ingested or provider keys are funded.

### 8. Ingest the two manuals once

Open a shell **inside the running backend service**, for example `railway ssh` after
linking the CLI to the correct project, environment and backend service. Confirm the
directory is `/app` and backend variables are inherited. Run this one-time command:

```sh
python scripts/download_manuals.py && python scripts/ingest_manuals.py
```

It downloads the official manifest sources, verifies PDF hashes and embeds locally
into `DATABASE_URL`. It needs network downloads and compute, but no paid provider calls.
Do not put it in startup or a pre-deploy command. Leave `MANUALS_DIR`/`PROCESSED_DIR`
at their defaults for this command; do not use `--rebuild` for initial ingestion.
The Dockerfile creates the processed-output directory.

Verify in the database client:

```sql
SELECT count(*) AS documents FROM documents;
SELECT count(*) AS pages FROM document_pages;
SELECT count(*) AS chunks FROM document_chunks;
SELECT d.title, d.revision, d.pages_processed, d.chunks_created,
       count(c.id) AS stored_chunks
FROM documents d LEFT JOIN document_chunks c ON c.document_id = d.id
GROUP BY d.id ORDER BY d.title;
SELECT model, revision, dimensions, pipeline_version FROM corpus_config;
```

Expect two documents (ACS880 firmware revision V and motor/generator revision L),
positive page/chunk counts and nonzero chunks for each manual. Compare with ingestion
output rather than guessing totals. PDFs can disappear on container redeployment;
stored text/vectors remain in PostgreSQL and citations link to ABB. Download again only
for deliberate reingestion. Do not commit PDFs. `railway run` executes locally, unlike
SSH; private database hostnames generally will not resolve on your laptop.

## Part B — Vercel frontend

1. Import the same GitHub repository and reviewed branch when available.
2. Set Root Directory to `frontend`, framework Vite, install `npm ci`, build
   `npm run build`, output `dist`. Use a supported Node version compatible with Vite 8.
3. Set `VITE_API_BASE_URL` to the backend public HTTPS origin, without `/api`.
   This variable is public. Never put database URLs or API keys in `VITE_*` values.
   Keep `VITE_DEMO_MODE=false` for live mode.
4. Deploy when authorized. `frontend/vercel.json` provides SPA fallback. API requests
   and image URLs go directly to Railway, not through a Vercel function. See the
   [Vercel Vite guide](https://vercel.com/docs/frameworks/frontend/vite).
5. Add the final Vercel origin to backend `CORS_ALLOWED_ORIGINS`. Include scheme and
   hostname only, no trailing slash. Add preview domains explicitly if needed.
6. Apply/redeploy backend variable changes. Rebuild the frontend after changing its
   base URL because Vite embeds it at build time.

An empty frontend base preserves local `/api` requests through Vite's proxy to
`BACKEND_URL` or `http://127.0.0.1:8000`. That proxy is absent on static Vercel hosting;
set the cloud base URL explicitly. No Railway hostname is hard-coded in source.

## Part C — Verification after authorized deployment

The production deployment has completed the core smoke test below. Reasoning and
vision use paid calls, so repeat these checks only when needed.

- Open the public live URL; type `ABB ACS880-01` and `Drive shows fault 5091`.
- Detect and confirm; verify drafts survive automatic session creation.
- Run troubleshooting once and inspect the actual result without forcing MEDIUM.
- Open the citation around physical PDF page 525 and its original manual link.
- Submit `STO wiring has not yet been checked.` Confirm the same session and saved update.
- Separately test an authorized photo, its Railway image URL, reload and persistence
  after a controlled redeploy. Distinguish LOW evidence from service failure.
- Keep the explicitly labeled replay as backup.

## Part D — Common failures

| Failure | Check |
| --- | --- |
| CORS | Exact Vercel origin, no trailing slash, backend redeployed. CORS is not authentication. |
| HTML instead of API JSON | Cloud frontend base must be Railway origin; backend paths have no `/api` prefix. Rebuild Vercel. |
| Missing DATABASE_URL | Set the backend reference. Cloud start refuses a silent local fallback. |
| Database/SSL connection | Use private URLs inside Railway and public connection settings outside. SSL query options are preserved; only PostgreSQL driver prefixes change to psycopg3. |
| pgvector unavailable | Install a pgvector-capable image for the new DB, then enable the extension with adequate permission. |
| Health works but retrieval is empty | Check two documents and positive chunk counts; ingest once with the same embedding revision. |
| Missing API key/quota | Set a funded backend key for the selected provider, never a frontend key. |
| Sleeping/unavailable backend | Wake/retry, check logs and memory/startup budget. Refresh session after an ambiguous timeout before retrying. |
| Missing image file | Attach backend volume and place UPLOAD_ROOT under its mount. Lost ephemeral files require re-upload. |
| Slow cold model download | Persist MODEL_CACHE, allow outbound model access and adequate memory. |
| Docker build failure | Inspect Linux dependency/native-library build logs. Do not blindly loosen pins or disable TLS. |

Local secrets stay ignored by Git and excluded by the Docker context allowlist.
The repository scanner is heuristic review, not proof of absence of secrets.
