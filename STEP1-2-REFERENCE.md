# Historical Step 1–2 technical reference

This is the previous README, retained for its detailed extraction, matching and API
notes. Use [README.md](README.md) for current team setup; the native-database commands,
local defaults and port-8001 examples below describe an older validation environment.

Step 5 adds the React technician workspace, exact citation viewer and clearly labeled
recorded fallback. See [Step 5 setup and validation](STEP5.md) for local run commands,
workflow, tests and prototype limits. The existing Step 1–4 reasoning services and
supported equipment catalog are preserved.

Real ABB PDF ingestion and evidence-only hybrid retrieval. Python, FastAPI,
PostgreSQL, pgvector, PostgreSQL full-text search, and local sentence-transformers.
Step 2 adds local nameplate OCR, deterministic prototype-catalog matching, and explicit
equipment confirmation. Step 3 adds multi-angle image intake, structured visible
observations, session aggregation and visual retrieval context. Step 4 adds persistent
troubleshooting inputs, evidence review, conflict checks, cited candidate generation,
claim verification, ordinal confidence and text follow-ups. See [Step 4 guide](STEP4.md)
for setup, endpoints, a deterministic real-corpus demo and validation limitations.

**Step 3 validation status:** the subsequent OpenAI run processed all seven photos;
five of six main abnormalities were recognized, with no obvious false positives or
hidden-failure claims. See the current [provider validation report](STEP3-PROVIDER-VALIDATION.md).
The earlier [validation report](STEP3-VALIDATION.md) records the historical quota blocker.
See also the [Step 3 guide](STEP3.md). Earlier Step 1/2 sections below describe
those stages; their OCR and retrieval behavior is preserved.

## Step 2: equipment identification and confirmation

Existing Step 1 ingestion, embeddings, SQL retrieval and RRF services are unchanged.
Two additive PostgreSQL tables hold the prototype catalog and equipment sessions.
The catalog is explicitly **"Prototype equipment catalog for demo/testing."** It
contains ACS880-01, ACS580-01 and ACH580-01, with official ABB product links. Ranges
remain null: no SKU-specific electrical ratings are inferred from a series match.
No motor entries were added because they are outside this initial three-drive demo.

Use Python 3.11 or 3.12 (validated with 3.12); the pinned OCR package does not support
Python 3.13. Install the updated lock file, then initialize the additive schema:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m app.db.init_equipment
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

The existing PostgreSQL instance and corpus are reused; no re-ingestion is required.
Application startup also initializes these tables idempotently. The schema initializer
refuses catalog drift instead of silently changing a previously confirmed identity.
The earlier port-8000 process may still serve Step 1; this Step 2 demo uses port 8001.

### OCR and input provenance

RapidOCR 1.4.4 uses its bundled detection/recognition ONNX models through local CPU
ONNX Runtime. No external AI API is called and no Tesseract installation is required.
`OCRProvider.extract()` is the swappable provider boundary. Tests inject an explicitly
labeled mock provider; the production API has no raw-OCR-text override parameter.

Accept JPEG, PNG or WEBP, up to five still images, 10 MiB per image, and 16 million
pixels per image. Image validation uses actual decoded content. Pillow applies EXIF
orientation, converts to RGB and bounds the longest side to 2200 pixels. OCR boxes
refer to this processed image size. The service stores image hashes, raw recognized
text, recognition scores, boxes and parsed fields; it does not persist uploaded images.

Each image retains its own raw text, raw field values and normalized identifiers.
Manufacturer, family, model, type code, labeled serial, voltage/current/power/frequency,
and labeled fault/display code are parsed only from detected text. Ambiguous aggregate
fields remain null. A parsed type code is an observation, not proof that the complete
SKU exists. Unit values are preserved as recognized, without engineering conversion.

