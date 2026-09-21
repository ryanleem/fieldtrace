# Motor overheating and fan follow-up — live Step 4 validation

**Temporary motor-family fixture for reasoning validation only.**

This validates reasoning orchestration only. It does not establish supported motor identification, a real confirmed motor model, or actual equipment condition. The real catalog remains ACS880-01, ACS580-01 and ACH580-01. The temporary family/session/visual records were confined to an isolated schema, subsequently removed. The reported overheating and dust observation are controlled test inputs; no actual photograph was analyzed.

## Outcome

Two real OpenAI requests succeeded using `gpt-4.1-mini-2025-04-14`, one relevance review per run. Both reviews returned WEAK, so the production pipeline correctly stopped before conflict comparison, candidate generation and claim verification. Both final answers were LOW / insufficient evidence. No technical claim or maintenance recommendation was displayed. This is not a successful end-to-end claim-verification demonstration.

No prompts, model settings, supported catalog entries or production code were changed during this validation. All evidence came through production hybrid retrieval from the real ingested ABB motor manual; no supporting text or page reference was manually inserted. Request/returned models, prompt hashes, full evidence and actual provider responses are preserved in [raw live audit](data/evaluation/step4-live-motor.json).

## Before versus after

| Field | Initial | After “The cooling fan is running.” |
|---|---|---|
| Fixture | Temporary motor-family fixture for reasoning validation only. | Same fixture |
| Session | `500e67a6-fcb2-495c-aacb-d24eddede4f4` | Same session |
| Input revision | 1 | 2 |
| Primary suspected cause | None | None |
| Alternatives | None | None |
| Confidence | LOW | LOW, recalculated through weak-evidence branch |
| Recommended checks | None | None |
| Next question | What temperature was already measured, at which location, and under what operating conditions? | Same question; temperature and conditions remain missing |
| Retrieved evidence | Eight real chunks; useful thermal/cooling passage on p.107 at rank 7 | Eight real chunks; p.107 thermal/cooling passage at rank 1; seven newly retrieved fan-related chunks |
| Review classifications | 4 RELEVANT, 1 PARTIALLY_RELEVANT, 3 NOT_RELEVANT; overall WEAK | 1 RELEVANT, 7 PARTIALLY_RELEVANT; overall WEAK |
| Technical claims / verifier calls | 0 / 0 | 0 / 0 |

The evidence and relevance assessment changed, but the final answer did not. A running fan was not treated as proof of correct airflow, nor was dust treated as proof of an internal fault. The question remains useful but is not a new/adapted question; it does not acknowledge the fan update. The requirement for a newly tailored follow-up question was therefore not demonstrated.

## Follow-up instrumentation

The same session persisted the exact answer in `follow_up_answers`, retained the original symptom and visual input, and incremented its input revision. Retrieval ran once in each invocation, and the follow-up semantic/keyword queries include the running fan. Matching, OCR provider construction, OCR extraction and the vision execution entry point were instrumented to raise if called; their counts were all zero. Existing equipment/OCR state was unchanged in both runs.

Both invocations entered the actual production troubleshooting service. The WEAK-evidence gate intentionally short-circuited stages 4–6; no conflict consistency or verifier support was inferred from this absence. The LOW policy and final-response stages still executed. No unsupported primary was generated, so the one-retry path did not trigger.

## A–K summary

| Item | Result |
|---|---|
| A. Live OpenAI calls | 2 |
| B. API/network failures | 0; both HTTP 200, completed |
| C. SUPPORTED verdicts | 0 — verifier never reached |
| D. PARTIAL verdicts | 0 |
| E. UNSUPPORTED verdicts | 0 |
| F. Claims removed | 0 |
| G. Claims rewritten | 0 |
| H. Follow-up effect | Session/query/evidence changed; final result stayed insufficient evidence / LOW |
| I. OCR/vision/matching | Correctly skipped, instrumented zero calls |
| J. Supervised hackathon readiness | Suitable for showing conservative abstention and stateful retrieval. Not yet demonstrated as a complete motor troubleshooting/claim-verification flow. |
| K. Issues before Step 5 | Improve broad-word retrieval precision, review applicability accuracy, and follow-up specificity; validate stronger evidence and naturally generated claims live. |

