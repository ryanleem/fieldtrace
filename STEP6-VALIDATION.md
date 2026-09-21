# Step 6 — Supervised demo audit

## Scope and delivered changes

Kept the industrial layout and existing architecture. Added concise photo/symptom,
visual-evidence and confidence guidance. Loading copy explains the bounded search,
review and verification work without pretending to know the server's current stage
or progress percentage. Old next questions are hidden when a result is stale.

Two Step 5 UI defects were corrected: reset now clears measurement type/value/location
and other drafts, and failed runs no longer display a LOW-confidence badge. LOW is
reserved for an actual evidence result. Source failures have a local Retry source
button. Live reset creates a new session; replay reset clears only the displayed
record. Old saved sessions, manuals, corpus and configuration are not deleted.

Replay now includes the actual saved motor-overheating reasoning fixture. Its banner
and equipment card distinguish it from supported equipment identification. The real
catalog is unchanged. The ACS880 replay remains the previously validated prepared
result, including its documented output-role guard replay; no new evidence was invented.

## Real bug found during live audit

The first photo-context run passed visible corrosion/discoloration into retrieval,
but the candidate rationale then said that these observations might affect STO
signal continuity. The cited ACS880 pages 525, 275 and 276 documented fault 5091
and STO parameters, not that corrosion-to-fault connection. The verifier called the
rationale SUPPORTED while admitting the detail was not explicitly stated.

Small targeted Step 4 fix:

- Existing verifier instructions now explicitly reject undocumented causal links
  from visual findings, including assertions softened with “may”.
- A SUPPORTED verdict whose explanation explicitly admits an evidence gap is
  conservatively blocked. Audit preserves the original provider status and reason.
- This applies to initial statements and revised text. The existing one-retry limit
  remains; no new agent, reasoning stage or broad refactor was added.
- Three regressions cover the admitted-gap contradiction, rewritten text and retry limit.

A separate live recheck used the original failing text and unchanged retrieved ABB
citations. It returned PARTIAL, removed the corrosion linkage, and reverified the
narrower statement as SUPPORTED in two calls. The original faulty run remains in
`data/evaluation/ui/step6/`; corrected runs are separate in `step6-fixed/`.

## Validation methods

Live browser automation used the real FastAPI backend, PostgreSQL corpus and configured
OpenAI `gpt-4.1-mini-2025-04-14` for reasoning and vision. It exercises rendered controls,
not just direct service functions. Paid calls are not mocked in these artifacts.

Failure coverage uses deterministic browser fault injection, plus existing backend
tests: timeout, 429, provider failure, backend disconnect, database/retrieval errors,
corrupt image rejection and missing confirmation. These tests demonstrate preserved
state and retry behavior; they are not claimed as observed live provider outages.
The database was not deliberately stopped during the demo audit.

Motor abstention is a clearly disclosed replay of the existing live motor fixture,
not a new motor-identification run. It returns LOW, no diagnosis and a temperature /
location / operating-condition question. Its relevance was weak, so later candidate
and verifier stages were not exercised in that historical case.

## Regression and replay results

The fresh post-fix browser rerun completed with no observed API/network failures:

| Check | Result |
| --- | --- |
| ACS880-01 / 5091 | MEDIUM; suspected STO signal interruption; physical page 525 citation opened. |
| Follow-up | Same session; MEDIUM; identity/analysis request count stayed 2 before/after (identify + confirm only). |
| Real reference photo | Completed; visible corrosion and discoloration, image-linked. |
| Photo → troubleshooting | Query included both visual descriptions and separate user note; retained exact 5091. Final rationale stayed with the documented STO fault, without the earlier corrosion causality. |
| Live vague-input case | LOW, no primary cause, measurement follow-up question. |
| Existing motor fixture | Recorded LOW abstention, explicit temporary reasoning fixture label; no catalog change. |
| Live reset | New session ID, no uploaded images, empty symptom and not_run result. |
| Errors/retry | All deterministic browser fault cases passed; no fake result substituted. |

Final live screenshots and session states are under `data/evaluation/ui/step6-fixed/`.
The standard backend on port 8000 was restarted to load the verifier fix; live
frontend remains on 5173 and explicit replay on 5174.

- Backend: **142 passed**, including all 139 previous tests; two existing dependency warnings.
- Frontend unit: **4 passed**.
- Browser: **14 passed**, up from seven; reset and failed-confidence regressions included.
- Production frontend build: passed.
- Replay audit: primary MEDIUM, exact 5091 excerpt, motor LOW, visible finding,
  reset and reload all passed. **Zero /api requests and zero external requests**.
- Secret scanner: same **11 review flags**, all reviewed documentation placeholders
  or test fixtures. No new real key findings; scanner rules were not weakened.

## Demo and submission artifacts

`DEMO.md` gives the 4–5 minute narration, exact launch/replay commands and fixture
disclosures. `DEMO-CHECKLIST.md` covers preflight and a 60-second fallback procedure.
README adds Why FieldTrace and links both documents.

Local screenshots cover intake, result, photo findings, exact source, LOW and reset.
Recorded screens are labeled. `data/evaluation/ui/step6/recorded-replay-backup.webm`
is a short automated replay walkthrough, not a narrated or fresh-inference video.
Generated media and raw audits remain ignored by Git; prepared replay retains provenance.

Files changed: frontend App.tsx/styles.css, browser tests, live-validation.mjs;
scripts/prepare_ui_replay.py and its public replay/provenance output; the existing
troubleshooting provider/pipeline and their regression tests; README. Added
frontend/replay-validation.mjs and the three Step 6 documents.

## Limits and rough edges

- Live verification is probabilistic. The new conservative contradiction check catches
  explicit admissions; it is not a proof system or a guarantee against all hallucinations.
- Backend calls are synchronous; there is no stage-by-stage progress API. UI text
  describes the work honestly rather than simulating stages. Use rehearsed replay if slow.
- The generic connector image checks data flow, not ABB model identity or actual ACS880
  condition. Do not present a resulting combined test diagnosis as a field validation.
- Real nameplate OCR on field photographs was not newly evaluated; this UI run uses
  typed confirmed model text. The motor remains outside the supported identity catalog.
- The source viewer shows exact extraction and a page link, not an embedded PDF renderer.
- Follow-up questions can still be generic. Local single-user scope and provider
  availability limits remain. External ABB links need a network connection, but saved
  replay excerpts do not.
- Do not claim the first live photo-context run was clean: its verifier gap is documented
  above, with separate original and corrected artifacts.

No new catalog entries, accounts, telemetry, replacement recommendations or other
out-of-scope product features were added. Nothing was committed or pushed.

**Readiness:** ready for a supervised, rehearsed hackathon demo with the labeled replay
fallback open. The original observed verifier error prevents any claim that this
prototype guarantees factual correctness; the specific issue was fixed and rechecked.