Model normalization uppercases, removes identifier whitespace and normalizes Unicode
dashes. O/0 repair is limited to known family numeric segments and subtype O1 -> 01;
the raw value and correction notes remain separate. Serial numbers are not corrected.
Appearance alone supplies no authoritative signal. General equipment images can
contribute OCR text as a secondary signal; no visual classifier is implemented.

### Matching rules

All returned IDs come from the three-row catalog. Rule scores are ranking points,
not confidence percentages or diagnostic confidence:

| Signal | Base points |
|---|---:|
| Exact model or complete type-code prefix matching a catalog series | 100 |
| Explicit catalog alias | 95 |
| Exact family only (subtype not established) | 60 |
| Approximate identifier with SequenceMatcher ratio >= 0.55 | round(ratio × 30) |

For non-fuzzy signals, user text subtracts 10; OCR on a general equipment image
subtracts 25. Contextual O/0 corrections or a supporting OCR line score below 0.8
apply a minimum penalty of 25. Nameplate OCR otherwise receives the base score.
The candidate score is the maximum supporting score, not a sum; repeating images
does not inflate the level. HIGH >= 90, MEDIUM >= 45, otherwise LOW. Different OCR
families/subtypes cap HIGH to MEDIUM and emit mismatch warnings. A typed/OCR mismatch
is exposed explicitly; a strong nameplate match can remain HIGH, always requiring
user confirmation. Exact family evidence never proves a subtype.

Candidates sort by descending points and catalog ID for ties, returning at most
three. Uncertain identifiers can return three LOW candidates with UNCONFIRMED status;
unrecognizable text returns no candidates. No absent catalog model is fabricated.

### Endpoints and state

- `POST /sessions`: create persisted UNCONFIRMED state.
- `POST /sessions/{id}/equipment/identify`: multipart form with optional
  `entered_equipment_text`, repeated `images`, and optional `image_roles` JSON array
  parallel to those images (`nameplate` or `equipment`; default `nameplate`).
- `POST /sessions/{id}/equipment/confirm`: JSON `equipment_id` and optional
  `identification_revision`. Supplying the returned revision protects against stale
  confirmations (HTTP 409). Confirmation must select a current returned candidate.
- `POST /sessions/{id}/equipment/reject`: reject suggestions and clear confirmed filters.
- `GET /sessions/{id}/equipment`: reload persistent identification/confirmation state.

An identification call replaces the current input snapshot and clears prior confirmation;
send all currently relevant images/text when retrying. No-match returns UNCONFIRMED
and requests a clearer nameplate or model number. Reliable matches return SUGGESTED,
never auto-confirmed. Explicit confirmation sets CONFIRMED; rejection sets REJECTED.
Row locks and revision checks prevent in-flight OCR from overwriting newer state.

```powershell
$session = Invoke-RestMethod -Method Post http://127.0.0.1:8001/sessions
$sessionId = $session.session_id
curl.exe -X POST "http://127.0.0.1:8001/sessions/$sessionId/equipment/identify" -F "entered_equipment_text=ACS580" -F "images=@nameplate.jpg" -F 'image_roles=["nameplate"]'
# Review candidates and mismatch warnings, then submit the selected catalog ID:
$body = @{equipment_id='abb-acs880-01'; identification_revision=1} | ConvertTo-Json
Invoke-RestMethod -Method Post "http://127.0.0.1:8001/sessions/$sessionId/equipment/confirm" -ContentType application/json -Body $body
Invoke-RestMethod "http://127.0.0.1:8001/sessions/$sessionId/equipment"
```

Confirmed ACS880-01 exposes `confirmed_model=ACS880-01`, family `ACS880`, and
`retrieval_filters={equipment_model: ACS880, equipment_family: ACS880 Drives}`.
This explicit mapping respects the existing family-level corpus metadata. The helper
`confirmed_search_request()` constructs an ordinary Step 1 SearchRequest and refuses
unconfirmed states. Identification and confirmation do not automatically search or
troubleshoot. A separately requested search uses the returned filters. ACS580/ACH580
currently have no matching ingested manuals and return no evidence, without broadening
to ACS880 documents.

