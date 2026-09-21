# Step 3 provider validation - 2026-09-19

## Outcome

OpenAI live visual evaluation succeeded on all seven existing real photographs using the final adapter and its original networking defaults. Gemini support is implemented and mock-tested, but no GEMINI_API_KEY was present for a live Gemini run. No Step 4 functionality was added.

This is a prototype qualitative visual-inspection evaluation, not a field-accuracy benchmark. Expected labels are broad manual annotations, not independently certified ground truth. Review below was performed by Codex against the actual photographs.

## Final live run

- Provider: OpenAI; requested and returned model: `gpt-4.1-mini-2025-04-14`.
- Seven unique images; seven API calls succeeded; zero failed; one attempt per image.
- Seven valid structured outputs; all bounding regions null; all outputs stayed within visible-observation scope.
- Main labeled abnormality recognized in five of six abnormal images, plus one correct benign result.
- One primary miss (connector crack) and two secondary omissions (worn coating and housing deformation).
- Zero obvious false-positive abnormalities on this review; no severe false positive on the single benign image.
- Zero hidden/internal failures asserted, including in raw responses.
- Duplicate issue labels for the same cable damage and approximate locations remain limitations.

## Per-image review

### photo-01.jpg (close_up)

Expected: corrosion, discoloration. Contact strips show mottled dark and greenish deposits; composite photograph includes disassembly. Loose ends are not evidence of a missing component.

Provider/model: openai / gpt-4.1-mini-2025-04-14.

Image summary: The image shows a disassembled power strip with multiple views of the plug, socket outlets, internal components, and stripped wires.

- `corrosion` at middle right, on two metal strips; severity **medium**, visual confidence **high**. visible greenish corrosion on metal strips
- `surface_wear` at top left, on the socket outlet surfaces; severity **medium**, visual confidence **high**. visible surface wear and discoloration on socket outlet surfaces

Reasonableness: Reasonable corrosion and worn/discolored surfaces. Location of the metal strips is approximate.
False positives: None obvious.
Misses: No primary miss; discoloration is described under surface_wear.
Visible-only: yes. Hidden-failure hallucination: none observed.

### photo-02.jpg (close_up)

Expected: crack, damaged_housing. Visible split/irregular fracture line across clear connector shell near the lower edge; do not infer electrical performance.

Provider/model: openai / gpt-4.1-mini-2025-04-14.

Image summary: Close-up image of a transparent RJ45 connector plug.

- `surface_wear` at top and side surfaces of the connector plug; severity **low**, visual confidence **high**. visible dust buildup and surface wear on plastic surfaces

Reasonableness: Minor surface dust/wear is plausible, but it misses the manifest-labeled split in the transparent shell.
False positives: No obvious severe false positive; high confidence in subtle wear should be reviewed.
Misses: Primary miss: crack/damaged housing.
Visible-only: yes. Hidden-failure hallucination: none observed.

### photo-03.jpg (close_up)

Expected: dust_buildup. Dense pale dust on fan blades and hub.

Provider/model: openai / gpt-4.1-mini-2025-04-14.

Image summary: Dust buildup is visible on the fan blades and surrounding areas.

- `dust_buildup` at fan blades and center of fan; severity **medium**, visual confidence **high**. Visible dust buildup on fan blades and the center of the fan.

Reasonableness: Thick dust on fan blades and hub is clearly visible.
False positives: None obvious.
Misses: None obvious.
Visible-only: yes. Hidden-failure hallucination: none observed.

### photo-04.jpg (front)

Expected: no obvious abnormality. Fan in a trade-show water display; no clear physical abnormality visible; blur and reflections limit visibility. Water in the display is not leakage.

Provider/model: openai / gpt-4.1-mini-2025-04-14.

Image summary: No obvious visible abnormality detected in this image.

- No findings. This does not establish equipment health.

Reasonableness: Appropriate empty finding list for a benign water-display fan; water is not called leakage.
False positives: None.
Misses: None against the manifest; blur limits what can be concluded.
Visible-only: yes. Hidden-failure hallucination: none observed.

### photo-05.jpg (close_up)

Expected: corrosion, surface_wear. Orange-brown patches and worn coating on metal bracket beside 12V socket; dust on surfaces. Title does not establish the connector is broken.

Provider/model: openai / gpt-4.1-mini-2025-04-14.

Image summary: Close-up of a 12V electrical component with surrounding metal surface showing rust and discoloration.

- `corrosion` at left side metal surface near the electrical component; severity **medium**, visual confidence **high**. visible rust with orange-brown discoloration and rough texture on metal surface

Reasonableness: Corrosion is clearly visible on the surrounding metal plate.
False positives: None obvious.
Misses: Secondary omission: worn coating/surface wear is not explicitly distinguished from corrosion.
Visible-only: yes. Hidden-failure hallucination: none observed.

