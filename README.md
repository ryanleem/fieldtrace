# FieldTrace / ABB Guardian

FieldTrace connects equipment identification, visible photo observations and a technician's
symptom to real ABB manual evidence. Its React workspace shows suspected causes,
documented checks, confidence, follow-up questions and exact source excerpts.
Steps 1–5 are implemented, with Step 6 demo polish; this remains a supervised local prototype.

## Why FieldTrace

FieldTrace combines confirmed equipment identity, physical photo observations and
technician symptoms in a persistent troubleshooting session. Hybrid retrieval finds
ABB evidence; technical claim verification and uncertainty handling determine what
can be presented. Exact citations let technicians inspect the source and follow up
without processing their photos again. [Demo script](DEMO.md) ·
[Pre-demo and emergency checklist](DEMO-CHECKLIST.md).

The identification catalog supports **ACS880-01, ACS580-01 and ACH580-01**.
The corpus supports ACS880 troubleshooting and motor-family retrieval, but motor
identification is not supported. ACS580/ACH580 currently have no matching manuals.

## Architecture

- `backend/app/`: FastAPI, local OCR, confirmation, vision, persistent sessions,
  pgvector semantic + PostgreSQL keyword search with RRF, evidence review and claim verification.
- `frontend/`: React, Vite and TypeScript workspace and source viewer.
- `data/manuals/manifest.json`: official URLs and verified document hashes.
- `data/equipment_catalog.json`: supported identities; `scripts/`: setup and evaluation tools.

Flow: confirm equipment → collect visible observations and symptom → hybrid retrieval
→ evidence review → claim generation/verification → answer or follow-up question.
Text follow-ups reuse the session without rerunning OCR or vision.

## Prerequisites

Git, Python **3.11–3.12** (3.12 tested), Node.js **22.12+ or 24 LTS** (24 tested),
npm and Docker with Compose. Python 3.13 is unsupported by the pinned OCR package.
First setup downloads dependencies, model weights and PDFs. Embeddings and OCR run
locally; live provider calls need funded API keys.

Commands use PowerShell from the repository root unless stated otherwise.
On Linux/macOS use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

## Backend setup and environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
```

Do not overwrite an existing `.env`. Edit your private copy:

| Variable | Purpose |
| --- | --- |
| POSTGRES_PASSWORD | Your local password for Compose, native setup and the default backend connection. |
| DATABASE_URL | Optional full connection override; takes precedence over the default connection. |
| OPENAI_API_KEY | OpenAI vision and Step 4 reasoning; blank for mocked tests. |
| GEMINI_API_KEY | Gemini vision key. |
| VISION_PROVIDER | openai or gemini. |
| VISION_MODEL | OpenAI vision model. |
| GEMINI_VISION_MODEL | Gemini vision model. |
| TROUBLESHOOTING_MODEL | OpenAI reasoning model, independent of vision selection. |
| EMBEDDING_MODEL / EMBEDDING_REVISION | Pinned local embedding identity; keep consistent with the corpus. |

The example also documents limits/timeouts. Optional path overrides:
`MANUALS_DIR`, `PROCESSED_DIR`, `MODEL_CACHE`, `UPLOADS_DIR`.
Defaults belong to your checkout. Never put secrets in frontend `VITE_*` variables.

```dotenv
POSTGRES_PASSWORD=REPLACE_WITH_LOCAL_DB_PASSWORD
# Optional, only for a custom/existing database:
# DATABASE_URL=postgresql+psycopg://guardian:REPLACE_WITH_LOCAL_DB_PASSWORD@127.0.0.1:55432/guardian
```

Replace the placeholder with your own password. The backend builds the local URL and
encodes special characters automatically. If setting DATABASE_URL yourself, percent-encode
its password and keep it synchronized. Without either credential setting there is no
implicit password; password-authenticated database connections will fail.

## PostgreSQL + pgvector

Each teammate runs their own database and named Docker volume:

```powershell
docker compose up -d --wait
docker compose exec db psql -U guardian -d guardian -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Compose creates the `guardian` user and database using PostgreSQL 17 with pgvector.
Host port **55432** binds to loopback; container port is 5432.
Ingestion initializes retrieval tables. API startup initializes all session schemas
and the catalog. Existing `init_db`, `init_equipment`, `init_vision` and
`init_troubleshooting` modules own idempotent schema setup; there is no Alembic history.

For your own installed PostgreSQL, install matching pgvector binaries and use psql
as administrator: `CREATE ROLE guardian LOGIN;`, `\password guardian`,
`CREATE DATABASE guardian OWNER guardian;`, `\connect guardian`, then
`CREATE EXTENSION IF NOT EXISTS vector;`. Set DATABASE_URL to the actual port.
The application role needs permission to create tables and indexes.

`docker compose stop` preserves data. Editing .env does not change credentials in an
existing volume; change the PostgreSQL password and URL together. Don't delete the
volume as routine troubleshooting. The optional Windows native setup uses the same
POSTGRES_PASSWORD from the process environment or private .env (environment wins):

```powershell
.\.venv\Scripts\python.exe scripts/setup_native_postgres.py
```

It requires a nonempty password and rejects the example placeholder and line breaks.
The temporary initdb password file is removed on success or failure. Existing cluster
passwords are never reset by this script: configure the current password or change it
through PostgreSQL first. Do not run both database methods on port 55432.

## ABB manuals and ingestion

Download PDFs locally; do not commit them.

