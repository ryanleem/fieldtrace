# FieldTrace: judge questions and factual answers

Speaking notes for the completed local Steps 1–6 prototype. Use the [submission summary](ABB-SUBMISSION-SUMMARY.md) and [Step 6 audit](../STEP6-VALIDATION.md) for scope and recorded evidence.

## Why isn't this just RAG or chat with PDFs?

RAG is part of the implementation. The distinction is the workflow around it: confirmed equipment, structured photo observations, symptoms and session history shape retrieval. Evidence review and cited-claim verification determine what can be shown. Follow-up continues the investigation rather than starting another isolated manual question. We are not claiming a new foundation model or unique ownership of RAG.

## Why use images?

Nameplate OCR can supply identification text. Other views can show corrosion, discoloration, damaged insulation or debris. Images retain session, equipment, view and image associations; aggregation reduces obvious duplicates across views. Notes remain user reports. No clear visible abnormality does not mean healthy equipment.

## Why not infer internal failures from photographs?

An external view cannot establish winding damage, bearing failure, imbalance or an internal short. FieldTrace separates visible observations from diagnostic hypotheses. A causal link needs supporting documentation and case evidence. The generic connector photo must not be presented as proof of an ACS880 fault or identity.

## How do you prevent hallucinations?

We reduce their likelihood with equipment filtering, real retrieved ABB passages, relevance and applicability review, structured output, cited-claim verification and abstention. Unknown citation IDs are rejected. These checks remain fallible. Step 6 found a verifier accepting an unsupported visual causal link; the fix and live recheck are reported rather than hidden. We do not promise zero hallucinations.

## What does the verifier actually do?

It compares each technical claim only with its explicitly cited retrieved chunks. Cause labels, rationales, actions and question wording also undergo support checks. SUPPORTED wording survives. PARTIAL wording is narrowed and verified again; unsupported rewrites are removed. Failed primary support permits one refined retrieval/regeneration attempt, then LOW abstention if still unsupported. It does not merely count citations. The Step 6 guard also blocks a SUPPORTED verdict whose explanation explicitly admits an evidence gap.

## Why HIGH/MEDIUM/LOW rather than percentages?

We lack a field dataset that calibrates failure probabilities. These are deterministic evidence-policy labels. HIGH requires strong primary relevance, retrieval-channel support, confirmed equipment and no unresolved conflict, missing information, low-confidence visual finding or weakened statement. Other supported directions are MEDIUM. Weak evidence or unsupported primary support yields LOW without a diagnosis. None proves a physical fault.

## What happens when evidence conflicts?

The pipeline compares top evidence within same-issue groups and distinguishes consistent, complementary, conflicting and differently applicable guidance. Unresolved conflicts withhold actions and prompt clarification of model, revision or conditions. The UI links sources instead of silently selecting an instruction. UI handling has deterministic coverage; the earlier real-corpus applicability case did not establish a true contradiction.

## What if identification is uncertain?

The app shows candidates and mismatch warnings and requires confirmation before troubleshooting. On a fresh page, typing and photo selection remain available. Detection creates a session automatically and preserves drafts. An unmatched motor is not silently added to the catalog. Reidentification invalidates the old current answer for the changed identity.

## How much works today?

The local React UI connects to FastAPI, PostgreSQL, real ABB retrieval, configured providers, image storage and persistent session records. ACS880 5091, exact sources and follow-up have recorded live validation. The 142/4/21 baseline covers backend, frontend unit and browser behavior. Replay is a labeled read-only backup, not live processing. No new live calls were run to write these materials.

## What documentation is supported?

The manifest contains two real ABB manuals: ACS880 Primary Control Program Firmware Manual, 3AUA0000085967 revision V, and Manual for Induction Motors and Generators, 3BFP 000 050 R0101 revision L. Metadata preserves document, revision, source and physical PDF page. The catalog has ACS880-01, ACS580-01 and ACH580-01, but the latter two lack matching ingested troubleshooting manuals. Searchable motor documentation does not imply supported motor-model identification.

