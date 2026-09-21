# Step 4: evidence-backed troubleshooting

Latest: [live post-claim verifier validation](STEP4-VERIFIER-LIVE-VALIDATION.md) demonstrates ACS880 5091 candidate generation, cited-only verification and five natural PARTIAL rewrites/rechecks. Two narrow contract/output fixes were regression-tested: **127 tests pass**. No natural UNSUPPORTED verdict or primary retry was observed.

The authorized [motor fixture live validation](STEP4-MOTOR-LIVE-VALIDATION.md) now records the initial and fan-running follow-up using real OpenAI review calls. Both returned LOW/insufficient evidence; it validates conservative stateful retrieval, not live motor diagnosis or claim verification.

Subsequent live validation: see [live results and bug fixes](STEP4-LIVE-VALIDATION.md).
That report preserves unsuccessful attempts, the remaining motor-catalog blocker,
and the newer 125-test regression result. It supersedes the earlier no-live-calls
limitation below for the ACS880 scenarios only.

Implemented as an additive layer around Steps 1–3. Existing OCR, equipment confirmation,
image providers, visual taxonomy, document ingestion, embeddings and search services remain
unchanged. No Step 5 functionality is included.

## Run and configure

Use the existing Python 3.12 virtual environment and PostgreSQL instance. FastAPI startup
initializes the new tables after the previous schemas. An explicit idempotent initialization:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m app.db.init_troubleshooting
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Text reasoning uses the OpenAI Responses API with strict JSON Schema, `store=false`,
and local Pydantic validation. Set `OPENAI_API_KEY` in the process environment or private
ignored `.env`. Never commit credentials. This is independent of the OpenAI/Gemini **vision**
selection: `VISION_PROVIDER=gemini` does not select a text troubleshooting provider.

| Variable | Default | Purpose |
|---|---|---|
| `TROUBLESHOOTING_MODEL` | `gpt-4.1-mini-2025-04-14` | Text review, comparison, generation and verification |
| `TROUBLESHOOTING_TIMEOUT_SECONDS` | `60` | Per-request timeout |
| `TROUBLESHOOTING_TOP_K` | `8` | Reviewed retrieval window, 2–12 |
| `TROUBLESHOOTING_MAX_LLM_CALLS` | `48` | Total per-run call budget, including one regeneration |

The injectable `TroubleshootingProvider.complete(stage, payload)` interface separates orchestration
from the OpenAI adapter. Automated tests and the deterministic demo require no API key.
API contract reference: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## Database and session state

Two new PostgreSQL tables use the existing SQLAlchemy `create(checkfirst=True)` approach,
under advisory initialization lock 41088004. No existing table is altered:

- `troubleshooting_sessions`: foreign-keyed to `equipment_sessions`; additive inputs JSONB,
  current result JSONB, input/equipment revisions, run token, start/update timestamps.
- `troubleshooting_runs`: immutable run records with snapshot fingerprint, revisions, status,
  full retrieved provenance, provider responses, candidate, verification verdicts and final answer.

Inputs include symptoms, technician notes, measurements, completed checks, ruled-out causes,
confirmed observations and follow-up answers. Updates append and deduplicate exact values;
they do not overwrite equipment, OCR or visual state. Maximum 30 items per request field,
60 accumulated entries per field. A measurement explicitly names its value, unit and location.
Corrections can be recorded as follow-up answers; semantic contradiction resolution between
old and new technician reports is left to contextual review, not automatic field replacement.

Current state exposes the requested `current_primary_cause`, `current_alternative_causes`,
`current_recommended_actions`, `current_next_question`, `current_confidence`, `current_conflicts`
and `retrieved_evidence_history`, plus a structured `result`. Only visuals belonging to the
current confirmed identity are included. Image notes retain `source=user_report`.

Database locks are released before retrieval/provider calls. A lease prevents duplicate
concurrent runs; a fingerprint rejects results if input, equipment, visual findings or image
notes change during a run. An abandoned lease expires after one hour. Equipment reidentification
invalidates the current answer; a new input update starts fresh troubleshooting inputs for that
identity, preserving previous run history. A run failure stores LOW/no diagnosis and sanitized
error status rather than presenting an old answer as a new result.

