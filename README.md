# FieldTrace

FieldTrace is our ABB Accelerator prototype for **multimodal industrial troubleshooting**.

A technician can:
1. upload equipment/nameplate photos,
2. confirm the equipment model,
3. enter a symptom or fault code,
4. get visible photo findings,
5. run troubleshooting against real ABB manuals,
6. see the suspected cause, confidence, recommended checks, follow-up questions, and exact sources.

The system is designed to avoid guessing when the evidence is weak.

## Why FieldTrace

FieldTrace goes beyond chat over manuals by combining confirmed equipment identity,
physical photo observations, and technician symptoms or fault codes. Hybrid ABB manual
retrieval, claim verification, and uncertainty handling support answers with exact
citations. Persistent follow-up keeps the investigation in the same session.

See the [demo script](DEMO.md) and [demo checklist](DEMO-CHECKLIST.md).

## Start here if you are a teammate

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

Do not work directly on `main`.

```powershell
git checkout main
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
- semantic + keyword hybrid search
- citation-backed retrieval
- nameplate/OCR equipment identification
- equipment confirmation
- multi-photo visible issue analysis
- troubleshooting session state
- evidence review
- technical claim verification
- High / Medium / Low confidence
- follow-up troubleshooting
- exact source viewer
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

Latest validated baseline:
- **142 backend tests**
- **4 frontend unit tests**
- **21 browser tests**

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

See [Vercel + Railway deployment](docs/DEPLOYMENT.md) for cloud configuration,
persistent uploads and one-time corpus ingestion. The local setup above is unchanged.