No unsupported claim naturally reached the verifier. This run therefore provides **no evidence that the post-claim verifier blocked anything**; the relevance gate prevented candidate generation. No bad claim was injected to manufacture coverage.

## Human assessment and limitations

Abstention is reasonable: the exact model, cooling arrangement, temperature, ambient conditions and measured airflow are unknown. Confirmed family identity in this fixture does not establish whether open-air, air-to-air or air-to-water instructions apply. The retrieved motor manual contains relevant cooling guidance, but it does not prove dust caused this motor’s overheating.

Retrieval precision is uneven. Initially an unrelated bearing-pressure passage ranked first, with hazardous-dust and brush-gear passages also present. The follow-up improved the leading thermal/cooling passage but filled most remaining slots with fan-direction/damage rows across different cooling types. Those are not diagnoses of the inspected fixture.

The relevance model made a specific private-review error: its explanation for the p.97 “Heat source nearby” row described high intake air temperature instead. It also labeled cooling-type-specific rows RELEVANT despite unspecified cooling design. Neither error reached a technician diagnosis because the overall review stayed WEAK. These are live model accuracy/applicability limitations, not proof that deterministic code is broken. No prompt was tuned or product change made to obtain a passing result.

The follow-up reviewer mentioned winding/network information among its missing items. Those were private review suggestions, not findings or final recommendations; the final output contained no internal-failure assertion. No motor operating safety conclusion, replacement recommendation or repair instruction was generated.

No new deterministic implementation bug requiring a targeted fix was established. The generic unchanged follow-up question remains a usability limitation. The new report and temporary evaluation instrumentation are not product features. Step 5 was not started.

## Full per-run evidence and outputs

### 1 motor overheating

**Temporary motor-family fixture for reasoning validation only.**

Input state:

```json
{
  "session_id": "500e67a6-fcb2-495c-aacb-d24eddede4f4",
  "equipment_revision": 1,
  "revision": 1,
  "inputs": {
    "measurements": [],
    "checks_completed": [],
    "ruled_out_causes": [],
    "technician_notes": [],
    "follow_up_answers": [],
    "reported_symptoms": [
      "Motor is overheating."
    ],
    "confirmed_observations": []
  },
  "equipment": {
    "manufacturer": "ABB",
    "model": "induction motor",
    "family": "Induction Motors and Generators"
  },
  "retrieval_filters": {
    "equipment_model": null,
    "equipment_family": "Induction Motors and Generators"
  },
  "ocr_text": "",
  "visual_findings": [
    {
      "aggregated_finding_id": "30f10c44-ebfe-5f7f-ab31-5f33f1c0e7a3",
      "issue_type": "dust_buildup",
      "location": "ventilation/cooling area",
      "description": "Heavy dust buildup near ventilation/cooling area",
      "visual_confidence": "high",
      "supporting_image_ids": [
        "465269c8-0919-47a8-a574-db5e79d25e9f"
      ]
    }
  ],
  "image_user_notes": []
}
```

Contextual and executed semantic queries, exact terms and filters:

```json
{
  "semantic_query": "ABB induction motor Induction Motors and Generators; reported symptoms: Motor is overheating.; visible: Heavy dust buildup near ventilation/cooling area",
  "keyword_queries": [
    "overheating Heavy dust buildup near ventilation/cooling area"
  ],
  "retrieval_filters": {
    "equipment_model": null,
    "equipment_family": "Induction Motors and Generators"
  },
  "exact_keyword_terms": [],
  "filter_covered_terms": [],
  "unsearched_exact_terms": [],
  "executed_semantic_query": "reported symptoms overheating visible Heavy dust buildup near ventilation/cooling area",
  "omitted_semantic_context": [],
  "technical_keyword_queries": []
}
```