## API

Create/confirm equipment using the existing `/sessions` and equipment routes first.
All routes below are relative to `/sessions/{session_id}/troubleshooting`:

| Method | Route | Behavior |
|---|---|---|
| PUT | empty | Start/update additive troubleshooting inputs |
| GET | empty | Current inputs, answer and history metadata |
| POST | `/symptoms` | Append `{"symptom":"Motor overheating"}` |
| POST | `/run` | Run retrieval through verified response |
| POST | `/follow-up` | Append answer/measurements, then rerun from retrieval |
| GET | `/runs/{run_id}` | Historical final result |
| GET | `/runs/{run_id}?include_evidence=true` | Explicit debug audit with retrieved text and unverified candidates |

Example PUT or follow-up body:

```json
{
  "reported_symptoms": ["Motor overheating"],
  "answer": "The fan is spinning",
  "measurements": [{"name":"temperature","value":"92","unit":"C","location":"housing"}],
  "checks_completed": ["Observed fan spinning"],
  "expected_revision": 1
}
```

Omit `expected_revision` on first creation, or supply the revision from GET for optimistic
concurrency. Missing session/run gives 404, invalid input 422, stale input/in-flight run 409.
Provider/retrieval failure returns a stored `result.status=failed`, LOW confidence and no
diagnosis/actions. Callers must inspect status. Follow-ups never call OCR, matching or vision.

## Pipeline

1. Snapshot confirmed equipment, existing visual findings, OCR text and technician inputs.
2. Construct full contextual semantic query and separate exact keyword terms (model/fault codes,
   colon-delimited terminals, signed numbers, measurements, uppercase and quoted identifiers).
   Reuse Step 1 normalization to remove redundant filtered family/manufacturer words from the
   executed semantic query. Preserve originals in the snapshot/query audit.
3. Reuse Step 1 semantic search, keyword search and RRF with confirmed-equipment filters.
   Run separate FTS queries for disjoint exact terms, avoiding a requirement that every code and
   measurement co-occur in one chunk. Bound keyword requests to nine and record unsearched terms.
   Bound embedding input to its tokenizer budget and explicitly record omitted context.
4. LLM reviews every chunk for relevance and applicability. Incomplete reviews are failures.
   WEAK/no relevant evidence returns an information request without candidate generation.
5. For each same-issue group, compare its top 2–3 RRF-ranked chunks. Preserve CONSISTENT,
   COMPLEMENTARY, CONFLICTING or DIFFERENT_APPLICABILITY results and cited sources.
6. Generate a structured candidate: suspected primary cause, alternatives, claims, actions,
   follow-up and missing information. Model context and visual findings are not manual proof.
7. Verify each technical claim against **only its explicitly cited retrieved chunks**. Unknown
   or absent IDs are rejected before a model call. Verify cause labels and rationales separately
   against their referenced claims' sources, and verify actions/questions/missing-info wording.
8. Build the technician answer with citation metadata, confidence and concise rationale. No raw
   chunks or unverified candidate text appear in the default response.

SUPPORTED statements survive. PARTIAL statements are narrowed and the rewrite is verified again;
an unsupported rewrite is removed. Unsupported nonessential statements/actions are removed.
If a primary supporting claim, label or rationale fails, refine retrieval using that hypothesis
and regenerate **once**. Never promote an alternative automatically. A second failure returns
insufficient evidence, LOW and a question. The audit retains both attempts and verdicts.

Actions are withheld for unconfirmed equipment or unresolved conflicts. Conflict responses show
the relationship and source citations, ask for model/revision/conditions, and do not silently choose
an instruction. Free-form conflict explanations remain in the debug audit because they are not
themselves claim-verified. Completed checks and ruled-out causes are provided to generation;
exact repeated actions/causes are additionally suppressed deterministically.

## Ordinal confidence policy

