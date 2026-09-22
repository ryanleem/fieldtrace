# FieldTrace: ABB Prototype Phase presentation outline

Ten slides about the built Steps 1–6 prototype. This Markdown production brief accompanies the [4–5 minute demo](ABB-DEMO-SCRIPT.md); it is not a rendered deck.

Visual direction: ABB red #FF000F accents, black/dark gray text, medium gray secondary text, light gray rules, near-white and white backgrounds. Use generous space, a plain sans serif and one main visual per slide. Prefer actual UI screenshots. Label recordings and fixtures visibly. Avoid purple gradients, glowing brains, futuristic stock imagery and implied ABB endorsement. Retain reference-photo attribution.

## Slide 1: FieldTrace

**Purpose:** Introduce the built prototype and its starting point.

**Exact on-slide text:**

> FieldTrace
>
> Industrial troubleshooting starts with the equipment in front of you.
>
> ABB Accelerator 2026 · Prototype Phase

**Recommended screenshot/visual:** Actual workspace heading and intake, with no old case data. Near-white background with a red accent.

**Speaker notes:** We built a local technician workspace that connects equipment identity, physical observations, symptoms and ABB documentation in one troubleshooting session. Its output supports technician review. It does not establish whether equipment is safe to operate.

## Slide 2: Manual search leaves context with the technician

**Purpose:** Explain the problem without inventing productivity statistics.

**Exact on-slide text:**

> Manual search leaves context with the technician
>
> Which model and revision apply?
> What is visible on this equipment?
> Which checks have already happened?
> Does the passage support the claim?

**Recommended screenshot/visual:** Readable crop of an actual ABB fault table with document title and revision identified.

**Speaker notes:** Finding a passage is only part of the work. The technician must relate it to the equipment, observations and previous checks. We have not measured time saved or downtime reduction; those require a field study.

## Slide 3: The built prototype connects the whole case

**Purpose:** Explain the difference from basic document chat.

**Exact on-slide text:**

> The built prototype connects the whole case
>
> Confirmed equipment + visible photo findings + symptoms and fault codes
>
> Hybrid ABB retrieval + claim verification + exact citations
>
> Follow-up stays in the same session

**Recommended screenshot/visual:** Confirmed-equipment and session-activity crops from the same real run, arranged as one evidence strip.

**Speaker notes:** FieldTrace is not simply chat with a PDF. The distinction is its connected workflow, from confirmation and structured image evidence through cited-claim checks and persistent follow-up. We do not claim that no other product combines these capabilities.

## Slide 4: A technician can begin immediately

**Purpose:** Explain the final first-use workflow.

**Exact on-slide text:**

> A technician can begin immediately
>
> Enter a model, symptom or fault code. Add photos.
> Detect equipment and confirm the match.
> Inspect visible conditions and run troubleshooting.
> Open a source, then continue with an update.
>
> The app creates a session when it needs one.

**Recommended screenshot/visual:** Fresh intake with model text, fault 5091 and a queued photo preview. Include the confirmation hint.

**Speaker notes:** Typing and photo selection work before session creation. Detect creates or reuses a session and preserves drafts. Confirmation gates troubleshooting. Queued originals upload after confirmation. Start new troubleshooting session is an explicit reset/new-case action, not an entry requirement.

## Slide 5: Architecture of the running prototype

**Purpose:** Show where evidence enters reasoning.

**Exact on-slide text:**

> Architecture of the running prototype
>
> React workspace and FastAPI session API
> Local OCR, catalog matching and confirmation
> OpenAI or Gemini vision for visible observations
> PostgreSQL + pgvector + full-text search + Reciprocal Rank Fusion
> Evidence review, conflict check, candidate generation and cited-claim verification
> Confidence, source viewer and persistent follow-up

**Recommended screenshot/visual:** Simple architecture diagram using these labels. Show local image storage and PostgreSQL session records. Route follow-up back to contextual retrieval, not OCR or vision.

**Speaker notes:** Local embeddings support semantic retrieval. Exact terms supplement it through PostgreSQL full-text search. OpenAI currently supplies text reasoning. Vision provider selection is explicit, not automatic failover. This is a local prototype, not an offline-only or production multi-tenant service.

## Slide 6: A citation must support the actual claim

**Purpose:** Explain a concrete verifier safeguard and its limits.

**Exact on-slide text:**

> A citation must support the actual claim
>
> SUPPORTED: retain the statement
> PARTIAL: narrow it and verify again
> UNSUPPORTED: remove it or abstain
>
> An observed corrosion-to-STO inference lacked cited support.
> The corrected verifier removed that causal link on live recheck.