Top retrieved chunks (physical PDF pages; raw text is in the JSON audit):

| Rank | Chunk ID | Document / page / section | RRF score | Semantic rank / score | Keyword rank / score |
|---|---|---|---|---|---|
| 1 | 0618a368-81b9-4616-b2d8-b32732c9cafa | [Manual for Induction Motors and Generators, p.103](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=103) — 8. Trouble shooting | 0.01639344 | — / — | 1 / 0.8484849 |
| 2 | addc5f64-19bc-4e90-b6a0-ffb3f81da999 | [Manual for Induction Motors and Generators, p.97](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=97) — 8.1.3.2 Air-to-air cooling system | 0.01639344 | 1 / 0.49515074520404756 | — / — |
| 3 | 1cc7e9ff-e839-406e-b6b5-bce60d7b8924 | [Manual for Induction Motors and Generators, p.97](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=97) — 8.1.3.2 Air-to-air cooling system | 0.01612903 | 2 / 0.481037022943855 | — / — |
| 4 | d02fc01d-95ec-40ba-89a3-33a47784cafd | [Manual for Induction Motors and Generators, p.8](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=8) — Safety instructions — AMA, AMB, AMD, AMG, AMH, AMI, AMK, AMZ, AXR, HXR, M3BM, NMH, NMI, NMK, NXR | 0.01612903 | — / — | 2 / 0.7619048 |
| 5 | 13d38293-42ab-43f2-a370-906f64db6061 | [Manual for Induction Motors and Generators, p.88](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=88) — 7.7.2 Care of brush gear | 0.01587302 | — / — | 3 / 0.7368421 |
| 6 | 8fbb2220-e79b-48a0-ac80-941bcc39ee57 | [Manual for Induction Motors and Generators, p.96](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=96) — 8.1.3.1 Open air cooling system | 0.01587302 | 3 / 0.4687113184504923 | — / — |
| 7 | 06ed4387-663c-4982-aaea-5191144e0c70 | [Manual for Induction Motors and Generators, p.107](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=107) — 8.5 Thermal performance and cooling system | 0.01562500 | 4 / 0.4590807879519001 | — / — |
| 8 | 31621177-482e-412c-822c-e374a0b144e0 | [Manual for Induction Motors and Generators, p.103](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=103) — 8. Trouble shooting | 0.01562500 | — / — | 4 / 0.7368421 |

Actual relevance classifications and explanations (unverified model review, not technician advice):

```json
{
  "chunks": [
    {
      "issue": "pressure_measurement",
      "reason": "Discusses bearing pressure measurements and leakage but does not address overheating or cooling problems.",
      "chunk_id": "0618a368-81b9-4616-b2d8-b32732c9cafa",
      "relevance": "NOT_RELEVANT"
    },
    {
      "issue": "cooling_air_temperature",
      "reason": "Mentions that high intake air temperature can cause malfunctions and suggests ventilation to decrease ambient temperature, relevant to motor overheating.",
      "chunk_id": "addc5f64-19bc-4e90-b6a0-ffb3f81da999",
      "relevance": "RELEVANT"
    },
    {
      "issue": "cooling_air_temperature",
      "reason": "Identifies high intake air temperature due to high ambient temperature as a possible cause and suggests adding ventilation, directly applicable for overheating issues.",
      "chunk_id": "1cc7e9ff-e839-406e-b6b5-bce60d7b8924",
      "relevance": "RELEVANT"
    },
    {
      "issue": "hazardous_area_information",
      "reason": "Safety instructions about explosive atmospheres unrelated to motor overheating or cooling.",
      "chunk_id": "d02fc01d-95ec-40ba-89a3-33a47784cafd",
      "relevance": "NOT_RELEVANT"
    },
    {
      "issue": "cooling_air_circulation",
      "reason": "Discusses cleaning brush gear to remove dust which could affect insulation but no direct link to motor overheating or cooling system effectiveness.",
      "chunk_id": "13d38293-42ab-43f2-a370-906f64db6061",
      "relevance": "PARTIALLY_RELEVANT"
    },
    {
      "issue": "cooling_air_circulation",
      "reason": "Lists heat source nearby as a cause for malfunction and suggests placing heat sources away and checking ventilation, relevant for overheating.",
      "chunk_id": "8fbb2220-e79b-48a0-ac80-941bcc39ee57",
      "relevance": "RELEVANT"
    },
    {
      "issue": "cooling_system_maintenance",
      "reason": "Details thermal performance and cooling system checks, including cleaning and checking heat exchanger and air circulation, directly relevant for motor overheating.",
      "chunk_id": "06ed4387-663c-4982-aaea-5191144e0c70",
      "relevance": "RELEVANT"
    },
    {
      "issue": "pressure_measurement",
      "reason": "Continuation of pressure measurement discussion unrelated to overheating or cooling problems.",
      "chunk_id": "31621177-482e-412c-822c-e374a0b144e0",
      "relevance": "NOT_RELEVANT"
    }
  ],
  "strength": "WEAK",
  "missing_information": [
    "Specific model and cooling type of the motor",
    "Actual ambient temperature and ventilation conditions",
    "Condition and cleanliness of the cooling system and heat exchanger",
    "Detailed inspection results of internal cooling air circulation pathways",
    "Measurements of winding or bearing temperatures",
    "Presence and condition of any heat sources near the motor",
    "Status and operation of motor cooling fans or external blowers",
    "Any prior maintenance or faults related to motor cooling system"
  ]
}
```