| Manual | Revision / physical pages | Official source |
| --- | --- | --- |
| ACS880 Primary Control Program Firmware Manual | V / 604 | [ABB PDF](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf) |
| Manual for Induction Motors and Generators | L / 132 | [ABB PDF](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf) |

```powershell
.\.venv\Scripts\python.exe scripts/download_manuals.py
.\.venv\Scripts\python.exe scripts/ingest_manuals.py
```

First ingestion downloads pinned embedding weights. Identical documents are skipped
on repeat ingestion. A hash mismatch requires reviewing the changed official PDF,
not bypassing verification. Citations use physical PDF page positions.

## Run the backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs; health: http://127.0.0.1:8000/health.
Keep loopback binding: this prototype has no multi-user authentication.

## Run the frontend

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies /api to port 8000. For another port set
`$env:BACKEND_URL='http://127.0.0.1:8001'` before starting Vite.
See frontend/.env.example and [Step 5](STEP5.md) for the complete workflow.

Explicit recorded fallback: set `$env:VITE_DEMO_MODE='true'` and restart Vite.
Remove the variable and restart to return to live mode. Replay is read-only and labeled.
Prepared replay and its licensed photo are included. Regenerating it with
`scripts/prepare_ui_replay.py` requires original local validation artifacts;
it is not a fresh-clone setup step.

## Switch vision providers

Edit the backend .env and restart FastAPI:

```dotenv
VISION_PROVIDER=openai
VISION_MODEL=gpt-4.1-mini-2025-04-14
OPENAI_API_KEY=YOUR_OPENAI_KEY
```

Or:

```dotenv
VISION_PROVIDER=gemini
GEMINI_VISION_MODEL=gemini-2.5-flash
GEMINI_API_KEY=YOUR_GEMINI_KEY
```

Gemini replaces only vision; Step 4 still needs OPENAI_API_KEY.
Both adapters return the same visible-observation schema. Provider failure never
means healthy equipment and never creates fallback findings.

## Tests

With your database and corpus ready, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest --integration --corpus -q --basetemp work/pytest-team
```

Full baseline: **142 tests** (127 earlier tests, two viewer tests, ten database-configuration tests and three verifier-gap regressions).
Integration tests use isolated schemas. Unit-only: `python -m pytest -q`;
that intentionally skips database/corpus tests.

```powershell
cd frontend
npm run build
npm test
npm run test:e2e
```

Frontend: four unit tests and fourteen browser tests. Browser tests mock API responses
and start Vite if needed. Install Chrome or set CHROME_PATH to your Chromium executable
(default targets Windows Chrome). Automated tests don't spend API credits.
Live evaluations are separate opt-in paid runs.

## Team Development Workflow

After accepting the repository invitation:

```powershell
git clone https://github.com/YOUR_OWNER/fieldtrace.git
cd fieldtrace
git checkout main
git pull --ff-only
git checkout -b frontend-ui
# Alternatives: git checkout -b source-viewer
#               git checkout -b demo-testing
# Make a focused change and run the tests above.
python scripts/check_repository.py
git status --short
git add .
git diff --cached --stat
git diff --cached
# Review before committing.
git commit -m "Describe the focused change"
git push -u origin frontend-ui
```

Open a pull request against main, describe the change and test results, and request
a teammate's review. Merge only after review and passing tests. Each teammate uses
a separate branch and local database. Coordinate API changes rather than all editing
main directly. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Suggested Team Split

Suggestion only, not exclusive ownership:

- Integration / backend troubleshooting: API contracts and end-to-end flow.
- Frontend UI: intake, results and responsive behavior.
- Source viewer / citations: exact excerpts and provenance.
- Demo scenarios / testing: regression coverage and honest live/recorded demos.
- Documentation / deployment / presentation: onboarding and demo preparation.

## Collaboration Safety

Each teammate uses their own .env. Never commit secrets or share personal keys in
Discord, Slack or GitHub. Keep main working; use pull requests, review and tests
before merge. A private repository is not a secret store. Rotate any exposed real
credential even if it is later deleted.

Ignored files include local databases, uploads, raw evaluation results, PDFs, virtual
environments, dependencies and caches. Source, examples, catalog, manifests, licensed
evaluation images and prepared replay remain eligible. Run
`python scripts/check_repository.py`: it prints file/line categories, never matched
secret values. Heuristics cannot prove every possible secret is absent.
See [GitHub handoff](GITHUB-HANDOFF.md) for initial publishing and invitations.

## Common setup problems

- Database refused: start it; check port 55432 and matching passwords.
- Compose asks for POSTGRES_PASSWORD: edit private .env. New setup has no shared
  password fallback; existing native installations are unchanged.
- Missing vector: install matching pgvector or use the Compose image.
- Model/corpus mismatch: preserve pinned settings or create another database and reingest.
- First model download: allow Hugging Face access; unset HF_HUB_OFFLINE on a fresh clone.
- HTTP 429/quota: check billing. Switching vision does not switch Step 4 reasoning.
- Port 5173/8000 occupied: stop the previous process or coordinate port overrides.
- OCR with Python 3.13: recreate the environment with Python 3.12.
- Browser won't launch: set CHROME_PATH to an installed Chrome/Chromium binary.
- Old report JSON/screenshot links missing: raw outputs are intentionally local;
  narrative reports and curated replay remain included.

## Technical references

[Step 1–2 historical detail](STEP1-2-REFERENCE.md), [Step 3](STEP3.md),
[Step 4](STEP4.md), [Step 5](STEP5.md). This README is the current onboarding entry point;
older reports describe their original validation environment.