**Recommended screenshot/visual:** Editorial before/after text comparison labeled “Historical error” and “Corrected recheck,” based on STEP6-VALIDATION.md. Do not portray it as a UI verifier panel or show raw private audits.

**Speaker notes:** The initial verifier accepted a link between corrosion and STO continuity without explicit manual support. After a targeted fix, a separate live recheck returned PARTIAL, removed the link and verified narrower wording as SUPPORTED. This demonstrates a useful safeguard and a real observed failure, not guaranteed correctness. Failed primary support permits one retry, then LOW abstention if still unsupported.

## Slide 7: Live prototype: ACS880 fault 5091

**Purpose:** Demonstrate the actual end-to-end path.

**Exact on-slide text:**

> Live prototype: ACS880 fault 5091
>
> Confirm ACS880-01
> Run “Drive shows fault 5091”
> Review the suspected STO signal interruption direction
> Open the citation around physical PDF page 525
> Add a follow-up in the same session
>
> Rehearsed result: MEDIUM confidence

**Recommended screenshot/visual:** Switch to the live app. Keep a labeled recorded result screenshot available as backup.

**Speaker notes:** Follow the companion script. MEDIUM is the validated outcome, not a forced setting or guaranteed live result. The manual association does not prove a physical root cause. Do not suggest bypassing STO. Announce any switch to replay, whose provenance includes a documented output-role guard replay.

## Slide 8: What we validated

**Purpose:** Separate regression tests from limited live observations.

**Exact on-slide text:**

> What we validated
>
> 142 backend tests · 4 frontend unit tests · 21 browser tests
> Production frontend build passed
>
> Live ACS880 5091, exact citation viewer and same-session follow-up
> LOW-confidence abstention with weak evidence
> Multi-photo workflow and image-linked visible findings
>
> Prototype validation, not a field-accuracy benchmark

**Recommended screenshot/visual:** Compact table separating “Regression” and “Live scenarios.” No invented accuracy percentage or chart.

**Speaker notes:** These are existing completed Step 6 records and the supplied final baseline, not tests rerun while preparing this outline. The historical audit's 14 browser tests predate seven first-use regressions. Failure cases use deterministic fixtures. Photo evaluation is qualitative; generic images do not prove ABB identity.

## Slide 9: Uncertainty remains visible

**Purpose:** Make limitations explicit.

**Exact on-slide text:**

> Uncertainty remains visible
>
> HIGH / MEDIUM / LOW describe evidence strength
> Weak evidence prompts a useful question
> Conflicting applicability requires clarification
> Photos describe visible conditions only
>
> Small catalog and corpus. Local supervised prototype.

**Recommended screenshot/visual:** A labeled LOW result. If using the motor replay, retain “Temporary motor-family fixture for reasoning validation only.” in full.

**Speaker notes:** Identification supports ACS880-01, ACS580-01 and ACH580-01. The corpus has ACS880 firmware and motor/generator manuals, not matching ACS580/ACH580 manuals. Motor identification is unsupported. The historical motor fixture stopped at weak relevance before candidate generation and verification. We do not claim calibrated fault probabilities, production security or safety certification.

## Slide 10: The next validation step

**Purpose:** Close with credible future work.

**Exact on-slide text:**

> The next validation step
>
> Broaden model- and revision-specific ABB coverage
> Evaluate technician cases with expert reviewers
> Measure unsupported claims, useful next checks and time to evidence
> Add deployment security and data-governance controls
>
> FieldTrace keeps the technician, the equipment and the evidence connected.

**Recommended screenshot/visual:** Restrained closing typography with red emphasis. No speculative product mockup presented as built functionality.

**Speaker notes:** These are proposed next steps, not completed features or measured benefits. Our ask is access to representative cases and expert feedback. The current deliverable is a supervised prototype with inspectable sources and a disclosed replay fallback.

## Evidence and production notes

Reference [README](../README.md), [Step 6 audit](../STEP6-VALIDATION.md), [Step 4 pipeline](../STEP4.md), [Step 5 UI](../STEP5.md) and [replay provenance](../frontend/public/REPLAY-PROVENANCE.md).
Existing screenshots are described under `data/evaluation/ui/step6-fixed/` in the audit. They are ignored local artifacts and may not exist on another checkout. Inspect before use and retain replay/fixture labels. The source viewer shows exact extracted text and an external page link, not an embedded PDF or invented highlights. Do not equate test totals with diagnostic accuracy.