Conflict classification: **not run**, due to WEAK evidence. An empty conflict list is not a CONSISTENT verdict.

Candidate primary cause: **not generated**. Alternative causes: **not generated**. Generated technical claims: **none**.

Verifier results for every claim: **none**, because no claims were generated. Removed or rewritten claims: **none**.

Final confidence and complete technician-facing answer:

```json
{
  "status": "insufficient_evidence",
  "message": "The available evidence is insufficient to support a suspected cause.",
  "sources": [],
  "conflicts": [],
  "confidence": "LOW",
  "next_question": "What temperature was already measured, at which location, and under what operating conditions?",
  "primary_cause": null,
  "technical_claims": [],
  "alternative_causes": [],
  "missing_information": [],
  "recommended_actions": []
}
```

Instrumentation:

```json
{
  "retrieval_calls": 1,
  "ocr_factory_calls": 0,
  "ocr_extractions": 0,
  "vision_calls": 0,
  "matching_calls": 0,
  "equipment_and_ocr_state_unchanged": true
}
```

### 1 follow-up fan running

**Temporary motor-family fixture for reasoning validation only.**

Input state:

```json
{
  "session_id": "500e67a6-fcb2-495c-aacb-d24eddede4f4",
  "equipment_revision": 1,
  "revision": 2,
  "inputs": {
    "measurements": [],
    "checks_completed": [],
    "ruled_out_causes": [],
    "technician_notes": [],
    "follow_up_answers": [
      "The cooling fan is running."
    ],
    "reported_symptoms": [
      "Motor is overheating."
    ],
    "confirmed_observations": []
  },
  "equipment": {
    "manufacturer": "ABB",
    "model": "induction motor",
    "family": "Induction Motors and Generators"
  },
  "retrieval_filters": {
    "equipment_model": null,
    "equipment_family": "Induction Motors and Generators"
  },
  "ocr_text": "",
  "visual_findings": [
    {
      "aggregated_finding_id": "30f10c44-ebfe-5f7f-ab31-5f33f1c0e7a3",
      "issue_type": "dust_buildup",
      "location": "ventilation/cooling area",
      "description": "Heavy dust buildup near ventilation/cooling area",
      "visual_confidence": "high",
      "supporting_image_ids": [
        "465269c8-0919-47a8-a574-db5e79d25e9f"
      ]
    }
  ],
  "image_user_notes": []
}
```

Contextual and executed semantic queries, exact terms and filters:

