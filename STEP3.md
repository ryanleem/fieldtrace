# Step 3: visual evidence intake

Step 3 stores visible observations only. It does not diagnose internal conditions,
identify root causes, decide whether equipment can operate, recommend repairs,
verify diagnostic claims, calibrate diagnostic confidence, detect document conflicts,
or create a knowledge graph. Severity describes apparent physical extent, not urgency.
Visual confidence describes visibility, not a calibrated probability.

## Setup

Reuse the existing Python environment, PostgreSQL and ingested manuals. No additional
dependencies or re-ingestion are required. Select OpenAI or Gemini using the settings
below. Put the selected provider's key in the process environment or private `.env`.
Do not put credentials in source control.

| Provider | Selection | Required key | Model setting |
|---|---|---|---|
| OpenAI | `VISION_PROVIDER=openai` | `OPENAI_API_KEY` | `VISION_MODEL=gpt-4.1-mini-2025-04-14` |
| Google Gemini | `VISION_PROVIDER=gemini` | `GEMINI_API_KEY` | `GEMINI_VISION_MODEL=gemini-2.5-flash` |

The separate model settings prevent switching providers from accidentally sending an
OpenAI model name to Gemini. `GOOGLE_API_KEY` is not an alias in this application.
Restart the API after changing configuration because settings are cached. Selection
is explicit; the app does not silently send images to a second provider on failure.
After switching, use the single-image analyze endpoint to retry failed images.
Previously successful analyses remain idempotent; use a fresh session to compare providers.

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m app.db.init_vision
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002
```

Startup initializes the additive tables automatically. Existing sessions are reused.
Defaults: `VISION_PROVIDER=openai`, `VISION_MODEL=gpt-4.1-mini-2025-04-14`,
`VISION_TIMEOUT_SECONDS=60`, `MAX_INSPECTION_IMAGES=30`,
`MAX_INSPECTION_IMAGE_BYTES=10485760`, `MAX_INSPECTION_IMAGE_PIXELS=16000000`.
`UPLOADS_DIR` defaults to `data/uploads` under the repository root.

The adapter uses the OpenAI Responses API with an image data URL, `store=false`, and
a strict JSON schema. [Official image-input documentation](https://developers.openai.com/api/docs/guides/images-vision)
and [structured-output documentation](https://developers.openai.com/api/docs/guides/structured-outputs)
describe that API contract. Provider availability depends on account credits/access.

The Gemini adapter uses Google's official [generateContent REST API](https://ai.google.dev/api/generate-content)
with inline image data and JSON Schema output. It uses the existing `httpx` dependency;
no new SDK is needed. Both adapters feed the same `VisionResult` parser and existing
session/aggregation/retrieval-context services. The database assigns `source=vision_model`
for both; provider/model details remain in raw audit responses. Neither adapter claims
reliable localization, so bounding regions remain null. Raw blocked, truncated or invalid
responses cannot become findings. Malformed/out-of-scope output gets one strict retry;
HTTP failures yield a failed image state without findings. Empty findings describe only
what is visible in that image, never overall equipment health. The lexical scope guard
is not a complete semantic guarantee and human review remains necessary.

See [the provider validation report](STEP3-PROVIDER-VALIDATION.md) for the latest live
evaluation and its misses. Older quota-only reports are historical snapshots.

## API

Create a session with the existing `POST /sessions`. Identify and confirm through
the existing Step 2 endpoints. Upload unconfirmed images if needed; no view is mandatory.

| Endpoint | Behavior |
|---|---|
| `POST /sessions/{id}/images` | Multipart `images` repeated one or more times; JSON arrays `view_labels` and `user_notes` parallel to images. Missing arrays/null entries default to `additional`/null. Returns created records, UUIDs and status. |
| `GET /sessions/{id}/images` | Metadata including equipment snapshot, note, view, original filename, timestamp and status. |
| `POST /sessions/{id}/images/{image_id}/analyze` | Analyze a pending/failed image; successful results are idempotent. |
| `POST /sessions/{id}/images/analyze-all` | Analyze each pending image independently; return per-image results and rebuilt aggregates. Failed images require explicit single-image retry. |
| `GET /sessions/{id}/visual-findings` | Images, view/note/status maps, normalized findings and aggregates. |
| `GET /sessions/{id}/visual-context` | Structured visual evidence and text prepared for a later explicit search. |

```powershell
curl.exe -X POST "http://127.0.0.1:8002/sessions/SESSION_UUID/images" `
  -F "images=@front.jpg" -F "images=@detail.jpg" `
  -F 'view_labels=["front","close_up"]' `
  -F 'user_notes=[null,"Noise reported here"]'
```

Views: front, back, left, right, top, bottom, nameplate, close_up, additional.
Repeated close-ups/additional images are supported. The session cap includes previous
uploads. Invalid metadata/images return 422; unknown session/image returns 404;
active analysis or changed equipment association returns 409. Analysis failures are
persisted as `failed` with an error and no findings; the response body carries this
status even when the analysis endpoint returns HTTP 200.

No delete/replace endpoint is included. Use a fresh session for a different physical
asset. The model does not establish that all submitted photos depict the same asset.

## Storage and lifecycle

Three additive tables: `session_images`, `visual_findings`,
`aggregated_visual_findings`. UUID filenames are stored at
`data/uploads/{session_id}/{image_id}.{jpg|png|webp}`. Original names are metadata only.
Magic-byte decoding, full decode, file/pixel limits and animation rejection protect
image intake. Declared MIME types are not trusted. Batch upload validates all files
before writing; database failure removes files created by that request.

