# ABB Guardian — Step 1 validation

Validated locally on September 10, 2026. Step 1 is working; Step 2 was not started.

The delivered source implements real PDF ingestion, local embeddings, PostgreSQL/pgvector semantic search, PostgreSQL full-text search, standard RRF, and evidence-only API responses.

## Verified results

- PostgreSQL 17.11 and pgvector 0.8.6 running locally on 127.0.0.1:55432.
- Model: sentence-transformers/all-MiniLM-L6-v2, revision c9745ed1d9f207416be6d2e6f8de32d1f16199bf; observed dimension 384, context 256 tokens.
- 2 documents, 736 physical page records, 11,085 chunks; 0 missing document/page/chunk-index provenance values.
- Both manuals ingested without fatal errors. A second ingest returned duplicate=true for both with unchanged counts.
- 16 tests passed, including real PostgreSQL, real-corpus relevance, path restrictions, rollback, filters, model mismatch, and FastAPI endpoint tests.
- Live HTTP GET /health and POST /search both returned 200; the search returned five evidence objects.
- HNSW cosine and GIN full-text indexes exist; exact pgvector ranking is used for reliable SQL-filtered retrieval at this corpus size.
- No external embedding/LLM API was used. No diagnostic answer generation exists.

## Ingestion statistics

| Manual | Physical pages | Chunks | Pages with extraction notes | Second ingest |
|---|---:|---:|---:|---|
| acs880_primary_control_program_firmware_manual.pdf | 604 | 9811 | 521 | duplicate=true |
| abb_induction_motors_generators_manual.pdf | 132 | 1274 | 132 | duplicate=true |

A note is not a fatal error. Image-presence notes include repeated logos; table notes flag unverified cell relationships.

## Metadata verification

- **ACS880 Primary Control Program Firmware Manual**: 3AUA0000085967, revision V. Checked against physical PDF pages [1, 3]. [Official ABB source](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf).
  - SHA-256: `1c1a7004895164c00bc11eed738b728a4da1ec2d1de4b6fd575c633a59d60cbf`
- **Manual for Induction Motors and Generators**: 3BFP 000 050 R0101, revision L. Checked against physical PDF pages [1, 132]. [Official ABB source](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf).
  - SHA-256: `c6e4141f5c1cac79c0af1dad649dcfc6b6903756055c6fac2ece6c07b62ed542`

The motor manual's equipment_model remains null because it covers multiple models. Both manuals' bibliographic document numbers and revisions were verified, so none of those fields remains null. Optional section/page-label fields may be null when not detected; they are never invented.

## Final hybrid top five

The following are retrieved source excerpts, not generated troubleshooting instructions. Scores are ranks/similarity values, not confidence. Full text, IDs, bounding boxes, safety context and source links are in data/processed/retrieval-results.json.

### An ABB motor is overheating. What should I inspect?

SQL filters: equipment_family='Induction Motors and Generators', equipment_model=None. Normalized retrieval query: `overheating inspect`.

| Rank | Physical PDF page | Section | Semantic rank | Keyword rank | RRF |
|---:|---:|---|---:|---:|---:|
| 1 | 64 | 6.4 Supervision | 12 | 1 | 0.030282332 |
| 2 | 89 | 7.8.1 Maintenance instructions for machines with open air cooling | 1 | — | 0.016393443 |
| 3 | 107 | 8.5 Thermal performance and cooling system | 2 | — | 0.016129032 |
| 4 | 90 | 7.8.1.1 Cleaning of filters | — | 2 | 0.016129032 |
| 5 | 91 | 7. Maintenance | 3 | — | 0.015873016 |

1. [Manual for Induction Motors and Generators, physical PDF p. 64](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=64): “6.4 Supervision The operating personnel should inspect the machine at regular intervals. This means that they should listen, feel and smell the machine and its …”
2. [Manual for Induction Motors and Generators, physical PDF p. 89](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=89): “If the winding or cooling air temperature detectors show an abnormal temperature, a check of the cooling system has to be made. The two maintenance issues are t…”
3. [Manual for Induction Motors and Generators, physical PDF p. 107](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=107): “NOTE: An excessive heat production might be caused by a winding problem or by network unbalance, and in these cases corrective actions on the cooling system wou…”
4. [Manual for Induction Motors and Generators, physical PDF p. 90](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=90): “7.8.1.1 Cleaning of filters The filters should be cleaned regularly. The cleaning interval depends on the cleanliness of the air in the surrounding environment.…”
5. [Manual for Induction Motors and Generators, physical PDF p. 91](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=91): “The machine can be equipped with temperature detector(s) for monitoring the internal cooling air. If the temperature detectors show normal temperature, no addit…”

