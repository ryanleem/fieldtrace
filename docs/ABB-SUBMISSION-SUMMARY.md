# FieldTrace: ABB Prototype Phase submission summary

## Problem

Industrial troubleshooting requires more than locating a manual passage. Technicians must connect the equipment model, visible condition, symptoms and previous checks to applicable documentation, then decide whether the evidence supports the next step.

## Solution

FieldTrace is a working local multimodal troubleshooting prototype. Technicians can immediately enter a model or symptom and queue equipment photos. The app creates a session when backend interaction is needed. OCR and catalog matching assist identification, the technician confirms the model, and vision extracts visible conditions. Troubleshooting returns suspected causes, documented checks, questions and exact ABB citations, or requests more information when evidence is insufficient.

## Differentiator

FieldTrace starts with the equipment in front of the technician rather than a PDF query alone. Confirmed identity, image-linked observations, exact fault codes and persistent case history shape retrieval. The workflow checks technical claims against cited passages and carries follow-up answers into the same investigation.

## Architecture

A React/Vite/TypeScript workspace uses FastAPI. Local OCR supports nameplate reading. Local embeddings, PostgreSQL/pgvector semantic search and PostgreSQL full-text search feed Reciprocal Rank Fusion. OpenAI or Gemini supplies the selected vision adapter; OpenAI supplies text reasoning. The pipeline performs contextual retrieval, relevance review, conflict/applicability checks, candidate generation, cited-claim verification, confidence assignment and response assembly. PostgreSQL stores sessions and evidence records; uploaded images use local file storage.

## Responsible AI and grounding

Photos describe visible conditions, not hidden mechanical or electrical failures. User notes remain separate from AI observations. Technical statements require support in their explicitly cited retrieved evidence. PARTIAL statements are narrowed and rechecked; unsupported statements are removed. Failed primary support permits one retrieval/regeneration retry, then abstention if support remains insufficient. HIGH, MEDIUM and LOW are evidence-policy labels, not calibrated fault probabilities.

Step 6 exposed an unsupported corrosion-to-STO causal link. A targeted verifier fix and live recheck removed that link and verified narrower wording. The verifier reduces risk but remains fallible. Technician review is necessary.

## Validation

The completed Step 6 baseline is 142 backend tests, four frontend unit tests and 21 browser tests, with a successful production build. Recorded live validation covers ACS880 fault 5091, a MEDIUM suspected STO interruption direction, the exact firmware-manual citation around physical PDF page 525, same-session follow-up, LOW abstention on vague input and visible-condition data flow. Multi-photo and failure paths also have deterministic regression coverage. These are existing records, not new runs for submission preparation.

A labeled replay supplies backup. Generic reference photographs and the temporary motor-family reasoning fixture have explicit disclosures. This is prototype qualitative validation, not a statistically meaningful diagnostic or field-accuracy benchmark.

## Limitations

Identification supports ACS880-01, ACS580-01 and ACH580-01. The corpus contains the ACS880 Primary Control Program Firmware Manual (revision V) and Manual for Induction Motors and Generators (revision L). Motor model identification and matching ACS580/ACH580 troubleshooting manuals are not included. The typed-model Step 6 demo did not newly establish field-nameplate OCR robustness. General engineering-drawing or wiring-diagram comprehension is not validated.

The prototype is local and single-user, with external provider latency, cost and availability dependencies. It lacks production authentication, tenant isolation and automated retention controls. It is not production-ready or a safety certification, and has no measured downtime reduction or diagnostic accuracy percentage.

## Future work

Extend model/revision-specific manuals and identification coverage. Evaluate representative technician cases with domain experts, including misleading photos and conflicting evidence. Measure useful next checks, unsupported-claim rates and time to inspect evidence. Develop access control, retention policy and secure deployment before multi-user or field use. These are proposals, not delivered features.

## Supporting material

[Presentation outline](ABB-PROTOTYPE-DECK.md), [demo script](ABB-DEMO-SCRIPT.md), [judge Q&A](ABB-QA.md), [Step 6 validation](../STEP6-VALIDATION.md), [manual manifest](../data/manuals/manifest.json) and [README](../README.md).
