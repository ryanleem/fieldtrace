# Contributing

Start from an up-to-date `main` and create a short, descriptive branch, for example
`frontend-ui`, `source-viewer`, `demo-testing` or `fix/upload-status`. Do not work
directly on `main`.

Keep each pull request focused. Explain the problem, the change, how it was tested,
and any limits. Include screenshots for UI changes. Avoid unrelated refactors,
especially in the validated retrieval, identification, vision and troubleshooting
services. Coordinate changes to shared API contracts with the integration owner.

Before requesting review, run the full backend suite with the local database and
corpus, plus frontend build, unit and browser tests as described in README. Report
skipped or failed tests honestly. Automated tests mock paid providers; live evaluation
is opt-in and should not use a teammate's personal key.

Never commit `.env`, API keys, tokens, database dumps, uploaded inspection photos,
or local provider audits. Review `git diff --cached` and run
`python scripts/check_repository.py` before committing. The scanner is a heuristic,
not a guarantee. Keep `.env.example` limited to placeholders and public defaults.
If a key is exposed, revoke/rotate it; deleting it in a later commit is insufficient.

Update README and configuration examples whenever setup changes. Keep `main` working,
request another teammate's review, address feedback, and merge only after approval
and passing tests. Do not force-push shared branches. Branch protection should be
configured by the repository owner where the account plan permits it.