### ACS880 fault tracing

SQL filters: equipment_family=None, equipment_model='ACS880'. Normalized retrieval query: `fault tracing`.

| Rank | Physical PDF page | Section | Semantic rank | Keyword rank | RRF |
|---:|---:|---|---:|---:|---:|
| 1 | 529 | Fault tracing | 3 | 13 | 0.029571646 |
| 2 | 536 | Fault tracing | 8 | 9 | 0.029198636 |
| 3 | 535 | Fault tracing | 6 | 18 | 0.027972028 |
| 4 | 536 | Fault tracing | 9 | 16 | 0.027650648 |
| 5 | 536 | Fault tracing | 12 | 14 | 0.027402402 |

1. [ACS880 Primary Control Program Firmware Manual, physical PDF p. 529](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf#page=529): “Table columns: Code (hex) | Fault | Cause | What to do 64FF | Fault reset | Informative fault. | An active fault has been reset.…”
2. [ACS880 Primary Control Program Firmware Manual, physical PDF p. 536](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf#page=536): “Table columns: Code (hex) | Fault | Cause | What to do 9085 | External fault 5 (Editable message text) Programmable fault: 31.09 External event 5 source 31.10 E…”
3. [ACS880 Primary Control Program Firmware Manual, physical PDF p. 535](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf#page=535): “Table columns: Code (hex) | Fault | Cause | What to do 9081 | External fault 1 (Editable message text) Programmable fault: 31.01 External event 1 source 31.02 E…”
4. [ACS880 Primary Control Program Firmware Manual, physical PDF p. 536](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf#page=536): “Table columns: Code (hex) | Fault | Cause | What to do 9083 | External fault 3 (Editable message text) Programmable fault: 31.05 External event 3 source 31.06 E…”
5. [ACS880 Primary Control Program Firmware Manual, physical PDF p. 536](https://library.e.abb.com/public/b24019aa640f45bf83a14f04f53691fe/EN_ACS880_Primary_FW_manual_V_A4.pdf#page=536): “Table columns: Code (hex) | Fault | Cause | What to do 9084 | External fault 4 (Editable message text) Programmable fault: 31.07 External event 4 source 31.08 E…”

## Retrieval quality and remaining weak results

- Overheating: the final list includes general supervision on p.64, direct abnormal-temperature/cooling evidence on p.89, a caution about excessive heat production on p.107, filter maintenance on p.90, and cooling-system monitoring on p.91. The general supervision result still ranks above the more specific cooling evidence.
- ACS880 fault tracing: the broad query retrieves actual entries from the fault-tracing chapter, but specific fault entries outrank the introductory overview. It is not a diagnosis and does not establish that those faults apply to any equipment.
- ACS880 A4F6 IGBT temperature: the actual warning entry on physical p.503 ranks first in the final hybrid results.
- Bare A4F6: code-mapping tables on p.126 outrank the warning entry. Short identifiers remain a semantic weakness; keyword retrieval finds the actual entry, but equal-weight RRF can promote mapping-table overlap.
- Maintenance and vibration queries are included in the full six-query harness. Some general maintenance or short heading fragments remain; no weak results were removed from the logs.
- The first run ranked generic ABB/warranty text too highly and included decorative chapter-number hits. Deterministic query cleanup and heading/table chunk fixes improved the results. The first unmodified rankings are preserved in data/processed/retrieval-before-fixes.json.

## Extraction limitations

- Empty extracted text: ACS880 physical p.4 and motor-manual physical p.131. Both physical pages remain stored; no OCR or fabricated content was added.
- No fatal parsing failures or recorded table-extraction exceptions occurred. This does not establish perfect table reconstruction.
- Motor troubleshooting charts use merged cells, bullet matrices and column-group labels; e.g. physical pp.92 and 96 can produce rows with blank malfunction cells. These rows are returned as extracted, with page/bounding-box provenance; missing associations are not guessed.
- Some ACS880 mapping tables (e.g. p.126) retain duplicate/flattened text alongside structured rows. Numeric-only or very short fragments remain in the corpus (97 chunks shorter than 30 characters). These are known retrieval noise, not invented information.
- Visual checks covered ACS880 p.3 and p.503 and motor p.105 and p.132, plus raw-text inspection of relevant chapters. Not every page or table was visually verified.
- Image warnings include logos. Diagrams are not interpreted; content_type=diagram indicates extracted caption text only.
- Page-local section and safety associations are heuristic. Adjacent warning markers/body text are merged where detected; longer warnings remain linked in metadata. Cross-page safety/applicability relationships are not exhaustively resolved.
- Database content-type counts: diagram=13, fault_code=350, paragraph=1274, procedure=60, table=9203, warning=185.

## Actual setup and execution commands

The project directory is `C:\Users\rleem\Documents\Codex\2026-09-10\https-www-hackerearth-com-community-challenges\abb-guardian`. Initial environment setup was run from its parent; the remaining commands were run from the project directory.

```powershell
$env:UV_CACHE_DIR=Join-Path (Get-Location) 'work\uv-cache'
uv venv 'abb-guardian\.venv' --python 'C:\Users\rleem\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
uv pip install --python 'abb-guardian\.venv\Scripts\python.exe' -r 'abb-guardian\requirements.txt'
cd abb-guardian
$env:UV_CACHE_DIR=Join-Path (Get-Location) '..\work\uv-cache'
uv pip install --python '.venv\Scripts\python.exe' 'torch==2.6.0' 'transformers==4.49.0' 'sentence-transformers==3.4.1'
Copy-Item .env.example .env
.\.venv\Scripts\python.exe scripts\download_manuals.py
.\.venv\Scripts\python.exe scripts\inspect_corpus.py
.\.venv\Scripts\python.exe scripts\setup_native_postgres.py
& '.\work\native-postgres\pgsql\bin\postgres.exe' -D '.\work\native-postgres\data' -p 55432 -h 127.0.0.1
# In a second shell after PostgreSQL is running:
.\.venv\Scripts\python.exe scripts\setup_native_postgres.py
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m app.db.init_db
.\.venv\Scripts\python.exe scripts\ingest_manuals.py
# After the model is cached, subsequent inference works offline:
$env:HF_HUB_OFFLINE='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts\ingest_manuals.py --rebuild
.\.venv\Scripts\python.exe scripts\test_search.py > data\processed\retrieval-console.txt
.\.venv\Scripts\python.exe -m pytest --integration --corpus -q --basetemp work\pytest-final --tb=short > data\processed\pytest-output.txt
.\.venv\Scripts\python.exe scripts\ingest_manuals.py > data\processed\idempotency-console.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Preferred PostgreSQL startup elsewhere: `docker compose up -d --wait`. The application is not Dockerized. Docker Compose could not be validated here because Docker Desktop had no running engine; native PostgreSQL was fully validated instead.

For a clean repeat, use the shorter setup in README.md and install requirements.lock.txt. The model initially downloaded successfully online; final tests and retrieval ran with HF_HUB_OFFLINE=1.

## Pytest output

```text
................                                                         [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\rleem\Documents\Codex\2026-09-10\https-www-hackerearth-com-community-challenges\abb-guardian\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  C:\Users\rleem\Documents\Codex\2026-09-10\https-www-hackerearth-com-community-challenges\abb-guardian\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
16 passed, 2 warnings in 4.32s
```

## Failures encountered and resolved

1. The original conversation's sandbox file-read failure was no longer present on this attempt. A project directory and execution-check.txt were created/read before implementation.
2. PowerShell Invoke-WebRequest failed ABB TLS authentication. The downloader used Python httpx with certificate verification enabled and obtained both official PDFs successfully.
3. Docker Desktop did not expose an engine; its configuration access/startup attempts did not make it available. A project-local PostgreSQL fallback was used.
4. pg_ctl reported 'could not create restricted token: error code 87'. Direct postgres.exe startup succeeded under the existing sandbox. The fallback script now handles this specific launcher failure.
5. A newly installed torch 2.14.0 DLL was blocked by Windows Application Control. The pinned torch 2.6.0 / transformers 4.49.0 / sentence-transformers 3.4.1 combination imported and ran successfully; no operating-system policy was changed.
6. pytest's shared default temporary directory was inaccessible. Tests ran successfully using project-local --basetemp paths.
7. Test setup initially resolved corpus tables from the public schema. Explicit SQLAlchemy schema translation now isolates test tables. An interrupted localhost connection test left one empty test schema, which was checked and removed. Final audit shows no test schemas.
8. Two dependency deprecation warnings remain (Starlette/httpx and anyio BlockingPortal). They do not affect the passing tests and are retained in the recorded output.

## Architecture changes and reasons

- Added document_pages so all physical pages and raw extraction remain auditable and chunk page provenance is database-enforced.
- Added corpus_config to reject embedding-space/configuration mismatches before retrieval or ingestion.
- Added a SHA-256 manifest check, advisory locks and atomic rebuilds to prevent duplicates and partial ingestion.
- Added source block bounding boxes, extraction notes and safety_context to make text/table fragments reviewable without building a UI.
- Used exact SQL-filtered pgvector search for this corpus while creating the required HNSW index; this avoids approximate filtering recall surprises.
- Added deterministic query cleanup after observed poor results; it removes redundant wording without inventing technical facts or queries.
- Added optional project-local Windows PostgreSQL startup because Docker was unavailable. The standard Compose setup remains included.

## Native database download provenance

```json
{
  "postgres": {
    "url": "https://get.enterprisedb.com/postgresql/postgresql-17.11-3-windows-x64-binaries.zip",
    "sha256": "4b8db0930c38f6ef845db919551dedda3b6b845aeb0927b3d79a6e8e9e4537cf",
    "checksum_note": "Observed download hash, not publisher-verified"
  },
  "pgvector": {
    "url": "https://github.com/andreiramani/pgvector_pgsql_windows/releases/download/0.8.6_17/vector.v0.8.6-pg17.zip",
    "sha256": "420388e9e9f05d92f06d6967ce8772483629b27a66ca9255925fa0fdd445438e",
    "checksum_note": "Verified against GitHub release asset digest"
  }
}
```

## Final source tree

The archive includes both real PDFs and validation outputs. Virtual environment, model cache, native database binaries/data, scratch files and .env are excluded.

```text
abb-guardian/
  .env.example
  .gitignore
  backend/app/__init__.py
  backend/app/api/__init__.py
  backend/app/api/documents.py
  backend/app/api/search.py
  backend/app/config.py
  backend/app/db/__init__.py
  backend/app/db/init_db.py
  backend/app/db/session.py
  backend/app/main.py
  backend/app/models/__init__.py
  backend/app/models/document.py
  backend/app/models/document_chunk.py
  backend/app/schemas/__init__.py
  backend/app/schemas/document.py
  backend/app/schemas/search.py
  backend/app/services/__init__.py
  backend/app/services/chunking.py
  backend/app/services/embeddings.py
  backend/app/services/hybrid_search.py
  backend/app/services/ingestion.py
  backend/app/services/keyword_search.py
  backend/app/services/pdf_parser.py
  backend/app/services/query_normalization.py
  backend/app/services/search_common.py
  backend/app/services/semantic_search.py
  backend/tests/conftest.py
  backend/tests/test_api.py
  backend/tests/test_chunking.py
  backend/tests/test_query_normalization.py
  backend/tests/test_retrieval.py
  backend/tests/test_rrf.py
  data/evaluation_queries.json
  data/manuals/abb_induction_motors_generators_manual.pdf
  data/manuals/acs880_primary_control_program_firmware_manual.pdf
  data/manuals/manifest.json
  data/processed/.gitkeep
  data/processed/3605e706-4103-5b86-b9e0-fdac03d34b96.json
  data/processed/85229f68-87c9-5314-a4ad-6fb5a6094570.json
  data/processed/api-smoke.json
  data/processed/database-audit.json
  data/processed/idempotency-console.txt
  data/processed/ingestion-summary.json
  data/processed/pytest-output.txt
  data/processed/retrieval-before-fixes.json
  data/processed/retrieval-console.txt
  data/processed/retrieval-results.json
  docker-compose.yml
  execution-check.txt
  pytest.ini
  README.md
  requirements.lock.txt
  requirements.txt
  scripts/download_manuals.py
  scripts/ingest_manuals.py
  scripts/inspect_corpus.py
  scripts/setup_native_postgres.py
  scripts/test_search.py
  VALIDATION.md
```

All 18 Step 1 acceptance criteria were checked. OCR, diagnosis generation, frontend work and all other Step 2 features remain unimplemented.
