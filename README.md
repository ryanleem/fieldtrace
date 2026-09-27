# FieldTrace

FieldTrace is our ABB Accelerator prototype for **multimodal industrial troubleshooting**.

## Open FieldTrace

**Live site:** https://fieldtrace-blush.vercel.app

> The live production site currently reflects the deployed production backend. The newest authentication, saved-session, OCR/manual-coverage, and equipment-confirmation fixes are on `feat/scanned-manua-l-ocr-coverage` until they are deployed and merged.

A technician can:
1. upload equipment/nameplate photos,
2. confirm the equipment model,
3. enter a symptom or fault code,
4. get visible photo findings,
5. run troubleshooting against real ABB manuals,
6. see the suspected cause, confidence, recommended checks, follow-up questions, and exact sources.

The system is designed to avoid guessing when the evidence is weak.

## Live demo

FieldTrace is deployed for the ABB Accelerator prototype demo:

- **Frontend:** https://fieldtrace-blush.vercel.app
- **Backend health:** https://fieldtrace-production.up.railway.app/health
- **Hosting:** Vercel frontend + Railway FastAPI backend + Railway PostgreSQL/pgvector
- **Indexed corpus:** 2 ABB manuals, 736 pages, 11,085 chunks
- **Uploads:** persistent Railway volume

This is a supervised hackathon prototype, not a production service. Public API usage can consume provider credits and the deployment may be paused after the event.

## Why FieldTrace

FieldTrace goes beyond chat over manuals by combining confirmed equipment identity,
physical photo observations, and technician symptoms or fault codes. Hybrid ABB manual
retrieval, claim verification, and uncertainty handling support answers with exact
citations. Persistent follow-up keeps the investigation in the same session.

See the [demo script](DEMO.md) and [demo checklist](DEMO-CHECKLIST.md).

## Accounts and saved cases (local implementation)

Live use now requires Supabase Auth configuration. Supabase handles login only;
FieldTrace data stays in Railway PostgreSQL. Signed-in technicians can name, rename
and reopen their cases from **My Sessions**. The name dialog preserves fresh intake
drafts until a case is created. Use `/?demo=true` for the public labeled replay.

