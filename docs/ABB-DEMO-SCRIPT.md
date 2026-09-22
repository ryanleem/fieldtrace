# FieldTrace presenter script: 4–5 minutes

Use the [launch instructions](../DEMO.md) and [checklist](../DEMO-CHECKLIST.md).
Target 4:45 including normal waits. If a live call is slow, use disclosed replay.
No live calls are required merely to prepare these materials.

## Before the timer

Have live mode at port 5173 and replay at 5174 open separately. Live must say LOCAL WORKSPACE. Use a fresh browser tab/session with no old case. If a previous session restores, click **Start new troubleshooting session** once before presenting to clear it. That is reset preparation, not a prerequisite to typing or selecting photos on a fresh page.

Use typed `ABB ACS880-01` for the reliable main demo path. A genuine readable nameplate may be used if available; typed identification does not validate field-photo OCR. Keep the generic connector example for the separate visible-evidence replay later.

## 0:00–0:30 — Start with the equipment

**Click/type:** In **Model text, if known**, type `ABB ACS880-01`. In **What problem are you seeing?**, type `Drive shows fault 5091`. Do this before creating a session.

**Say:** “FieldTrace starts with the equipment in front of the technician. I can enter the model and exact fault code straight away. The workspace keeps our observations and documentation together as we investigate.”

**Expected UI:** Both fields accept text. **Add equipment photos** is also immediately usable on a fresh page; no photo is needed for this typed-model case. **Run troubleshooting** stays disabled with “Confirm the equipment model before running troubleshooting.” No result exists yet.

**Fallback:** If the live app cannot load, announce replay immediately. A recorded result does not demonstrate fresh intake; explain that distinction.

## 0:30–1:05 — Detect and confirm equipment

**Click/type:** Click **Detect equipment / read nameplate**, review the ACS880-01 candidate and any warnings, then click **Confirm equipment** for that match.

**Say:** “I am using the typed model for this demonstration. A genuine readable nameplate can also be used. Detect creates the session automatically, and I confirm ACS880-01 before running the documentation check.”

**Expected UI:** Detect creates or reuses one session and preserves the typed model and symptom. The card shows CONFIRMED EQUIPMENT and troubleshooting becomes available. Photo intake remains optional for this case.

**Fallback:** On creation/identification failure, show preserved drafts. Do not select a different model to force success. If a refresh and one reasonable retry cannot resolve a transient failure, use labeled ACS880 replay.

## 1:05–2:00 — Run the documented fault case

**Click/type:** Click **Run troubleshooting** once. While waiting, point to the confirmed model and exact code. Read the actual returned primary suspected cause, confidence and checks.

**Say:** “The app searches ABB manuals using the confirmed equipment and exact fault code. It reviews the evidence, checks applicability, then checks technical statements against their cited passages before displaying the result.”

**Expected UI:** The rehearsed case returned MEDIUM with a suspected STO signal/circuit interruption direction. Read only checks that actually appear. Do not improvise wiring instructions or suggest bypassing STO.

**Say after a supported result:** “This is a documented direction for investigation. MEDIUM means more checks are needed. It does not prove what failed physically.”

**Fallback:** If LOW appears, acknowledge the missing evidence and its question. For a failed or slow call, say “I'll show our previously validated recorded run,” switch to 5174 and select **ACS880 fault 5091**. Keep the replay banner visible. Explain that this is a labeled replay of a previously validated result, not fresh analysis. The [replay provenance](../frontend/public/REPLAY-PROVENANCE.md) records how the prepared example was assembled. Do not change prompts to force MEDIUM.

## 2:00–2:40 — Inspect the exact citation

**Click/type:** Click the citation chip or Sources row for the 5091 passage around physical PDF page 525. Show **Exact cited chunk**, title, revision and page. Use **Open manual page** if the ABB link is reachable, then return and close the viewer.

**Say:** “This is the exact stored excerpt from the ACS880 firmware manual. We preserve the source page so the technician can check the claim. A relevant-looking citation is not enough; the passage must support the actual statement.”

**Expected UI:** Exact chunk and provenance appear. Physical PDF and printed page numbers can differ. There are no invented highlights or embedded PDF renderer.

**Fallback:** Use **Retry source** once for a transient fetch error. Replay has a saved excerpt without internet; the external ABB page link still requires network access.

## 2:40–3:30 — Continue the same case

**Click/type:** Under **Add more information**, leave Entry type as **Answer / observation / fault code**. In **Update for this session**, type `STO wiring has not yet been checked.` Click **Submit update & check documentation** once.

**Say:** “I am adding what we still do not know. The same session stores this update. Retrieval and claim verification run again using it, without repeating equipment identification or photo analysis.”

**Expected UI:** The same session ID remains. Session activity shows the saved answer and another documentation check. Confidence and citations are recalculated. The validated case stayed MEDIUM; an unchanged cause can be reasonable. Do not promise a changed cause or a more specific question without evidence.

**Fallback:** After a timeout, **Refresh session status** before retrying because processing may still be active. Replay is read-only: do not simulate a live follow-up submission. Show saved history if available, or explain the previously validated behavior and move on.

## 3:30–4:20 — Separately show uncertainty and visible evidence, if time allows

**Click/type:** Announce the switch to replay. Select **Motor uncertainty fixture** and read **Temporary motor-family fixture for reasoning validation only.** Then select **Recorded visible finding** and show its image, view, observation and attribution.

**Say:** “This recorded fixture shows LOW confidence and a request for temperature and operating conditions instead of forcing a diagnosis. Motor identification is not supported in our catalog. This run stopped at weak evidence before generating or verifying a cause.”

**Say for the photo:** “This separate generic connector example shows visible corrosion and discoloration. It does not prove an internal failure or a cause of fault 5091. Visual confidence describes what can be seen.”

**Expected UI:** Replay banner throughout, no primary cause for motor LOW, and image/view association for photo observations. No new provider call occurs. Keep the generic photo attribution visible; its source is documented in [replay provenance](../frontend/public/REPLAY-PROVENANCE.md). This photo does not establish ABB identity.

**Fallback:** Use labeled backup screenshots or replay video. If time is short, show only one example. Optional live photo analysis belongs in a separate clearly labeled controlled session outside the timed main case.

## 4:20–4:45 — Close honestly

**Click/type:** Return to the live result if available, or leave the labeled replay visible.

**Say:** “We validated the ACS880 fault case, exact sources, follow-up and uncertainty behavior, alongside 142 backend, four frontend unit and 21 browser tests. This is a supervised prototype, not production maintenance authority. Next we want expert-reviewed technician cases and broader model-specific documentation.”

## Presenter guardrails

Do not attribute STO interruption to corrosion without explicit cited support. Step 6 found and corrected exactly that verifier gap. Do not claim that all hallucinations are prevented, every ABB model is supported, or LOW means API failure. Provider failure and weak evidence are separate UI states. Reset creates a new case but does not delete saved backend sessions. Never display keys, private environment files or raw provider audits.
