# FieldTrace team handoff

The private GitHub repository is live:

https://github.com/ryanleem/fieldtrace

For normal setup, start with the main [README](README.md).

## How to get access

Ryan must invite each teammate to the private repository.

On GitHub:

1. Open the repository.
2. Go to **Settings**.
3. Open **Collaborators**.
4. Click **Add people**.
5. Enter the teammate's GitHub username.
6. Send the invitation.

The teammate must accept the GitHub invitation before cloning the private repository.

## After you are invited

Clone the repository:

```powershell
git clone https://github.com/ryanleem/fieldtrace.git
cd fieldtrace
```

Then follow the setup steps in [README.md](README.md).

## Collaboration rule

Do not edit `main` directly.

Create a branch:

```powershell
git checkout main
git pull
git checkout -b your-branch-name
```

After making a focused change:

```powershell
git add .
git commit -m "Describe your change"
git push -u origin your-branch-name
```

Then open a Pull Request into `main`.

## What is not stored in GitHub

Each person must create their own local setup for:

- `.env`
- API keys
- PostgreSQL data
- downloaded ABB PDFs
- model caches
- local uploads/evaluation output

Never send personal API keys through GitHub, Slack, Discord, or group chat.

## Current validation

Latest validated baseline:

- 139 backend tests
- 4 frontend unit tests
- 7 browser tests
- frontend production build passes

## ABB manuals

The project downloads and ingests the supported manuals with:

```powershell
.\.venv\Scripts\python.exe scripts/download_manuals.py
.\.venv\Scripts\python.exe scripts/ingest_manuals.py
```

The PDFs themselves are intentionally excluded from Git.

## Where to look

- `README.md` — start here
- `CONTRIBUTING.md` — collaboration rules
- `backend/` — FastAPI backend
- `frontend/` — React UI
- `STEP3.md` — visual inspection
- `STEP4.md` — troubleshooting engine
- `STEP5.md` — technician UI