- Unsupported primary or weak/no usable evidence: LOW; no diagnosis.
- A supported answer is HIGH only if its primary citations are all RELEVANT, at least one primary
  citation was found by both search channels, equipment is confirmed, no unresolved conflict,
  no low-confidence visual finding, no missing information and no weakened statement.
- All other supported answers: MEDIUM. In particular, unconfirmed equipment, conflicting or
  differently applicable sources, partial relevance, missing information, or a weakened claim
  cannot yield HIGH.

These rules are deterministic policy labels, **not** calibrated probabilities or proof of a fault.

## Deterministic demo and validation

```powershell
.\.venv\Scripts\python.exe scripts/demo_troubleshooting.py
.\.venv\Scripts\python.exe -m pytest --integration --corpus --basetemp work/pytest-step4-final -q
```

The demo uses actual hybrid retrieval from the existing ABB motor corpus, plus explicitly
simulated equipment-family confirmation, open-air cooling design, dust finding and symptom.
It creates an isolated temporary session schema, stores the simulated visual evidence and
troubleshooting inputs, executes the production orchestration, then removes that temporary schema.
It does not add a motor to the real Step 2 catalog or fabricate a manual passage.

LLM replies are deterministic scenario fixtures. Verifier fixtures only accept the specific
demo statements if their supporting text actually appears in the cited retrieved chunks;
this tests wiring/provenance and is not a live LLM accuracy evaluation.

Saved artifact: [full demo JSON](data/evaluation/step4-demo.json), containing query, actual retrieved
evidence, reviews, conflict, candidate, per-statement verification, confidence and final response.
The final demo uses the default top-K=8. It finds complementary passages in *Manual for Induction
Motors and Generators*, revision L, physical p.89, sections 7.8 and 7.8.1. Its suspected cause is
possible reduced cooling efficiency from dirt in an open-air-cooled machine, confidence MEDIUM.
It asks for an already measured temperature and conditions. No maintenance actions or alternative
causes are invented when the bounded scenario lacks support for them.

Final validation on 2026-09-19: **122 tests passed** (all 85 existing tests plus 37 Step 4
tests), with PostgreSQL integration and real-corpus tests enabled and no skips. Two existing
Starlette/httpx/AnyIO deprecation warnings remain. The explicit additive initializer and
default-eight-chunk deterministic demo also completed successfully.

## Remaining limitations

- The text-only production adapter is wire-tested with mocked HTTP responses; no live diagnostic
  LLM accuracy claim is made. The prior seven-photo evaluation validates Step 3 only.
- Same-model LLM review and verification can share mistakes; citations and successful verification
  do not establish a real equipment fault or make maintenance instructions safe to execute.
- Retrieval is wording-sensitive. Broad motor/dust/area wording initially retrieved irrelevant
  passages; a more specific visible description retrieved the cooling passage. This single demo
  does not establish broad troubleshooting recall. Corpus layout/table extraction also limits evidence.
- The catalog remains three drive families. Motor confirmation/design in the demo is a declared
  isolated fixture, not live OCR/model identification. Model/frame-specific applicability needs
  real confirmation and project documentation.
- Calls run synchronously with a bounded call count; latency/cost can be substantial. There is no
  background job queue, authentication, audit retention policy or production operational hardening.
- User observations and ruled-out causes remain technician reports; semantic duplicate/correction
  handling is model-assisted. No autonomous maintenance actions or Step 5 functionality is present.

## Changed files

Added:

```text
backend/app/api/troubleshooting.py
backend/app/db/init_troubleshooting.py
backend/app/models/troubleshooting.py
backend/app/schemas/troubleshooting.py
backend/app/services/troubleshooting_pipeline.py
backend/app/services/troubleshooting_provider.py
backend/app/services/troubleshooting_query.py
backend/app/services/troubleshooting_sessions.py
backend/tests/test_troubleshooting.py
scripts/demo_troubleshooting.py
data/evaluation/step4-demo.json
STEP4.md
```

Modified `backend/app/config.py`, `backend/app/main.py`, `.env.example`, and `README.md`.
No existing Step 1–3 service implementation was edited.
