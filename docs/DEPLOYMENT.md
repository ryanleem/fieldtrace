# FieldTrace deployment: Vercel + Railway

Prepared for a supervised hackathon deployment; nothing deploys automatically.
Vercel serves the static React/Vite frontend. A Railway Docker service runs FastAPI
and connects to Railway PostgreSQL with pgvector. Backend Root Directory is the
repository root; Vercel Root Directory is `frontend`. Do not deploy FastAPI to Vercel.

The currently deployed version predates the local authentication changes described
below. After review and deployment, live session access requires Supabase Auth and
an owner check in Railway PostgreSQL. Use authorized demo data and supervised access;
this is still a prototype, not production security.

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

The authenticated version requires login for session APIs and `/search`. Signup
still permits new users to consume the shared demo budget: login is not a spending
limit. Keep the existing rate limits and provider budget controls in place.

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
only prototype safeguards: an attacker can exhaust the shared budget or an authenticated
user can consume credits within the limits. The old deployed version also allows access
by known session ID; the reviewed authenticated version rejects other users regardless
of UUID knowledge. Do not store sensitive demo data.
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


## Authentication and saved sessions (pending review; not deployed)

Supabase manages accounts, passwords, email confirmation, refresh and logout only.
All FieldTrace sessions, equipment, photos, findings, runs and vectors stay in Railway.
No Supabase application tables, database migration to Supabase, or service-role key
are needed. The browser uses the official Supabase SDK. FastAPI verifies ES256/RS256
JWT signatures against the project's fixed JWKS endpoint, issuer, `authenticated`
audience, expiry, issued-at, user UUID and authenticated role. Anonymous Supabase
users and legacy HS256 signing keys are not supported by this implementation.