## Can it understand every scanned manual, table or wiring diagram?

No. Local OCR supports equipment-photo text, and retrieval preserves extracted manual text and provenance. General engineering-drawing, scanned-document and wiring-diagram understanding has not been established. The theme's possible features must not be presented as delivered capabilities.

## What did you validate?

Existing records cover live ACS880 fault 5091, MEDIUM confidence, physical PDF page 525, same-session follow-up, weak-evidence abstention, generic-photo observations and transfer of visual findings into retrieval context. Multi-photo intake and failures also have deterministic tests. The final baseline is 142 backend, four frontend unit and 21 browser tests, plus a successful build. Photo evaluation is qualitative. The motor identity/context is a temporary fixture, not field identification; its LOW result stopped before candidate generation and verification.

## How does follow-up context work?

Answers, measurements and completed checks append to the same backend session. Retrieval uses confirmed identity, existing visual findings and updated inputs, then reviews and verifies new output. The follow-up endpoint does not rerun OCR, matching or vision. A changed diagnosis is not guaranteed if new information does not justify one. The UI exposes saved updates and run history.

## How is technician data handled?

Selected photos begin as browser-local drafts. Confirmed uploads use local files under `data/uploads/{session_id}/`; PostgreSQL stores metadata, notes, findings, sessions and run audits, including provider responses. OCR and embeddings run locally. Vision sends image data and orientation context to the selected OpenAI or Gemini provider. Text reasoning sends contextual information and retrieved excerpts to OpenAI. OpenAI adapters request `store=false`; this alone does not guarantee all aspects of provider retention.

Keys stay in the backend environment. The tab remembers its session ID in sessionStorage. Starting a new case does not delete old backend records. There is no production login, tenant isolation or automatic retention policy. Use authorized demo data until appropriate controls and provider data terms have been reviewed for sensitive plant material.

## What are the biggest limitations?

A small catalog/corpus, limited field-photo and nameplate evaluation, probabilistic verification, sometimes generic questions, provider cost/latency and a synchronous backend. The source viewer shows exact extracted text and a page link, not an embedded PDF with highlights. Production security, offline reasoning and a validated field-safety workflow are not delivered. This is a supervised hackathon prototype.

## How would it scale across ABB equipment?

Curated model/revision metadata, more authorized manuals, broader identification and expert-labeled cases are the next steps. Existing retrieval/provider interfaces are a starting point, but applicability, source quality, latency, security and unsupported-claim rates need evaluation. No knowledge graph, enterprise integration or autonomous maintenance capability is claimed today.

## What happens if a provider fails?

The live app preserves saved inputs and displays an error rather than fabricated findings or a LOW badge pretending successful analysis. Refresh after an ambiguous timeout before retrying. We can switch explicitly to recorded replay. Vision selection is configurable, but the prototype does not silently switch providers or substitute recordings. External manual links still need internet even when replay excerpts work.

## Does it tell an engineer what is safe to operate?

No. It presents suspected causes and documented checks for qualified review. It does not certify health, replace site procedures or justify bypassing Safe Torque Off. Fault 5091 demonstrates a documented STO direction rather than a confirmed physical root cause.

## What would make the next evaluation convincing?

Expert review of representative cases including clean images, ambiguous nameplates, unsupported symptoms, revisions and conflicts. Measure citation support, next-check usefulness, abstention quality and time to evidence. Compare with ordinary manual search before claiming productivity gains.

## Reference map

- [Step 4 pipeline and confidence](../STEP4.md)
- [Step 5 UI and limits](../STEP5.md)
- [Step 6 verifier error and correction](../STEP6-VALIDATION.md)
- [Manual provenance](../data/manuals/manifest.json)
- [Catalog](../data/equipment_catalog.json)
- [Replay provenance and photo attribution](../frontend/public/REPLAY-PROVENANCE.md)
