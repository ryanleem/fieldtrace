# FieldTrace judge demo — about 4–5 minutes

Use a live workspace on port 5173 and a clearly labeled replay tab on port 5174.
Rehearse before presenting; model latency varies. Never call recorded output a fresh
analysis. If live calls are slow, explicitly switch to the recorded example.

Presenter-ready click/type/say instructions: [ABB demo script](docs/ABB-DEMO-SCRIPT.md).

## Intro — 20 seconds

“FieldTrace connects physical ABB equipment to the right technical documentation.
Instead of starting with a manual search, a technician can start with the equipment
in front of them. We combine confirmed identity, visible observations and symptoms,
then verify technical claims against retrieved ABB evidence.”

## 1. ACS880 fault 5091 — about 2 minutes

1. Open a fresh live workspace. Immediately enter `ABB ACS880-01` in **Model text,
   if known** and `Drive shows fault 5091` in **What problem are you seeing?**.
   **Add equipment photos** is already usable; selection queues files locally.
   Do not click Start new troubleshooting session as a prerequisite. If an old
   case restores, use that button only to reset before the demonstration.
   Use a genuine readable nameplate for OCR, or disclose the typed-model route.
   Do not pass a generic reference photograph off as an ABB nameplate or drive.
2. Click **Detect equipment / read nameplate**. This creates/reuses the backend
   session automatically and preserves typed model/symptom drafts. Review the
   candidate and **Confirm equipment**. Queued originals are saved on confirmation.
3. Click **Run troubleshooting**, now enabled. The symptom was editable before
   confirmation; only running the troubleshooting was gated.
4. While it runs: “The confirmed equipment scopes the manual search. Fault codes
   are preserved exactly. Evidence is reviewed before technical claims are displayed.”
5. Show the supported STO circuit signal interruption direction and **MEDIUM**.
   “This is a supported troubleshooting direction, not proof of a physical fault.”
6. Open the fault 5091 citation: show the ACS880 manual's physical page 525 and exact
   stored text. Point to **Open manual page**. Do not claim invented highlights.
7. Show the next question. Submit `STO wiring has not yet been checked.`
8. Show the same session and saved follow-up. “Retrieval and verification run again;
   the nameplate and photos are not processed again.”

If live output differs from the rehearsed result, acknowledge it. Do not adjust the
symptom or prompts to force MEDIUM. Use the labeled replay of a previously validated ACS880 result, with disclosure
in the banner. It is not fresh analysis; [replay provenance](frontend/public/REPLAY-PROVENANCE.md)
documents how the prepared example was assembled.

## 2. Motor uncertainty — 45 seconds

Switch visibly to the replay tab and select **Motor uncertainty fixture**.
Read its label: **Temporary motor-family fixture for reasoning validation only.**
It is the recorded motor-overheating run, with a supplied dust observation. It does
not demonstrate supported motor identification or a new photo inference.

Show **LOW**, no primary diagnosis, and the question about measured temperature,
location and operating conditions. “When documentation and observations are not
strong enough, FieldTrace does not invent a diagnosis. It asks for more information.”
The historical relevance review stopped this run before candidate generation and
claim verification; do not claim those stages were exercised in this example.

## 3. Visible evidence — 45–60 seconds

Show the validated generic connector image and findings via **Recorded visible finding**,
or upload `frontend/public/replay-photo-01.jpg` in a clearly labeled controlled live
test session. Use `close-up` and a note saying it is a generic reference photograph,
not proof of ABB model identity. Click **Save photos & inspect visible conditions**.

Show corrosion/discoloration observations with image/view association and ordinal
visual confidence. “These are visible observations, not evidence of an invisible
electrical or mechanical failure. They join the confirmed equipment and technician
symptom in the retrieval context.” The Step 6 live integration audit verifies that
transfer; a generic photo is not validation of an actual ACS880 physical condition.

For a short presentation, use the disclosed recording for this stage rather than
waiting for another provider call. No hidden failure should be inferred from the image.

## Close — 15 seconds

“FieldTrace follows an equipment-specific, persistent inspection session: physical
observations, exact fault codes, verified technical claims, source pages and honest
uncertainty. The technician can inspect the evidence and continue the investigation.”

Reset with **Start new troubleshooting session** in live mode or **Reset demo** in
replay mode. Neither deletes the corpus or configuration. Old saved live sessions
remain in the database; the screen and its drafts are cleared.

## Exact launch commands

From the repository root, start your configured database (choose one method):

```powershell
docker compose up -d --wait
```

For this existing Windows native installation, if stopped:

```powershell
& .\work\native-postgres\pgsql\bin\postgres.exe -D .\work\native-postgres\data -p 55432 -h 127.0.0.1
```

Do not start both on the same port. Then start the backend in another terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Live frontend, separate terminal:

```powershell
cd frontend
Remove-Item Env:VITE_DEMO_MODE -ErrorAction SilentlyContinue
npm run dev
```

Open http://127.0.0.1:5173. Confirm the header says **LOCAL WORKSPACE**, not replay.
Also remove any `VITE_DEMO_MODE=true` entry from a private frontend env file if present.

Explicit fallback, another terminal:

```powershell
cd frontend
$env:VITE_DEMO_MODE='true'
npm run dev -- --port 5174
```

Open http://127.0.0.1:5174 and select **ACS880 fault 5091**. No database or provider
is needed for replay. A cold installation still needs `npm ci` first.

Audit commands with the respective servers running:

```powershell
cd frontend
$env:UI_EVALUATION_DIR='../data/evaluation/ui/step6'
node live-validation.mjs
node replay-validation.mjs
```

The live script spends configured provider credits. Replay validation spends none.
Screenshots, final states and a short automated replay walkthrough video are saved
under `data/evaluation/ui/step6/` (ignored local artifacts, not fake screenshot data).
