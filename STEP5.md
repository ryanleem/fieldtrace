# Step 5 — Technician workspace

FieldTrace connects the existing FastAPI workflow to one React/Vite/TypeScript screen.
No Step 6 functionality, catalog expansion, or changes to the Step 1–4 reasoning
pipeline were made.

## Run locally (PowerShell)

Start in the `abb-guardian` repository. Reuse the configured `.env` and ingested corpus.
If the existing native database is stopped, run this in a separate terminal:

```powershell
& .\work\native-postgres\pgsql\bin\postgres.exe -D .\work\native-postgres\data -p 55432 -h 127.0.0.1
```

Start FastAPI from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```powershell
cd frontend
npm ci --cache ../work/npm-cache
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to FastAPI, so no separate backend or
CORS policy changes are needed. Set `BACKEND_URL` in the shell if using a different
backend port. Provider keys remain exclusively in the backend environment; never
put secrets in `VITE_*` variables. See the existing Step 3/4 guides for providers.

## Workflow and behavior

1. Start a session; the tab remembers its ID in sessionStorage.
2. Queue multiple JPEG/PNG/WEBP photos, assign views and optional notes. Mark
   nameplate photos for OCR, or enter supported model text.
3. Review suggested matches and mismatch warnings, then confirm. To preserve the
   existing image/equipment association rule, queued originals are uploaded after
   confirmation. Queued files are lost on reload; already uploaded files persist.
4. Inspect visible conditions, or save photos without analysis. Failed images remain
   visible and can be retried. Notes remain separate from model findings.
5. Enter the exact symptom/fault code and run troubleshooting. The UI displays the
   backend's final cause, rationale, checks, alternatives, citations and next question.
   LOW is a normal need-for-information state; provider failure is a separate state.
6. Open citation chips or source rows to view the exact stored chunk and provenance,
   with a link to the manual page. No artificial highlights or reconstructed pages.
7. Submit an answer, completed check or measurement. Only the follow-up endpoint is
   invoked; the existing session is updated without another OCR/matching/vision call.

Read-only backend additions: session-scoped image file serving, and a source endpoint
that permits only chunks actually cited in the selected run's final result. The source
response contains exact text and provenance, not audit prompts or candidate judgments.
These session checks are not authentication; this remains a local single-user prototype.

Timeout, rate-limit, transport and provider errors preserve saved state and provide
retry/refresh controls. After an ambiguous network timeout, refresh the session before
retrying because processing may still be running. No replay automatically substitutes
for live failures. The app does not expose raw internal reasoning.

## Explicit recorded fallback

Stop the frontend, then start it with:

```powershell
$env:VITE_DEMO_MODE='true'
npm run dev
```

The banner says **DEMO REPLAY · Not a fresh analysis**. Three read-only examples cover
ACS880 fault 5091, low evidence, and a visible corrosion finding. Upload and live calls
are disabled. The ACS880 replay includes the previously documented output-role guard
replay; it is not represented as an untouched fresh model response. Photo attribution
is displayed and documented in `frontend/public/REPLAY-PROVENANCE.md`.

Return to live mode by stopping Vite, removing the flag and restarting:

```powershell
Remove-Item Env:VITE_DEMO_MODE -ErrorAction SilentlyContinue
npm run dev
```

`scripts/prepare_ui_replay.py` regenerates these display-only records from saved
validation artifacts. It does not export internal provider prompts.

## Validation commands

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest --integration --corpus --basetemp work/pytest-step5-check -q
cd frontend
npm run build
npm test
npm run test:e2e
```

The backend suite passes **129 tests**: 127 existing tests plus two viewer integration
tests covering exact citation access, session isolation and safe image paths.
Four frontend unit tests and seven browser tests cover the complete workflow,
multi-image metadata, confirmation, findings, confidence, citation viewer, follow-up
without upstream reruns, low evidence, conflict warning, failure/retry and mobile layout.
Browser regression tests use explicit recorded API fixtures, not paid model calls.
Chrome is used locally; set `CHROME_PATH` for a different installed Chromium executable.

