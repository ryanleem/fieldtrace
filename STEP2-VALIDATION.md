# ABB Guardian — Step 2 validation

Validated locally on September 10, 2026. Step 2 is complete: nameplate OCR, catalog matching, mismatch warnings and explicit equipment confirmation. Step 3 was not started.

## Result and preservation of Step 1

- **29 tests passed**, including all 16 existing Step 1 tests and 13 new Step 2 tests. Two pre-existing dependency deprecation warnings remain.
- Real local OCR successfully read the synthetic test nameplate and ranked ACS880-01 first despite typed ACS580. Mock OCR reproduced the same workflow.
- Live HTTP multipart upload, confirmation persistence and a separate confirmed-filter search all succeeded on http://127.0.0.1:8001.
- Original corpus remains 2 manuals, 736 physical pages and 11,085 chunks. The catalog has three entries.
- Byte comparison with the delivered Step 1 ZIP confirms all original backend files except backend/app/main.py are unchanged. That file only adds the equipment router/schema initialization and updates the application title/version. Ingestion, embeddings, SQL search, RRF and original tests were not rewritten.

## Files changed and added

Changed:

- `backend/app/main.py`
- `README.md`
- `requirements.lock.txt`
- `requirements.txt`

Added:

- `backend/app/api/equipment.py`
- `backend/app/db/init_equipment.py`
- `backend/app/models/equipment.py`
- `backend/app/schemas/equipment.py`
- `backend/app/services/equipment_matching.py`
- `backend/app/services/equipment_ocr.py`
- `backend/app/services/equipment_parsing.py`
- `backend/app/services/equipment_sessions.py`
- `backend/tests/test_equipment.py`
- `data/equipment_catalog.json`
- `scripts/demo_equipment.py`
- `STEP2-VALIDATION.md` (this report)
- `data/processed/equipment-demo-real.json`, `equipment-demo-mock.json`, `equipment-live-api.json`, corresponding console logs, `pytest-step2-output.txt`, and `step2-preservation-audit.json`.

## Additive database schema

`equipment_catalog` stores id (string primary key), manufacturer, equipment_family, model_name (unique), model_number_pattern, product_type, aliases (JSONB), optional voltage/current/power ranges, official source_url, optional related_document_number, and explicit retrieval_model/retrieval_family mappings. Family is indexed.

`equipment_sessions` stores UUID id, entered_equipment_text, raw_ocr_text, parsed_ocr_fields (JSONB), per-image ocr_results (JSONB), raw/normalized typed input_identifiers, ranked_candidates, mismatch_warnings, selected_candidate and confirmed_equipment_id (catalog foreign keys), confirmation_status, identification_revision and timestamps.

Database checks limit status to UNCONFIRMED/SUGGESTED/CONFIRMED/REJECTED, require a confirmed ID exactly when status is CONFIRMED, and require selected/confirmed IDs to agree. A new identification clears prior confirmation. Explicit reject also clears filters. Row locks and revision checks prevent OCR from overwriting newer state. Clients should send identification_revision with confirmation to reject stale candidate screens (HTTP 409).

The initializer creates only these additive tables and idempotently seeds the catalog, refusing silent catalog drift. No ALTER, DROP or re-ingestion of the Step 1 corpus was needed. Catalog links use the document number rather than a deployment-specific document UUID.

## OCR approach

Local **rapidocr-onnxruntime 1.4.4**, with bundled text detection/recognition ONNX models and CPU ONNX Runtime. The exact installed environment is in requirements.lock.txt. No external AI API or Tesseract executable is required. Python 3.11–3.12 is supported by this pinned package; validation used 3.12.

The swappable OCRProvider.extract(image) interface returns raw_text, provider name, line text, recognition scores, bounding boxes and warnings. PIL validates actual image content, applies EXIF orientation, converts to RGB and bounds the longest edge to 2200 pixels. Limits: five images, 10 MiB each, 16 million pixels each; JPEG/PNG/WEBP still images only. OCR boxes use processed-image coordinates.

Deterministic parsing extracts only observed fields. Every image preserves raw OCR and raw model text separately from normalized identifiers. Missing or ambiguous aggregate fields are null. Multiple images with different model/voltage values retain their originals and emit warnings. Fault/display codes are only extracted as text, never interpreted diagnostically.

## Exact matching rules

Catalog label: **Prototype equipment catalog for demo/testing.** Entries: ACS880-01, ACS580-01, ACH580-01, verified by the linked official ABB product pages. All voltage/current/power ranges remain null rather than implying SKU-specific ratings. No motor example was added.