Each image stores confirmed equipment ID at upload, or at analysis if still null.
Analysis never edits Step 2 state. If confirmation changes during a request, normalized
results are discarded and raw attempts kept. Previously analyzed images retain their
original association. The context helper excludes images linked to other equipment,
and does not attribute already-analyzed unconfirmed images to a newly confirmed model.
Upload those photos again under the reviewed confirmation to use them in that context.

Analysis status: pending, analyzing, completed, no_clear_abnormality, failed. A bounded
lease prevents simultaneous analysis of one image and permits single-image retry after
a process interruption. Session row locks serialize count checks and aggregate rebuilds.
Original bytes stay on disk. Provider copies are EXIF-oriented, converted to RGB,
resized to at most 2200px and stripped of metadata before transmission.

Raw attempts and the orientation context live in `session_images.raw_vision_results`,
separate from findings. They may contain rejected/untrusted model text. Inspect through
the database or internal `visual_state(..., include_raw=True)` for audit; normal HTTP
responses and retrieval context do not expose raw text. User notes are stored separately
and remain explicitly labeled user reports; they are not appended to the visual query.

## Vision contract and scope

`VisionProvider.analyze_equipment_image(VisionImage, context, strict=False)` is the
adapter boundary. It returns `{output, raw}`. Register a replacement in
`get_vision_provider()` or inject it with FastAPI dependencies. The exact prompt is the
`VISION_PROMPT` constant in `backend/app/services/vision_provider.py`, reproduced in
the validation report and evaluation output. Manufacturer, family, model, view and
optional note are orientation only. Labels, notes and image text are untrusted.

Pydantic validates the summary and each finding, forbids extra fields, limits text,
enforces low/medium/high ordinals and validates optional normalized boxes including
their extents. This adapter always requests null boxes; it has no reliable localization.
`id` in stored finding records is the finding UUID; `id` in an aggregate is its aggregate
UUID. Source is `vision_model`; relationships preserve session/image provenance.

Taxonomy: corrosion, rust (normalized to corrosion), crack, broken_component,
damaged_cable, damaged_insulation, burn_mark, discoloration, leakage, fluid_residue,
dust_buildup, debris, missing_component, missing_fastener, deformation, bent_component,
surface_wear, abrasion, damaged_housing, blocked_ventilation,
unknown_visible_abnormality. Unrecognized visual labels use the last value; original
description and raw output are preserved.

Conservative prompting plus a lexical scope guard rejects common diagnostic, causal,
repair and operational-safety wording in summaries, issue types and descriptions.
Malformed/out-of-scope output gets one strict retry; failure stores no fallback findings.
This guard is **not** a semantic guarantee or a future grounded post-claim verifier.
It can reject harmless wording and miss paraphrases. Human review remains necessary.

`no_clear_abnormality` means only that the image produced no clear visible finding.
Occlusion, blur, glare and unseen/internal conditions remain unknown.

## Aggregation and retrieval handoff

Aggregation requires the same equipment snapshot, issue type and normalized location.
Normalization folds case/punctuation/articles and housing/enclosure. Direction and
component identifiers remain distinct. Vague locations are not merged. If multiple
same-type/same-location findings occur in one image, that location group remains
unmerged because correspondence is ambiguous. Supporting image and finding UUIDs are
preserved. Severity uses the maximum apparent extent; confidence uses the minimum
supporting confidence and never rises merely because there are multiple views.

This is a conservative duplicate heuristic, not physical feature tracking. Different
parts described identically may still merge; different descriptions may under-merge.
Original per-image evidence remains available. Aggregate IDs are deterministic for a
given support set. An aggregate records its rebuild timestamp.

`build_visual_retrieval_context(session_id, engine=None)` prepares all matching visual
evidence plus confirmed metadata/filters. `visual_search_request(context, embedder)`
optionally packs findings within the existing encoder token limit, returning omitted
finding IDs explicitly. Full structured context is retained. Call the existing
`search_all` explicitly if needed; no endpoint automatically searches or diagnoses.

## Tests and qualitative evaluation

```powershell
$env:HF_HUB_OFFLINE='1'
.\.venv\Scripts\python.exe -m pytest --integration --corpus -q -p no:cacheprovider
.\.venv\Scripts\python.exe scripts\demo_visual_contract.py
.\.venv\Scripts\python.exe scripts\evaluate_vision.py
```

The contract demo uses synthetic images and explicitly mocked vision, while exercising
the real database/API and real ABB retrieval. It is not a vision-quality demonstration.
The evaluation script uses actual licensed photographs and the live configured adapter,
verifies image hashes, and writes `data/evaluation/results.json` after each image.
It does not pass labels, source titles or annotations to the model.

See `data/evaluation/manifest.json` for author, license, source, thumbnail changes,
hashes and broad labels. The seven-image sample contains electrical connectors, fans,
a tractor socket/bracket and cable damage. It is not ABB-specific. Keep image licenses
and attribution when redistributing. Labels were created by Codex visual review, not
an independent industrial inspector. A human should review labels and returned claims.

Current live run: all seven requests returned 429 because API credits were exhausted.
No findings or accuracy conclusions can be drawn. Re-run after funding the API key;
review recognized issues, false positives, missed abnormalities and any diagnostic
language. The live qualitative acceptance criterion remains outstanding.

Prototype limits: synchronous loopback API, no authentication/frontend, no production
upload-body gateway limit, no background job worker, and no automatic disk retention
or orphan cleanup after abrupt crashes. Do not expose this development server publicly.
No Step 4 functionality has been added.