Supabase documents the [public signing-key endpoint](https://supabase.com/docs/guides/auth/signing-keys).
Choose an asymmetric signing key in the Supabase project before configuring this release.

### Configuration after approval

1. Create/select a Supabase project, enable email/password sign-in, and configure
   email confirmation and the Site URL/allowed redirect URLs for the production
   Vercel origin and your local development origin. Test email delivery explicitly.
2. Backend Railway variables: `SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co`
   and `SUPABASE_JWT_AUDIENCE=authenticated` (default). The backend needs only public
   signing keys, not the anon key, JWT signing secret or service-role key.
3. Frontend build variables: `VITE_SUPABASE_URL` with the same URL and
   `VITE_SUPABASE_ANON_KEY` with a **public publishable key or legacy anon key**.
   Keep `VITE_API_BASE_URL` and `VITE_DEMO_MODE=false`. Never use a service-role or
   secret key as this value. Rebuild Vercel after changing public configuration.
4. Keep the exact production frontend origin in `CORS_ALLOWED_ORIGINS`. CORS now
   permits the Authorization header and PATCH; it still does not authenticate users.
5. Keep provider keys, DATABASE_URL and filesystem configuration on Railway only.

Missing auth configuration fails closed. The login screen explains unavailable
configuration and offers the public recorded demo at `/?demo=true`. This path is
explicitly labeled and does not call live session, OCR, vision or reasoning APIs.

### Additive database migration

Back up the database before the approved release. **Do not reset it or re-ingest.**
The migration adds nullable `owner_user_id` (UUID) and `session_name` (text) to
`equipment_sessions`, a name constraint, an owner/updated-at index, and child-table
triggers that update the existing parent timestamp after changes. No existing rows
are deleted. Existing ownerless sessions remain stored but cannot be accessed or
claimed through authenticated endpoints. Any future legacy ownership assignment
requires a separate, audited administrative decision; this release adds no claim API.

For the existing Railway database, apply the migration from the **new reviewed
image**, before routing traffic to the authenticated backend. After deployment is
approved, configure this as a Railway pre-deploy command for that release:

```sh
PYTHONPATH=backend python -m app.db.migrate_user_sessions
```

It is transactional, uses an advisory lock and is safe to rerun. It must run on
Railway, where the private DATABASE_URL resolves. Do not use `railway run` expecting
remote execution. For a brand-new empty database, first initialize the existing
Step 1–4 tables with the existing setup, then apply the migration before use.

Local PowerShell (after initializing the existing tables):

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m app.db.migrate_user_sessions
```

Release order after review: back up → apply additive migration → deploy authenticated
backend → deploy configured frontend → test two separate users, email confirmation,
private photo/citation access, session history and follow-up. There may be a brief
login-required window for old clients; no live infrastructure was changed during
implementation. Do not roll back to an unauthenticated backend once private sessions
exist, because the old UUID-only routes would expose them.

### Session API and limitations

- `POST /sessions` requires `{ "session_name": "ACS880 Fault 5091" }`; verified JWT
  identity sets the owner. Extra ownership fields are rejected.
- `GET /sessions?limit=50&offset=0` lists only your sessions, most recently updated
  first (maximum page size 100).
- `GET /sessions/{id}` returns owned metadata; `PATCH /sessions/{id}` renames it.
- Every existing child route requires the same owner check, including image bytes,
  visual context, source excerpts, troubleshooting runs and follow-ups. Missing and
  foreign IDs both return 404. `/health` remains public; production audit restrictions
  and upload/path limits still apply.

Names are trimmed, 1–100 characters; duplicate names are allowed. The name dialog
creates nothing until confirmed. Cancelling or failure preserves drafts. Lazy creation
is shared by concurrent actions. An explicit new case resets drafts only after success.
My Sessions reopens saved state using GETs only; it does not repeat paid analysis.
Photo bytes are fetched with Authorization and displayed through temporary object URLs,
which are revoked on unmount. Tokens are never put in image URLs or application logs.

The Supabase SDK stores browser auth state to restore sessions; XSS or a compromised
browser can steal it. Keep dependencies reviewed and use trusted devices. Logout clears
local auth/workspace, but an already issued bearer JWT can remain valid until expiry;
local JWKS verification does not provide immediate revocation. Set a suitably short
access-token lifetime in Supabase. Password reset and account administration remain
Supabase-managed and are not added as FieldTrace product features here. No real
Supabase account/email flow was exercised by mocked automated tests; verify it before
production release. The global single-instance rate limiter remains shared by all users.

For exact Supabase URLs, email settings and the real two-user validation procedure,
see [Supabase readiness review](SUPABASE-READINESS.md).

### Deleting private sessions

`DELETE /sessions/{session_id}` authenticates and locks an owner-scoped SQL row.
The transaction deletes the parent and uses existing foreign-key cascades for images,
findings, troubleshooting state and runs. Measurements, checks, follow-ups, retrieved
history and citations are JSON in those rows; shared manuals/chunks/catalog stay intact.
No schema migration or provider call is required for deletion.

Only after commit, recorded UUID image files directly under `UPLOAD_ROOT/{session_id}`
are unlinked. Missing files are harmless. Traversal, redirected paths and unexpected
filenames are skipped. No recursive directory deletion is used. Database failure leaves
files untouched. If file cleanup fails, the API still reports successful database
deletion with `file_cleanup_pending=true`; the UI warns and server logs identify the
session UUID for administrator cleanup. Such leftover files are inaccessible through
session APIs but remain on disk until an administrator removes them. No automatic retry
queue is implemented. Empty session directories may remain. Upload storage must be
server-controlled; concurrent hostile filesystem mutation is outside this prototype's
threat model. Existing upload transactions lock the same parent row before writing.

### Saving workspace drafts

The active named session exposes GET/PUT `/sessions/{session_id}/draft`, guarded by
verified ownership and a parent-row lock. The bounded, extra-field-forbidding payload
contains model text, symptom text, follow-up text, entry type and partial measurement
fields. It is a replaceable `workspace_draft` in the existing troubleshooting inputs
JSON, so this feature needs no schema migration. GET falls back to existing entered
model text and the latest submitted symptom for sessions without a saved draft.

Typing debounces silently for 850 ms; Save flushes immediately. Writes are serialized and bound
to the captured session ID; leaving/switching cases waits for pending draft saves.
Logout/unmount cancels pending timers, and completed requests cannot update another
account's UI. Use manual Save and wait for Saved successfully before logging out or closing the
page; unsent edits are not durable. Simultaneous edits in separate browser tabs use last-write-wins semantics.
Failed saves retain on-screen text and offer manual retry. No new session is created.

Draft saves do not append partial symptoms/checks, alter equipment confirmation,
increment the reasoning input revision, or invalidate results. Retrieval fingerprints
exclude workspace drafts. Run/Submit update still submits the completed input through
existing endpoints; merely saving a draft never invokes providers or retrieval.
Already-submitted notes/checks/measurements and history remain untouched. Rename saves
the name separately; uploaded photos are already durable and are not re-uploaded by
auto-save. Manual Save also uploads queued photos and notes, one file per request,
without OCR, analysis or troubleshooting. Acknowledged uploads leave the queue and
are not retried; failed files remain queued. Session switching is blocked during
manual Save, and logout stops subsequent queued uploads. Successful manual feedback
clears after 2.5 seconds; failed saves retain drafts and show a retry message.

### Photo persistence and removal

The browser hashes original file bytes with SHA-256 to skip duplicates in the active
session queue or saved list. The backend independently computes the hash, locks the
session and enforces a unique `(session_id, content_sha256)` index. Retrying after a
lost response reuses the existing image ID and file, without overwriting its note or
analysis. Identical filenames with different bytes remain separate photos. Hashes
are exposed only through owner-authorized session endpoints, never a global lookup.

The additive, repeatable migration is `PYTHONPATH=backend python -m
app.db.migrate_image_fingerprints` (PowerShell: set `$env:PYTHONPATH='backend'`, then
run `python -m app.db.migrate_image_fingerprints`). Existing vision initialization
also invokes it. Run this against the intended database before serving the updated
application; no production migration has been performed as part of local work.
The nullable column preserves all legacy images, including existing duplicates.
Legacy hashes are read from contained original files and assigned lazily on upload;
existing duplicate copies remain available for explicit user removal.

Saved photos show **Saved · Not analyzed**, with explicit Inspect / Analyze and
Remove actions. Saving does not run providers. Owner-only DELETE
`/sessions/{session_id}/images/{image_id}` removes the image record and its findings,
rebuilds aggregates from remaining photos, and invalidates the current troubleshooting
result. Historical run snapshots remain historical. Shared manuals are untouched.
After the database transaction commits, cleanup unlinks only the recorded UUID file
inside the session directory; redirected/outside paths are refused. Missing files
are harmless. Partial cleanup returns `file_cleanup_pending` and a UI warning;
an administrator must review residual files (there is no background cleanup retry).

### Limited-evidence equipment identification

Model text is optional. Identification uses selected queued/saved photos, cached local
OCR, and (when there is no strong exact nameplate) one multi-photo identity extraction
request through the configured `VISION_PROVIDER` adapter. Existing OpenAI/Gemini model
and key settings apply. The frontend explicitly sends `use_visual=true`; API clients
can omit this flag for OCR-only identification. Identification now counts against the
production provider-call budget. Saving, reopening, and changing photo selection do
not call a provider. No credentials are added to browser configuration.

The visual request returns observed text/features and provisional identity candidates,
separately from visible-abnormality analysis. Deterministic catalog matching chooses
exact observed type, supported model, family, manufacturer, or insufficient evidence.
Strong readable nameplate text takes precedence over partial text, typed identity and
appearance. Symptoms are never identity inputs. Appearance alone cannot confirm a
subtype or invent a full type code; family-only cards ask for readable model evidence
before model-filtered troubleshooting. HIGH/MEDIUM/LOW are ordinal evidence labels.
A strong nameplate remains HIGH even when weaker typed text conflicts; the conflict
is still shown for explicit technician review. A full observed SKU is not catalog-validated.

Up to 30 selected photos are fused in one request. Byte-identical inputs are counted
once. OCR is reused by content hash and role; validated visual observations are reused
for the same ordered image hashes. Failure leaves readable OCR available with a visible
unavailability notice, never fabricated identity evidence. Visual recognition remains
fallible; mocked tests establish contracts, not real-photo identification accuracy.

Before running updated code against an existing database, apply the repeatable additive
migration: `PYTHONPATH=backend python -m app.db.migrate_identification_evidence`.
PowerShell: `$env:PYTHONPATH='backend'; python -m app.db.migrate_identification_evidence`.
Startup initializers also apply it. It adds `equipment_sessions.identification_evidence`
(JSONB) and nullable `session_images.use_for_identification`. No rows are removed.
Legacy nameplates default to selected; other legacy views can be selected explicitly.
New queued photos default to selected, and saving persists that choice. Owner-only
PATCH `/sessions/{session_id}/images/{image_id}/identification` changes selection without
uploading or analyzing the photo. Existing catalog entries and shared corpus are unchanged.