With both servers running in live mode, this opt-in script uses real configured
providers and may incur API charges:

```powershell
node live-validation.mjs
```

It saves final session states, request paths and screenshots under
`data/evaluation/ui/`. The generic connector reference photo tests visible inspection
and UI association only, not ABB equipment identification. Model text confirmation is
used for the live UI check. No motor is added to the supported catalog.

## Live workspace validation — 2026-09-20

OpenAI key presence was checked without printing its value. Both vision and
troubleshooting used `gpt-4.1-mini-2025-04-14`. No provider configuration change was
required. PostgreSQL was initially stopped; after restarting the existing database,
the full integration/corpus suite passed. No reasoning bug or prompt change was needed.

| Scenario | Observed outcome |
| --- | --- |
| ACS880 fault 5091 | Real browser → FastAPI → real corpus/provider. Suspected STO circuit signal interruption, MEDIUM, four sources. |
| Citation viewer | Exact stored fault 5091 chunk rendered; actual manual link includes page 525. |
| Follow-up | Same session retained, “STO wiring has not yet been checked.” saved; result recalculated at MEDIUM with updated citations. Identity/analysis request count stayed 2 before and after (identify + confirm); no OCR/vision rerun. |
| Visible inspection | Real generic connector photo, close-up label and separate note saved. Corrosion and discoloration returned, image-linked, with high visual confidence. Existing result correctly became stale when evidence changed. |
| Weak evidence | Separate confirmed ACS880 session; LOW, no primary cause, measurement follow-up question. |
| Failure/retry | Deterministic browser tests injected transport/provider/vision failures; preserved inputs and session, no fake findings, retry demonstrated. Not represented as a live provider outage. |
| Replay | All three recorded examples opened with explicit banner and zero `/api` requests. |

Live artifacts: `data/evaluation/ui/live-workspace.json`, `live-acs880.png`,
`live-source.png`, `live-photo.png`, `live-weak.png`. No API or network failure was
observed during these browser scenarios. The photo is a generic reference in a
controlled session, not an assertion that it depicts an ACS880. The next question
remained the backend's generic measurement question after the follow-up; the UI
deliberately does not embellish it. New live troubleshooting was not run after adding
the generic photo, to avoid treating it as an actual drive observation.

**Readiness:** suitable for a supervised local hackathon demo with working backend
services and the explicitly labeled replay fallback. Not a production or field-safety
validation.

## Files delivered

- `frontend/src/App.tsx`, `types.ts`, `api.ts`, `main.tsx`, `styles.css`: workspace,
  backend transport, typed state and industrial layout.
- Frontend package/lock, HTML, TypeScript/Vite/Vitest/Playwright configuration,
  `.env.example`, `.gitignore`, `src/api.test.ts`, `e2e/workspace.spec.ts`.
- `frontend/public/demo.json`, reference photo and `REPLAY-PROVENANCE.md`;
  `scripts/prepare_ui_replay.py`; opt-in `frontend/live-validation.mjs`.
- `backend/app/api/viewer.py`, router registration in `backend/app/main.py`,
  `backend/tests/test_viewer.py`: additive read-only integration only.
- This guide, README link, and saved UI evaluation artifacts.

## Remaining limitations

- Local single-user development server, not a production deployment or multi-user app.
- Upload UI uses the default backend limits (10 MB/image, 30 images/session).
- No embedded PDF renderer: exact extraction and original manual page link are shown.
- No image deletion, annotation editing, cross-tab synchronization or session browser.
- Provider output and availability remain variable; recorded fallback is deliberately
  read-only. A single successful live UI run is not a new diagnostic accuracy benchmark.
- Supported identity catalog remains ACS880-01, ACS580-01 and ACH580-01.