### Step 2 validation and reproducible demo

```powershell
$env:HF_HUB_OFFLINE='1' # after Step 1 model is cached
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m pytest --integration --corpus -q --basetemp work/pytest-step2
.\.venv\Scripts\python.exe scripts/demo_equipment.py --mock-ocr
.\.venv\Scripts\python.exe scripts/demo_equipment.py
```

The demo creates a clearly labeled **synthetic OCR test image, not a real ABB
nameplate**. It submits typed ACS580 plus ACS880-01-07A2-3 nameplate text, records the
mismatch, confirms ACS880-01, reloads the session and explicitly searches for fault
tracing with the confirmed filters. Default mode uses actual local OCR; `--mock-ocr`
uses deterministic fixture text. Both save complete JSON under `data/processed/`.
Demo sessions persist for inspection. Unit tests require no external AI service.

Known limits: glare, rotation, blur, tiny characters, multilingual labels and stacked
or unlabeled electrical ratings may produce missing/wrong OCR. The parser supports
a narrow catalog and English field labels. Recognition scores and rule levels are not
calibrated probabilities; confirmation remains mandatory. No real technician photo
was supplied, so real OCR was validated on synthetic text, not on field photography.
See `STEP2-VALIDATION.md` for the observed outputs and tests.

## Step 1 setup (PowerShell, Python 3.11–3.12)

Run from the `abb-guardian` directory. These are development-only, loopback database
credentials, not deployment credentials.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
docker compose up -d --wait
.\.venv\Scripts\python.exe scripts/download_manuals.py
.\.venv\Scripts\python.exe scripts/ingest_manuals.py
.\.venv\Scripts\python.exe scripts/test_search.py
.\.venv\Scripts\python.exe -m pytest --integration --corpus -q --basetemp work/pytest-validation
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

`uv venv .venv --python 3.12` and
`uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt` are
equivalent environment setup commands. On Linux/macOS, replace the interpreter path
with `.venv/bin/python`. `requirements.txt` records the supported direct dependencies;
`requirements.lock.txt` records the exact packages used in this validation.

Docker Compose runs only PostgreSQL, with a persistent volume and health check.
`docker compose stop` stops it without deleting the corpus. Do not run both database
startup methods on port 55432 at the same time.

### Windows fallback used in this workspace

Docker Desktop did not expose a working engine. The optional fallback installs a
portable PostgreSQL distribution beneath `work/`, without a Windows service:

```powershell
.\.venv\Scripts\python.exe scripts/setup_native_postgres.py
```

This uses EDB PostgreSQL 17.11 and the community-maintained
`andreiramani/pgvector_pgsql_windows` pgvector 0.8.6 build for PostgreSQL 17.
The pgvector ZIP is checked against its GitHub release SHA-256. The EDB download is
over verified TLS; its observed SHA-256 is recorded, but no publisher-signed hash was
available in this workflow. URLs and hashes are saved in
`work/native-postgres/downloads.json`. Docker remains the preferred portable setup.

If `pg_ctl` cannot create a nested restricted Windows token, the fallback starts the
standard `postgres.exe` directly under the same user and sandbox. In this session
the working startup command was:

```powershell
& .\work\native-postgres\pgsql\bin\postgres.exe -D .\work\native-postgres\data -p 55432 -h 127.0.0.1
```

Normal stop/restart commands:

```powershell
& .\work\native-postgres\pgsql\bin\pg_ctl.exe -D .\work\native-postgres\data -m fast -w stop
.\.venv\Scripts\python.exe scripts/setup_native_postgres.py
```

## Corpus and provenance

The official downloads are listed in `data/manuals/manifest.json`:

| PDF | Physical pages | Confirmed document number | Revision | Verification page |
|---|---:|---|---|---:|
| ACS880 primary control program firmware manual | 604 | 3AUA0000085967 | V | 3 |
| Manual for induction motors and generators | 132 | 3BFP 000 050 R0101 | L | 132 |

