# Step 3 live validation rerun

**Still blocked; Step 3 is not fully validated.** No application source or configuration changed; no Step 4 work added.

Provider: OpenAI Responses API. Model: `gpt-4.1-mini-2025-04-14`. The effective `OPENAI_API_KEY` is present in the process environment, not the project `.env`. Keys were not printed. Settings can load that same variable from either source; process environment takes precedence.

Abstraction: `backend/app/services/vision_provider.py` defines `VisionProvider`, `VisionImage`, `OpenAIVisionProvider` and `get_vision_provider()`. Only `openai` is implemented. `scripts/evaluate_vision.py` resolves that factory, validates each manifest image/hash, and calls `run_vision(provider, VisionImage(data, mime), {view_label: ...})`. That helper invokes `analyze_equipment_image`, validates structured findings, and permits one stricter retry for malformed/out-of-scope output. Labels and source filenames are withheld from the provider.

Executed the repository Python environment with `python scripts/evaluate_vision.py --output data/evaluation/validation-rerun.json`. The output override preserves the prior run. Exit status: 1. All seven image requests returned HTTP 429. A separate minimal request confirmed the specific error:

```json
{
  "http_status": 429,
  "type": "insufficient_quota",
  "code": "credit_balance_exhausted",
  "message": "You have no credits remaining. Add credits to continue using the API at https://platform.openai.com/settings/organization/billing/."
}
```

## Per-image results

| Filename | Expected broad visible labels | Model result |
|---|---|---|
| photo-01.jpg | corrosion, discoloration | HTTP 429; no model output |
| photo-02.jpg | crack, damaged_housing | HTTP 429; no model output |
| photo-03.jpg | dust_buildup | HTTP 429; no model output |
| photo-04.jpg | Clean/benign fan display; limited visibility | HTTP 429; no model output |
| photo-05.jpg | corrosion, surface_wear | HTTP 429; no model output |
| photo-06.jpg | burn_mark, discoloration, damaged_housing | HTTP 429; no model output |
| photo-07.jpg | damaged_cable, damaged_insulation | HTTP 429; no model output |

For every image, returned issue types, location, severity, confidence and description are unavailable. Observation-only compliance and hidden-failure hallucination are **not assessed**, rather than passed or failed. The raw harness flags are false because there is no valid result; that is not evidence of a hallucination. The accompanying summary JSON uses null for unavailable assessments.

Qualitative successes: none can be measured. False positives, missed obvious findings, and hidden-failure hallucinations: unassessable because no model text was returned. These requests must not be counted as visual detection misses or clean-image successes. Structured output could not be validated on live responses.

## Regression and preservation

`python -m pytest --integration --corpus -q -p no:cacheprovider --basetemp work/pytest-validation-rerun --tb=short` completed: **64 passed, 2 warnings in 7.15s**. The warnings are the existing Starlette/httpx and anyio deprecations. Image/session linkage, aggregation and real-corpus retrieval remain covered by deterministic/integration tests; they do not substitute for live accuracy evaluation.

Byte comparison against the Step 3 implementation ZIP found **zero changes among 58 backend, script and dependency-lock files**. Step 1/2 code and behavior remain preserved. No architecture rewrite or Step 4 reasoning was added.

## Smallest unblock

Fund the existing OpenAI account or set `OPENAI_API_KEY` to a funded OpenAI project key with access to the configured model. This is a credential-only change; preserve `VISION_PROVIDER=openai` and the current model. Restart the application after changing its environment (settings are cached); the evaluation script loads fresh settings each run. Do not paste keys into chat.

There is no second supported vendor adapter in this repository. Merely setting VISION_PROVIDER to another vendor will fail. To use a different vendor, the smallest code change would be one adapter implementing the existing protocol and returning `{output, raw}`, its environment credential/model settings, and a factory registration. Session, ingestion, retrieval and aggregation code need not change. An arbitrary OpenAI-compatible base URL is not presently configurable either. No unverified alternative was selected or claimed to work.

## Remaining limits and next validation

Rerun the seven real photographs once generation access is funded, inspect all returned descriptions and raw retry attempts, and assess recognition, severe clean-image false positives and prohibited internal-failure claims. Only then can live acceptance be considered.

The existing seven-image manifest covers corrosion/discoloration, a connector crack, dust, a benign fan, surface wear, damaged housing and damaged cable insulation. It does not contain explicit positive labels for leakage/fluid residue or missing fasteners; those classes remain untested. Deformation is described in one annotation but not independently labeled. Generic consumer/electrical components, one composite, and a blurred water display do not establish industrial field accuracy or ABB-specific performance. Labels were reviewed by Codex, not an independent technician.

Acceptance remains unmet for successful live processing, useful abnormality recognition, benign-image false-positive control, live observation-only compliance and live schema validation. The implementation/test checks continue to pass. **Step 3 cannot yet be called fully validated.**
