# Scanned manual OCR and manual coverage

This change is based on the supplied `auth-session-history` snapshot. It preserves
Supabase authentication, session ownership, named history, draft saving, photo
management and the new equipment identity flow. It does not change the frontend.

## Optional local document OCR

Set this in the backend's private `.env` before running ingestion:

```dotenv
DOCUMENT_OCR_ENABLED=true
```

The default is `false`. Normal native-text pages retain the existing parser.
For pages with no extractable native text, the enabled parser renders bounded RGB
images (long edge at most 2400 pixels) and reuses the existing local RapidOCR
provider. No new provider key or dependency is required for this feature.

OCR output retains the physical PDF page number, extraction method, line source
boxes and an explicit transcription warning. Boxes use the same unrotated,
crop-local PDF-point coordinates as native extraction, including rotated pages.
Warnings are retained in stored pages and indexed/retrieved evidence; the existing
source dialog does not yet render extraction notes or page-box overlays.

If OCR fails, ingestion aborts transactionally; replacement failure preserves the
previously stored document. The development ingestion endpoint returns a clear
503 error identifying the physical page without exposing the provider exception.
Ordinary native parser failures still fall back to pypdf as before.

Use the existing scripts and configured development database:

```sh
python scripts/download_manuals.py
python scripts/ingest_manuals.py
```

Changing the OCR flag does not reprocess duplicate, already-indexed PDF hashes.
Reprocessing existing documents requires a deliberate rebuild with
`python scripts/ingest_manuals.py --rebuild` against the intended development
corpus. A rebuild must not be pointed at a shared demo database accidentally.

Scope: this handles pages without native text. A scanned body accompanied by a
native header/page number still follows native extraction and may need separate
preprocessing. OCR can misread identifiers, numbers and symbols; it is not diagram
interpretation or reliable scanned-table reconstruction. Check technical content
against the original page.

## Manual coverage before troubleshooting

For confirmed equipment, the snapshot uses the same model/family metadata filters
and document/page joins as retrieval to check whether indexed chunks actually
exist. A manifest entry or a nonzero cached document count is not enough.

If coverage is absent, the normal troubleshooting flow returns:

- `insufficient_evidence`, `LOW`, no suspected cause, actions or sources;
- a message explaining that no indexed manual matches the equipment;
- a follow-up asking for an applicable manual or confirmation of the model.

This returns before query embedding, retrieval or LLM inference. Existing frontend
message and follow-up components display the explanation. The presence of matching
chunks only means retrieval can proceed; it does not certify firmware/revision
applicability or the correctness of a diagnosis.

Explicitly injected service retrievers can target another corpus and receive
unspecified coverage during pipeline execution. The public API/default retriever
uses the database check. Persistent fingerprints still use the original database
snapshot. Adding/removing coverage invalidates an existing result until rerun.
A fingerprint from before this change can likewise become stale; history is kept.

Draft fields remain excluded from the diagnostic snapshot. Saving unsubmitted
text does not change its fingerprint or trigger analysis, and submitted input
updates preserve the draft. The existing authentication/ownership gates are intact.

## Validation

Fresh local validation on 2026-09-25:

| Check | Result |
|---|---|
| Backend `python -m pytest --integration -q` | 259 passed, 6 skipped, 7 dependency warnings |
| Frontend `npm run build` | Passed |
| Frontend `npm test` | 31 passed |
| Browser `npm run test:e2e` with local Chrome | 51 passed |
| Local RapidOCR, generated image-only PDF | Correctly extracted ACS880 and 5091; one other word had an OCR typo |
| `git diff --check` | Passed |

Database tests used a newly initialized disposable local PostgreSQL 17.7 with
pgvector 0.8.6. No existing/shared database was used. All six skips are the existing
`--corpus` tests needing the real ABB corpus and embedding model. Browser tests use
mocked authentication/API responses; live Supabase, model-provider accuracy and
cloud deployment were not validated. The runtime was built and used only under
local ignored work directories.

The regression suite includes real local SQL filter checks, an isolated PostgreSQL ingestion
rollback test, saved-draft and fingerprint tests, injected-retriever compatibility,
and unauthenticated route checks. OCR geometry/error tests use deterministic
fixtures. A separate local RapidOCR smoke uses one generated image-only page;
it is not a real-manual accuracy benchmark.

To repeat the backend checks against a disposable configured PostgreSQL/pgvector
instance, using the repository's locked dependencies:

```sh
python -m pytest -q
python -m pytest --integration -q
```

`--corpus` additionally requires the downloaded, indexed ABB manuals and the real
embedding model. It must not be treated as covered by mocked retrieval tests.
Frontend validation uses the unchanged build, unit and browser commands from the
repository. On macOS the existing browser config accepts `CHROME_PATH` pointing
to a local Chrome executable.