| Match signal | Base rule points |
|---|---:|
| Exact catalog model or full type-code prefix for that series | 100 |
| Explicit catalog alias | 95 |
| Exact family only; subtype unproven | 60 |
| Approximate identifier (maximum SequenceMatcher ratio to model/family >= 0.55) | round(ratio × 30) |

For non-fuzzy matches, typed text subtracts 10 points; general equipment-image OCR subtracts 25. A contextual O/0 repair or supporting OCR recognition score below 0.8 imposes a minimum 25-point penalty. Nameplate OCR otherwise uses the base score. Candidates take their maximum signal score, so repeated images cannot inflate the level. Ties use catalog ID. Return at most the closest three catalog candidates.

HIGH requires >=90 points; MEDIUM >=45; otherwise LOW. Conflicting OCR families/subtypes cap HIGH to MEDIUM. Strong nameplate evidence can remain HIGH when typed text differs, but that mismatch is shown and confirmation remains mandatory. These levels describe deterministic identification evidence, not diagnostic confidence or calibrated probabilities.

Normalization uppercases and removes identifier whitespace, normalizes Unicode dashes, and repairs O/0 only in recognized family numeric segments or subtype O1->01. Corrections are disclosed and raw text is retained. Unknown subtypes are never promoted to an exact catalog model. Prefix matching identifies a catalog series, not the validity or ratings of every possible full SKU.

No appearance classifier is present. Equipment-image OCR is secondary; a photo with no usable text and no typed identifier cannot establish identity. No-match returns UNCONFIRMED with a request for clearer input. Low approximate suggestions do not auto-confirm.

## Observed identification output (real local OCR)

**The image is a synthetic OCR fixture, not a real ABB nameplate and not a validated product specification.** It is generated by scripts/demo_equipment.py. No field photograph was supplied.

```json
{
  "session_id": "cd13b522-f32a-4c7c-ade0-df7412737718",
  "entered_equipment_text": "ACS580",
  "confirmation_status": "SUGGESTED",
  "confidence": "HIGH",
  "raw_ocr_text": "SYNTHETICOCRTEST-NOTANABBNAMEPLATE\nABB\nTYPE:ACS880-01-07A2-3\n400V\n7.2 A\n3kW\n50Hz\nSERIAL:DEMO123456",
  "parsed_ocr_fields": {
    "manufacturer": "ABB",
    "equipment_family": "ACS880",
    "model_number": "ACS880-01-07A2-3",
    "type_code": "ACS880-01-07A2-3",
    "serial_number": "DEMO123456",
    "voltage": "400V",
    "current": "7.2 A",
    "power": "3kW",
    "frequency": "50Hz",
    "fault_display_code": null
  },
  "confirmation_prompt": "Did you mean ABB ACS880-01? Confirm the catalog model before using equipment filters.",
  "top_candidate": {
    "candidate_id": "abb-acs880-01",
    "candidate_model": "ACS880-01",
    "match_level": "HIGH",
    "rule_score": 100,
    "explanation": "Catalog entry ACS880-01: nameplate[0] full type-code prefix (series match; full SKU not validated)"
  },
  "raw_and_normalized_identifier": {
    "raw": "ACS880-01-07A2-3",
    "normalized": "ACS880-01-07A2-3",
    "normalization_notes": []
  }
}
```

## Observed mismatch output

```json
{
  "mismatch_warnings": [
    "user_text contains ACS580 (normalized ACS580); differs from ACS880-01"
  ],
  "conflicting_signals": [
    "user_text contains ACS580 (normalized ACS580); differs from ACS880-01"
  ]
}
```

## Confirmation and restricted retrieval

```json
{
  "confirmation_status": "CONFIRMED",
  "confirmed_equipment_id": "abb-acs880-01",
  "confirmed_equipment_family": "ACS880",
  "confirmed_model": "ACS880-01",
  "retrieval_filters": {
    "equipment_model": "ACS880",
    "equipment_family": "ACS880 Drives"
  },
  "identification_revision": 2
}
```

After explicit confirmation, the demo makes a separate Step 1 /search call for `fault tracing` using those filters. Identification and confirmation never invoke troubleshooting or retrieval automatically.