### photo-06.jpg (close_up)

Expected: burn_mark, discoloration, damaged_housing. Blackened and deformed material at upper-right terminal region; yellow-brown marks on surrounding surface. Cause unknown from image.

Provider/model: openai / gpt-4.1-mini-2025-04-14.

Image summary: Burn damage and discoloration visible on electrical outlet and surrounding wires.

- `burn_mark` at right side of the outlet near the terminals and wires; severity **high**, visual confidence **high**. Visible burn mark with black charring and discoloration on the outlet and wires.
- `discoloration` at top middle edge of the outlet; severity **medium**, visual confidence **high**. Visible brown discoloration around screws and outlet surface.

Reasonableness: Charring and brown/yellow discoloration are visibly supported; no cause is asserted.
False positives: None obvious.
Misses: Secondary omission: deformed/damaged housing is not separately described.
Visible-only: yes. Hidden-failure hallucination: none observed.

### photo-07.jpg (close_up)

Expected: damaged_cable, damaged_insulation. Frayed outer cable cover near connector; confirm against photograph before evaluation.

Provider/model: openai / gpt-4.1-mini-2025-04-14.

Image summary: Visible damaged insulation and damaged cable on both ends of a white cable.

- `damaged_cable` at near both ends of the cable; severity **high**, visual confidence **high**. Visible torn and frayed cable insulation exposing inner wires on both ends of the cable.
- `damaged_insulation` at near both ends of the cable; severity **high**, visual confidence **high**. White insulation is visibly torn and missing, exposing the internal wiring.

Reasonableness: Exposed inner conductors and torn outer insulation are clearly visible.
False positives: None obvious.
Misses: No primary miss. damaged_cable and damaged_insulation overlap for the same physical damage; do not count them as independent problems.
Visible-only: yes. Hidden-failure hallucination: none observed.

## Availability history and reproducibility

The first evaluation in this task returned HTTP 429 on all seven images. Subsequent connectivity probes succeeded. A seven-image direct-transport run then succeeded, and a final seven-image run with the original networking defaults also succeeded. A temporary routing option was removed because it was unnecessary. No API key, provider or OpenAI model was changed. No proxy was discovered in the environment/system checks, so the cause of the availability change is unproven; the new 429s were not independently classified as billing versus rate limiting.

Across the three evaluation passes: 21 image-analysis calls, 14 successful and 7 failed, on the same seven unique images. Separate connectivity probes are excluded from those evaluation counts. Earlier results are retained rather than overwritten.

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_vision.py --output data/evaluation/results-openai-final.json
```

Detailed responses and exact outputs: [final results](data/evaluation/results-openai-final.json). Earlier [429 run](data/evaluation/results-openai-provider-switch.json) and [direct-transport run](data/evaluation/results-openai-direct.json).

## Regression tests

```powershell
.\.venv\Scripts\python.exe -m pytest --integration --corpus --basetemp work/pytest-provider-switch-final -q
```

**85 passed**, no skips or failures; two existing dependency deprecation warnings. This includes all original 64 tests and 21 added provider tests, including Gemini session persistence, image IDs, source attribution, aggregation and preservation of equipment confirmation. Existing tests exercise OCR/equipment filtering and retrieval against the real ABB corpus. [Saved test output](data/processed/pytest-provider-switch-final.txt).

## Limits and readiness

Suitable for a supervised hackathon demonstration of visible evidence extraction, with manual review and explicit failed/no-clear-abnormality states. It is not reliable enough to promise complete visual inspection. The connector crack was missed in both successful passes. The seven-photo set contains generic electrical hardware, not a representative ABB motor/drive field sample. It has no positive leakage/fluid-residue example and no dedicated missing-part/fastener example; those categories remain unvalidated. Housing deformation was visible but not separately captured. A single benign photo cannot establish a general false-positive rate. Gemini live quality and account access remain untested until a key is configured. Ordinal visual confidence is not calibrated.

## Files changed

- `backend/app/config.py`: Gemini key/model settings; secret excluded from dumps/repr.
- `backend/app/services/vision_provider.py`: Gemini adapter and factory/model selection; shared prompt clarifications; preserved OpenAI request implementation.
- `backend/app/schemas/vision.py`: existing lexical scope guard also rejects internal short circuits. Taxonomy unchanged.
- `backend/tests/test_vision_providers.py`: 21 deterministic provider and session tests.
- `scripts/evaluate_vision.py`: correct provider/model, view label and expectation in reports; expected labels still never sent to the model.
- `.env.example`, `STEP3.md`, `README.md`: configuration and behavior documentation.
- This report, three evaluation JSON artifacts, and saved test output.

The session/database/retrieval implementations and Step 1/2 behavior were not changed. The supplied workspace has no Git repository metadata, so this is a file-level change inventory rather than a Git diff.