```json
{
  "semantic_query": "ABB induction motor Induction Motors and Generators; reported symptoms: Motor is overheating.; follow up answers: The cooling fan is running.; visible: Heavy dust buildup near ventilation/cooling area",
  "keyword_queries": [
    "overheating cooling fan running Heavy dust buildup near ventilation/cooling area"
  ],
  "retrieval_filters": {
    "equipment_model": null,
    "equipment_family": "Induction Motors and Generators"
  },
  "exact_keyword_terms": [],
  "filter_covered_terms": [],
  "unsearched_exact_terms": [],
  "executed_semantic_query": "reported symptoms overheating follow up answers cooling fan running visible Heavy dust buildup near ventilation/cooling area",
  "omitted_semantic_context": [],
  "technical_keyword_queries": []
}
```

Top retrieved chunks (physical PDF pages; raw text is in the JSON audit):

| Rank | Chunk ID | Document / page / section | RRF score | Semantic rank / score | Keyword rank / score |
|---|---|---|---|---|---|
| 1 | 06ed4387-663c-4982-aaea-5191144e0c70 | [Manual for Induction Motors and Generators, p.107](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=107) — 8.5 Thermal performance and cooling system | 0.03047795 | 1 / 0.526675399938178 | 11 / 0.7916667 |
| 2 | d99ac06b-154a-4cb9-8976-00cd39310f3d | [Manual for Induction Motors and Generators, p.97](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=97) — 8.1.3.2 Air-to-air cooling system | 0.02964427 | 6 / 0.4901402744609056 | 9 / 0.8 |
| 3 | b619b2c2-a122-4471-9d7b-b6d5c3438484 | [Manual for Induction Motors and Generators, p.96](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=96) — 8.1.3.1 Open air cooling system | 0.02913851 | 14 / 0.450446492380322 | 4 / 0.8333333 |
| 4 | b8e7f326-7b47-4a55-9ffd-6489cfde3962 | [Manual for Induction Motors and Generators, p.97](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=97) — 8.1.3.2 Air-to-air cooling system | 0.02862400 | 7 / 0.48912561069421634 | 13 / 0.7826087 |
| 5 | e269a462-843a-4547-8525-f1eb4aa0f660 | [Manual for Induction Motors and Generators, p.97](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=97) — 8.1.3.2 Air-to-air cooling system | 0.02853124 | 3 / 0.5004386603570792 | 19 / 0.7619048 |
| 6 | 075f5228-d0bb-4933-b9f0-4ae03c5a7358 | [Manual for Induction Motors and Generators, p.97](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=97) — 8.1.3.2 Air-to-air cooling system | 0.02803922 | 8 / 0.4847754565282849 | 15 / 0.7619048 |
| 7 | ce34efe3-cc44-40a6-a438-264348ffe2ae | [Manual for Induction Motors and Generators, p.96](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=96) — 8.1.3.1 Open air cooling system | 0.02800627 | 9 / 0.47508689909655544 | 14 / 0.7826087 |
| 8 | e02173e0-f748-49e0-af97-231a65c6909e | [Manual for Induction Motors and Generators, p.98](https://library.e.abb.com/public/361cc64cff8a4f739368f3e88d72588a/Manual%20for%20Induction%20Motors%20and%20Generators_EN.pdf#page=98) — 8.1.3.3 Air-to-water cooling system | 0.02678571 | 20 / 0.43960452799743077 | 10 / 0.8 |

Actual relevance classifications and explanations (unverified model review, not technician advice):

```json
{
  "chunks": [
    {
      "issue": "cooling_system_overheating",
      "reason": "Provides detailed temperature issues linked to cooling system checks and cleaning, applicable to motor overheating with fan running.",
      "chunk_id": "06ed4387-663c-4982-aaea-5191144e0c70",
      "relevance": "RELEVANT"
    },
    {
      "issue": "cooling_fan_issues",
      "reason": "Mentions damaged cooling fans causing low cooling circuit performance but not directly about overheating or dust buildup.",
      "chunk_id": "d99ac06b-154a-4cb9-8976-00cd39310f3d",
      "relevance": "PARTIALLY_RELEVANT"
    },
    {
      "issue": "cooling_fan_issues",
      "reason": "Addresses incorrect fan rotation as a cause for cooling malfunction, relevant to cooling but user reports fan running.",
      "chunk_id": "b619b2c2-a122-4471-9d7b-b6d5c3438484",
      "relevance": "PARTIALLY_RELEVANT"
    },
    {
      "issue": "cooling_fan_issues",
      "reason": "Similar to above on damaged external fans causing low cooling performance, related to cooling problems.",
      "chunk_id": "b8e7f326-7b47-4a55-9ffd-6489cfde3962",
      "relevance": "PARTIALLY_RELEVANT"
    },
    {
      "issue": "cooling_fan_issues",
      "reason": "Notes fan rotating in wrong direction as a cause for malfunction; related but does not address dust or fan running state.",
      "chunk_id": "e269a462-843a-4547-8525-f1eb4aa0f660",
      "relevance": "PARTIALLY_RELEVANT"
    },
    {
      "issue": "cooling_fan_issues",
      "reason": "Mentions corrective action if fan rotates in wrong direction, relevant only for fan direction issues.",
      "chunk_id": "075f5228-d0bb-4933-b9f0-4ae03c5a7358",
      "relevance": "PARTIALLY_RELEVANT"
    },
    {
      "issue": "cooling_fan_issues",
      "reason": "States replacing damaged cooling fans, related to cooling issues but no direct link to motor overheating with fan running.",
      "chunk_id": "ce34efe3-cc44-40a6-a438-264348ffe2ae",
      "relevance": "PARTIALLY_RELEVANT"
    },
    {
      "issue": "cooling_fan_issues",
      "reason": "Deals with low cooling circuit performance caused by damaged fans, indirectly relevant to motor overheating symptom.",
      "chunk_id": "e02173e0-f748-49e0-af97-231a65c6909e",
      "relevance": "PARTIALLY_RELEVANT"
    }
  ],
  "strength": "WEAK",
  "missing_information": [
    "Verification of motor winding condition and network balance",
    "Measurement of winding or cooling air temperature detectors",
    "Details on heat exchanger condition and airflow",
    "Specific identification of dust impact on air circulation inside motor cooling circuit"
  ]
}
```

Conflict classification: **not run**, due to WEAK evidence. An empty conflict list is not a CONSISTENT verdict.

Candidate primary cause: **not generated**. Alternative causes: **not generated**. Generated technical claims: **none**.

Verifier results for every claim: **none**, because no claims were generated. Removed or rewritten claims: **none**.

Final confidence and complete technician-facing answer:

```json
{
  "status": "insufficient_evidence",
  "message": "The available evidence is insufficient to support a suspected cause.",
  "sources": [],
  "conflicts": [],
  "confidence": "LOW",
  "next_question": "What temperature was already measured, at which location, and under what operating conditions?",
  "primary_cause": null,
  "technical_claims": [],
  "alternative_causes": [],
  "missing_information": [],
  "recommended_actions": []
}
```

Instrumentation:

```json
{
  "retrieval_calls": 1,
  "ocr_factory_calls": 0,
  "ocr_extractions": 0,
  "vision_calls": 0,
  "matching_calls": 0,
  "equipment_and_ocr_state_unchanged": true
}
```

## Validation artifacts

- [Raw live calls, evidence and state](data/evaluation/step4-live-motor.json)
- [Machine-readable summary](data/evaluation/step4-live-motor-summary.json)
- [Earlier ACS880/weak-evidence live validation](STEP4-LIVE-VALIDATION.md)

Regression check: `python -m pytest --integration --corpus --basetemp work/pytest-step4-live-motor -q`. Product code was unchanged; see the recorded final result below.

**125 passed**, no skips, in 9.84 seconds. Two existing Starlette/httpx/AnyIO deprecation warnings remain. No Step 1–4 product code was changed; only temporary validation instrumentation and reports were added/updated.