Cover titles, publisher, and publication identifiers were checked against the real
PDFs, with representative pages rendered for visual review. The motor manual's
`equipment_model` is null because it covers multiple models. Equipment-family and
document-type values are catalog categories supported by the cover and contents,
not claimed verbatim bibliographic fields. Download hashes prevent changed files
from silently inheriting old verified metadata.

`python scripts/inspect_corpus.py` repeats the source-text checks and writes raw
page/structure JSON plus selected page renders under `work/pdf-inspection/`.
It is specialized to the two initial PDFs. New documents need their own metadata
verification; unconfirmed bibliographic values must remain null.

Every extracted page is stored in `document_pages`, even if it produces no chunks.
Every chunk references a real `(document_id, page_number)` row through a composite
foreign key. `page_number` is **1-based physical PDF position**, suitable for
`#page=N` links. `printed_page_label` is the optional PDF page-label field and is
never substituted for physical position. Document hashes and UUIDs identify source
files; each document has globally sequential zero-based `chunk_index` values.

## Extraction and chunking

PyMuPDF extracts each page separately. PDF bookmarks and detectable numbered
headings provide section context; bordered tables become row units with explicit
column separators. Raw text is always kept for inspection. Structured failures
fall back to page text; pypdf is a secondary parser if a page fails in PyMuPDF.

Chunks follow headings and paragraph boundaries, keep short procedures and safety
notes together when feasible, and never cross a physical page. Oversized blocks
split at sentence/line boundaries, then words as a size guard. Rare malformed single
tokens have a last-resort character split. Fault/table fragments retain row identifiers
and column headers when they fit. A source block ID and bounding box link fragments.
Nearby warning text is repeated in `safety_context` metadata when a size split is
needed. Headings attach to body evidence instead of becoming standalone hits.

Token budgets are derived from the selected model's context length. Inputs are
checked again before embedding; oversized inputs cause an error rather than silent
truncation. Embedding dimensions come from the model, and batches are normalized.
The default model is pinned to the revision in `.env.example`. Its observed dimension
is 384; the implementation does not assume that dimension.

The `corpus_config` table records model identity, requested revision, dimension, and
pipeline version. A mismatch fails explicitly. To change model/configuration, create
a separate database and reingest; vectors from different embedding spaces must not
be combined. For a configurable model with a moving revision, pin `EMBEDDING_REVISION`
before reproducible ingestion. Models requiring query/document prompts should use a
sentence-transformers version exposing those methods or configured model prompts.

## Search behavior

Semantic retrieval uses pgvector cosine distance. At this corpus size, it deliberately
uses exact SQL-filtered ranking for reliable filter recall; an HNSW cosine index exists
for later scale. The exact path disables index scans locally to avoid approximate
post-filter underfilling. This is still pgvector retrieval, not a Python vector scan.

Keyword retrieval uses generated `tsvector`, a GIN index, `websearch_to_tsquery`,
`plainto_tsquery`, and `ts_rank_cd`. English stemming handles prose while the `simple`
configuration preserves fault codes and technical lexemes. Technical identifiers
are required in identifier-bearing keyword queries. Prose uses OR lexemes to avoid
an all-words requirement for conversational questions.

A deterministic cleanup removes conversational filler and redundant ABB/model/family text
already conveyed by filters. It retains symptoms, negation and technical identifiers;
it adds no diagnoses, synonyms or generated content. The inspection script prints
the resulting retrieval query beside the original question.

The two rankings run independently and are fused only by standard RRF:
`sum(1 / (RRF_K + rank))`, using one-based ranks. Raw cosine and keyword scores are
never added together. UUID tie-breaking makes ties deterministic within a corpus.
`SEMANTIC_TOP_N`, `KEYWORD_TOP_N`, `RRF_K`, and `HYBRID_TOP_K` are configurable.
Model, family and document filters are applied in both SQL candidate queries.

## API

