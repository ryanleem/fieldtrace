# Pre-demo checklist

- [ ] Local database running; port 55432 available to the backend.
- [ ] Backend running on 8000; `Invoke-RestMethod http://127.0.0.1:8000/health` succeeds.
- [ ] Both ABB manuals ingested; current embedding configuration matches the corpus.
- [ ] Live frontend on 5173; header says LOCAL WORKSPACE.
- [ ] OpenAI key configured and account funded; don't display the key or .env.
- [ ] Correct vision provider selected; its key is available.
- [ ] Test image `frontend/public/replay-photo-01.jpg` available with provenance.
- [ ] Generic-photo and temporary-motor-fixture disclosures ready; no motor added to catalog.
- [ ] Start a new primary session; no old symptom, photos, result or measurement draft.
- [ ] Rehearse ACS880-01 / fault 5091 and check MEDIUM with real citations.
- [ ] Open the exact page 525 excerpt and check original manual link before judging.
- [ ] Submit one follow-up and confirm the session continues without photo processing.
- [ ] Replay running separately on 5174; ACS880, motor LOW and photo cases all open.
- [ ] Replay source viewer and Reset demo checked; zero live API requests in its audit.
- [ ] Backup walkthrough `.webm` in `data/evaluation/ui/step6/` opens locally.
      This is a short automated recorded-replay walkthrough, not a narrated live demo.
- [ ] Browser window approximately 1440×1050, zoom 100%; no DevTools/debug console.
- [ ] No terminal, API key, private .env or raw provider audit visible to judges.
- [ ] Timed rehearsal fits 4–5 minutes; narrate evidence while live calls run.

## 60-second emergency procedure

1. **0–10 seconds:** Stop repeated clicks. Read the error. Your session stays saved;
   a timeout may still be running. Refresh session status before retrying.
2. **10–20 seconds:** If the backend/database is reachable and the failure is transient,
   retry once. Don't change model prompts or inputs to manufacture a better answer.
3. **20–40 seconds:** If unresolved, say “I'll show the previously validated recorded
   run.” Switch to the already-open replay tab at 5174. Verify the replay banner.
4. **40–60 seconds:** Select ACS880 fault 5091, open the source, then show the motor
   LOW case. If the frontend itself is unavailable, open the labeled backup video or
   screenshots. Never describe these as fresh inference.

After the presentation, record the failure and inspect logs privately. Do not delete
the database, reingest manuals, reset API keys or expose secrets as an emergency fix.
