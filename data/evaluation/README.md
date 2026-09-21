# Prototype qualitative visual-inspection evaluation

Seven real photographs of generic electrical hardware. This sample is not an ABB
equipment identification test, a statistical benchmark, or field validation.

`manifest.json` records source page, author, Creative Commons license/link, downloaded
thumbnail URL, SHA-256, changes and broad visible labels. Keep the manifest with these
photos when redistributing. CC BY-SA images retain their respective share-alike licenses;
CC BY images retain their attribution licenses. The photos do not inherit any code license.
Thumbnails were provided by Wikimedia; this repository made no visual alterations.

Labels were produced by Codex inspecting each downloaded photograph before any vision
API results, not by an independent human technician. They are non-exhaustive review aids.
In particular, source descriptions that claim causes or equipment failure were excluded
from labels and are never sent to the model. Photo 01 is an existing multi-panel composite,
not multiple separately analyzed camera uploads. Photo 04 is a water-display fan with
limited visibility; the water is not labeled as leakage. Photo 07 shows damaged cable
cover and exposed braid near the connector; no electrical state is inferred.

Run `python scripts/evaluate_vision.py` from the project root with a funded API key.
Expected labels and source titles are withheld from the model. `results.json` stores
returned findings, validation status, raw response attempts and errors. Scope-guard
success is only a lexical check, not confirmation that every statement is visually true.
Review each claim against the photograph before interpreting the outcome.

Recorded run: **seven provider failures, zero successful analyses**. The account returned
HTTP 429; a separate minimal request confirmed `credit_balance_exhausted` /
`insufficient_quota`. No field-accuracy or recognition claim can be made from this run.
The live qualitative acceptance criterion is outstanding. The deterministic contract
demo elsewhere in the repository does not substitute for this evaluation.