Set backend `SUPABASE_URL` and frontend `VITE_SUPABASE_URL` /
`VITE_SUPABASE_ANON_KEY` (public key only), then apply the additive session migration.
See [authentication setup and migration](docs/DEPLOYMENT.md#authentication-and-saved-sessions-pending-review-not-deployed).
These changes have not been deployed; the current hosted demo is unchanged.

For optional scanned-manual OCR and the indexed-manual preflight, see
[OCR and manual coverage](docs/SCANNED-MANUAL-OCR-AND-COVERAGE.md).

## Start here if you are a teammate

The current integration branch is **`feat/scanned-manua-l-ocr-coverage`**. Start from that branch for new work until the pending changes are merged to `main`.

You do **not** need Ryan's local files. Everything needed to collaborate is in this private repository, except:
- API keys,
- local database data,
- downloaded ABB PDFs,
- local model/cache files.

Each teammate uses their own local `.env` and local PostgreSQL database.

### 1. Clone the repository

```powershell
git clone https://github.com/ryanleem/fieldtrace.git
cd fieldtrace
```

### 2. Create your own branch

Do not work directly on `main` or the shared integration branch. Base new work on the current integration branch:

```powershell
git fetch origin
git switch feat/scanned-manua-l-ocr-coverage
git pull
git checkout -b your-branch-name
```

Examples:

```text
frontend-ui
source-viewer
demo-testing
fix-upload-flow
```

### 3. Backend setup

Requirements:
- Python 3.11 or 3.12
- Docker Desktop
- PostgreSQL + pgvector through Docker
- an OpenAI API key for live troubleshooting
- optional Gemini API key for Gemini vision

Create the Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
```

Open `.env` and set your own values.

At minimum for a normal local setup:

```dotenv
POSTGRES_PASSWORD=choose_your_own_local_password
OPENAI_API_KEY=your_openai_key
```

Optional Gemini vision:

```dotenv
VISION_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_VISION_MODEL=gemini-2.5-flash
```

Never commit `.env` or API keys.

### 4. Start PostgreSQL

```powershell
docker compose up -d --wait
docker compose exec db psql -U guardian -d guardian -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

The local database runs on port **55432**.

### 5. Download and ingest the ABB manuals

The PDFs are intentionally not stored in GitHub.

```powershell
.\.venv\Scripts\python.exe scripts/download_manuals.py
.\.venv\Scripts\python.exe scripts/ingest_manuals.py
```

Current manuals:

- [ACS880 Primary Control Program Firmware Manual](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf)
- [Manual for Induction Motors and Generators](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf)

### 6. Run the backend

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Backend API:
- http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

### 7. Run the frontend

Open another PowerShell window:

```powershell
cd frontend
npm ci
npm run dev
```

Then open:

```text
http://127.0.0.1:5173
```

## Current prototype status

Implemented:
- ABB manual ingestion
- optional OCR for image-only/scanned manual pages
- indexed-manual coverage preflight before troubleshooting
- semantic + keyword hybrid search
- citation-backed retrieval
- nameplate/OCR equipment identification
- equipment confirmation with persisted reopen/refresh state
- multi-photo visible issue analysis with explicit per-photo re-analysis
- visual findings label the supporting uploaded photo as evidence
- troubleshooting session state
- evidence review
- technical claim verification
- High / Medium / Low confidence
- follow-up troubleshooting
- exact source viewer
- relevant ABB passages remain reviewable on low-evidence results without being presented as proof of a diagnosis
- technician-facing React UI

Current equipment identification catalog:
- ACS880-01
- ACS580-01
- ACH580-01

Important limitation:
- the motor manual is searchable,
- but motor model identification is not currently part of the supported catalog,
- ACS580/ACH580 identification exists but matching troubleshooting manuals are not yet included.

## Project structure

```text
backend/                  FastAPI backend
frontend/                 React + Vite + TypeScript frontend
data/equipment_catalog.json
data/manuals/manifest.json
scripts/                  setup, ingestion, evaluation, demo tools
README.md                 main setup guide
CONTRIBUTING.md           collaboration rules
STEP3.md / STEP4.md / STEP5.md
                         detailed implementation notes
```

## How we collaborate

The normal workflow is:

```text
main
  ↓
your feature branch
  ↓
commit changes
  ↓
push branch
  ↓
open pull request
  ↓
review
  ↓
merge into main
```

Commands:

```powershell
git checkout main
git pull
git checkout -b your-branch-name

# make your changes

git status
git add .
git commit -m "Describe what you changed"
git push -u origin your-branch-name
```

Then open a Pull Request on GitHub into `main`.

Do not push unfinished work directly to `main`.

## Suggested team split

Possible ownership:

- **Backend / integration** — troubleshooting pipeline and API integration
- **Frontend** — technician UI and workflow
- **Sources / citations** — source viewer and evidence display
- **Testing / demos** — demo scenarios, regression testing, failure cases
- **Presentation / deployment** — ABB prototype submission, demo flow, documentation

These are suggestions, not strict boundaries.

## Tests

Backend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Full database/corpus validation:

```powershell
.\.venv\Scripts\python.exe -m pytest --integration --corpus -q --basetemp work/pytest-team
```

Frontend:

```powershell
cd frontend
npm run build
npm test
npm run test:e2e
```

Latest validation on the current integration branch:
- **273 backend/integration/corpus/coverage tests passed**
- **42 frontend unit tests passed**
- **62 browser tests reported passing**; the local Playwright runner hung during shutdown and was interrupted after the tests completed
- frontend production build passed
- `git diff --check` passed

The backend corpus run used the real local ABB corpus: **2 manuals, 736 pages, 11,085 chunks**.

## Before you commit

Run:

```powershell
python scripts/check_repository.py
git status
git diff --cached
```

Do not commit:
- `.env`
- API keys
- passwords
- downloaded PDFs
- uploaded technician photos
- database files
- model caches
- `node_modules`
- Python virtual environments

See [CONTRIBUTING.md](CONTRIBUTING.md) for the collaboration rules.

## Need more technical detail?

The main README is intentionally kept simple.

Detailed implementation notes:
- [Step 1–2 reference](STEP1-2-REFERENCE.md)
- [Step 3 — visual inspection](STEP3.md)
- [Step 4 — troubleshooting engine](STEP4.md)
- [Step 5 — technician UI](STEP5.md)
- [Demo script](DEMO.md)
- [Demo checklist](DEMO-CHECKLIST.md)
- [Step 6 — demo validation](STEP6-VALIDATION.md)

## Cloud deployment

See [Vercel + Railway deployment](docs/DEPLOYMENT.md) for the deployed architecture,
public-demo safeguards, persistent uploads and corpus setup. The local setup above is unchanged.

For **both Vercel Production and Preview**, set these build variables separately:

- `VITE_SUPABASE_URL` — Supabase project HTTPS URL.
- `VITE_SUPABASE_ANON_KEY` — matching public publishable/anon key; never a service-role key.
- `VITE_API_BASE_URL` — compatible Railway backend HTTPS origin, without `/api`.
- `VITE_DEMO_MODE=false` — live mode; labeled replay remains at `/?demo=true`.

Preview variables may also have branch-specific overrides; check those for
`feat/scanned-manua-l-ocr-coverage`. Production settings do not fill Preview settings.
Vercel uses `npm run build:hosted` to reject incomplete live configuration. Rebuild
the intended preview after changing variables; an existing bundle does not update.
Use a compatible preview backend and authorize its frontend origin in Railway CORS
and Supabase redirect settings. See the deployment guide for scope and compatibility checks.