Open `http://127.0.0.1:8000/docs` for the API schema. This is a local development API
without authentication; keep the default loopback binding.

`POST /documents/ingest` accepts a manifest entry or the equivalent request body.
It reads only PDFs within the configured `data/manuals` directory. It does not fetch
arbitrary request URLs. Ingestion is one transaction per PDF, with a unique file hash
and transaction-scoped advisory lock for concurrency-safe idempotency. A failed
embedding batch rolls back the whole document. Repeating an ingest returns the
existing document ID with `duplicate: true`.

```json
{
  "filename": "acs880_primary_control_program_firmware_manual.pdf",
  "title": "ACS880 Primary Control Program Firmware Manual",
  "manufacturer": "ABB",
  "equipment_family": "ACS880 Drives",
  "equipment_model": "ACS880",
  "document_type": "firmware_manual",
  "document_number": "3AUA0000085967",
  "revision": "V"
}
```

Use the complete manifest entry to include the official source URL and verified hash.
The response includes document ID, pages processed, chunks created, warnings, errors,
and duplicate status. Validation failures return structured HTTP 422 errors; missing
PDFs return HTTP 404. Unexpected database/server failures remain HTTP 500 failures.

`POST /search`:

```json
{
  "query": "An ABB motor is overheating. What should I inspect?",
  "equipment_family": "Induction Motors and Generators",
  "top_k": 5
}
```

Returns the original query and ranked evidence with document/chunk IDs, title,
physical page, optional label, section, content type, chunk text, source URL and
page link, source bounding boxes, safety context, and semantic/keyword/RRF ranks and
scores. These are retrieval scores, **not calibrated confidence or diagnoses**.

## Validation and inspection

```powershell
# Unit tests only; database/model tests are explicitly skipped.
.\.venv\Scripts\python.exe -m pytest -q
# Database tests create and remove isolated test schemas, not production tables.
.\.venv\Scripts\python.exe -m pytest --integration --corpus -q --basetemp work/pytest-validation
# All six required queries; semantic, keyword and hybrid top five, including weak hits.
.\.venv\Scripts\python.exe scripts/test_search.py
# Repeat ingestion to demonstrate duplicate suppression.
.\.venv\Scripts\python.exe scripts/ingest_manuals.py
# Explicit atomic rebuild after extraction changes, preserving old data on failure.
.\.venv\Scripts\python.exe scripts/ingest_manuals.py --rebuild
```

The harness includes warning A4F6, observed in the real ACS880 PDF on physical page
503. Results and extraction warnings are saved in `data/processed/`.
For offline runs after the first model download, set `$env:HF_HUB_OFFLINE='1'`.
Local model inference never calls an external embedding or LLM API.

See `VALIDATION.md` for the actual environment, test output, final ingestion counts,
top-five evidence, and known weak results.

## Limitations

Step 3 provider selection, image intake and live-review results are documented in
[STEP3.md](STEP3.md) and [STEP3-PROVIDER-VALIDATION.md](STEP3-PROVIDER-VALIDATION.md).
OpenAI and Gemini share the same visible-observation contract; neither performs diagnosis.

- No PDF OCR in document ingestion: image-only/blank PDF pages are recorded with warnings and no fabricated text. Nameplate image OCR is provided separately by Step 2.
- Diagrams/images are not interpreted. Captions and nearby text can be indexed;
  image-presence warnings include recurring logos, not just technical figures.
- Tables are structural heuristics. Empty/merged cells are not guessed; rotated,
  borderless, or complicated tables can remain page-aware text. Verify the source
  page before treating a flattened row as a complete technical instruction.
- Section detection is heuristic; page-spanning subsections can fall back to chapter
  context. Warnings are linked locally, not exhaustively across pages/documents.
- English keyword stemming and a small general embedding model leave some false
  positives, especially short identifiers. RRF does not prove evidentiary support.
- This is synchronous local ingestion suitable for two manuals. Background jobs,
  authentication, database migrations and large-corpus ANN tuning are future work.