| Rank | Source | Physical PDF page | Section | RRF |
|---:|---|---:|---|---:|
| 1 | [ACS880 Primary Control Program Firmware Manual](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf#page=529) | 529 | Fault tracing | 0.029571646 |
| 2 | [ACS880 Primary Control Program Firmware Manual](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf#page=536) | 536 | Fault tracing | 0.029198636 |
| 3 | [ACS880 Primary Control Program Firmware Manual](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf#page=535) | 535 | Fault tracing | 0.027972028 |
| 4 | [ACS880 Primary Control Program Firmware Manual](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf#page=536) | 536 | Fault tracing | 0.027650648 |
| 5 | [ACS880 Primary Control Program Firmware Manual](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf#page=536) | 536 | Fault tracing | 0.027402402 |

All results have equipment_model=ACS880 and equipment_family=ACS880 Drives. The integration test also confirms ACS580 and verifies that all retrieval branches return no evidence, rather than broadening into ACS880 documentation.

## Commands and tests

Run from the existing abb-guardian directory:

```powershell
$env:UV_CACHE_DIR=Join-Path (Get-Location) '..\work\uv-cache'
uv pip install --python '.venv\Scripts\python.exe' 'rapidocr-onnxruntime==1.4.4' 'python-multipart>=0.0.20,<1'
# Clean repeat: install the complete updated requirements.lock.txt instead.
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m app.db.init_equipment
$env:HF_HUB_OFFLINE='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts\demo_equipment.py --mock-ocr
.\.venv\Scripts\python.exe scripts\demo_equipment.py
.\.venv\Scripts\python.exe -m pytest --integration --corpus -q --basetemp work\pytest-step2-final --tb=short
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

The demo creates a session, submits typed ACS580 plus nameplate image, observes the OCR mismatch, confirms ACS880-01, reloads persisted state, and explicitly searches with confirmed filters. Mock mode uses dependency injection, not a production OCR-text bypass. The real and mock demos completed without failure. Demo sessions intentionally remain in the local database for inspection.

Tests cover exact/family/alias-context normalization, mismatches, no-match, top-three catalog-only candidates, raw/normalized preservation, weak OCR, secondary image evidence, invalid uploads, multipart API, unknown sessions, persistence, rejection, stale confirmation, new-input invalidation, multiple images, and real confirmed-equipment retrieval.

```text
.............................                                            [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\rleem\Documents\Codex\2026-09-10\https-www-hackerearth-com-community-challenges\abb-guardian\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  C:\Users\rleem\Documents\Codex\2026-09-10\https-www-hackerearth-com-community-challenges\abb-guardian\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
29 passed, 2 warnings in 5.20s
```

## Known limitations and scope

- OCR was exercised on a high-contrast synthetic image. Blur, glare, tiny text, oblique plates, rotation beyond orientation handling and field-camera conditions are not validated. Real nameplate recognition accuracy is not claimed.
- OCR may remove spaces (e.g. 400V instead of 400 V). Raw OCR is preserved exactly, including such differences. English field-label parsing, serial extraction, and multiple or unlabeled electrical ratings are heuristic.
- The three-model catalog is a prototype. It does not identify every ABB device, validate a complete SKU, establish electrical compatibility, or infer missing ratings.
- Fuzzy ranking can offer wrong alternatives; levels are not probabilities. Explicit human confirmation is required even for HIGH matches.
- Images are processed in memory; only OCR/provenance metadata is stored. Re-identification expects a fresh complete input snapshot and clears previous confirmation. There is no image archive or session-authentication frontend.
- As with Step 1, this is a synchronous loopback development API without authentication. No UI was added beyond FastAPI documentation.
- Existing Step 1 broad fault-tracing results and extraction limitations are unchanged. Confirmed filters restrict the source corpus; they do not establish that any fault applies to the equipment.
- No damage detection, diagnostic reasoning, claim verifier, diagnostic confidence calibration, document conflict detector, replacement engine or knowledge graph was added.

## Architecture changes and rationale

Step 2 lives in separate equipment_* service/model/schema modules, so it cannot replace the validated retrieval path. A small JSON seed supplies stable catalog IDs and explicitly maps confirmed model names to the existing corpus family/model fields. Persistent sessions and catalog foreign keys keep selected models bounded to actual demo entries. Confirmation exposes filters through confirmed_search_request(), reusing Step 1 SearchRequest and search_all unchanged. OCR is provider-injected so a future local/cloud engine can be substituted without changing matching or confirmation.

All eleven Step 2 acceptance criteria were verified. This delivery stops at Step 2.
