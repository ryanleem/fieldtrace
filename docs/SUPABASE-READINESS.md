# Supabase readiness review — 2026-09-24

Verdict: proceed to Supabase project setup and a real two-user test in a non-production
environment. Do not deploy the authenticated release yet. This review did not create
accounts, change cloud configuration, run a Railway migration, or call paid providers.
No application code changes were necessary during this review.

## Real project connectivity update — 2026-09-24

Local ignored `.env` and `frontend/.env.local` now contain the supplied public
Supabase configuration. Other values were preserved; the frontend API base remains
local `/api`. No production configuration or main ref was changed.

- Real `/auth/v1/settings`: HTTP 200 using the supplied publishable key.
- Email/password enabled; signup allowed; email confirmation required; anonymous
  sign-in disabled. Confirmation settings were not changed.
- Real JWKS: HTTP 200, one ES256 public signing key. The backend's actual PyJWKClient
  fetched it successfully. This alone does not prove which key signs a new login.
- Actual backend verifier rejected malformed input and a token signed with an
  unrelated test key using the real project's kid: HTTP 401. No tokens were logged.
- Real signup, email delivery/confirmation, login/logout, restoration, refresh, and
  issued-token validation remain **pending two confirmed test accounts**. Expiry,
  issuer, audience, UUID and cross-user checks pass deterministic tests, not yet
  real-account validation. No claim that live token refresh has been validated.
- Owner gates were re-inspected on all session routes, photos, history and sources.
  Live two-user checks remain pending; the earlier positive-control caveat applies.
- No service-role key was requested, used, or required. No paid provider calls.

To unblock: use two email addresses whose inboxes you control. Sign up through the
local auth build and follow the confirmation messages. Keep confirmation enabled.
If email delivery prevents this, in Supabase **Authentication → Users → Add user →
Create new user**, create two test users with distinct addresses and passwords and
select auto-confirm for those individual test users. This enables login tests but
**does not validate the email confirmation flow**. Enter passwords only in the local
login form, never in chat or tracked files. Configure custom SMTP if the project's
sender cannot deliver to those addresses. Verify redirect allowlisting in the
Supabase dashboard; public settings do not disclose it.

Production variables (plan only; not applied):

```dotenv
# Railway backend
SUPABASE_URL=https://kodylgzaqdyaptrdfidn.supabase.co
SUPABASE_JWT_AUDIENCE=authenticated
# Vercel frontend, build-time public configuration
VITE_SUPABASE_URL=https://kodylgzaqdyaptrdfidn.supabase.co
VITE_SUPABASE_ANON_KEY=sb_publishable_sX63bVHCyxnqsA9XgQ51Jg_Pv2VVzj6
```

Safe deployment sequence, after separate approval:

1. Complete real two-user validation locally or in an isolated staging database.
2. Back up Railway Postgres; verify restore access, schema compatibility, and the
   existing corpus. Schedule a quiet migration window. Never reset or re-ingest.
3. Prepare the reviewed backend image and set its auth variables **before it serves
   traffic**. Apply the additive migration from that image as a pre-deploy step:
   `PYTHONPATH=backend python -m app.db.migrate_user_sessions`.
4. Start the reviewed authenticated backend only after migration succeeds. Confirm
   health, unauthenticated rejection and an authenticated positive control. Avoid
   rollback to an anonymous backend after private user data has been created.
5. Build a Vercel preview with the supplied public variables and the reviewed backend
   URL. Explicitly allow its exact origin in Supabase redirects and backend CORS.
   Prefer an isolated staging backend/database for this preview validation.
6. Complete the real two-user checklist on that preview, including existing-resource
   positive controls, refresh/logout, and signed-out replay with no provider calls.
7. Only after success and approval, promote the frontend to production with the final
   origin/redirect settings. A coordinated maintenance window avoids pairing the old
   anonymous frontend with the authenticated backend during rollout.

Migration re-review: additive transaction and advisory lock; ownerless legacy rows
stay ownerless; no tables/data/manuals deleted; index/name constraint and timestamp
triggers retained; repeat invocation covered by local tests. No production migration
was run. Backup/schema preflight remains required.

Validation rerun: **194 backend passed**, **16 frontend unit passed**, **27 browser
passed**, production build passed. Browser tests use mocked Supabase, not real users.
Windows browser-server teardown required stopping only this run's Vite process after
assertions completed; runner then exited successfully. Two existing Python deprecation
warnings remain. Scanner: 15 placeholder/test/HTML-markup review matches, no detected
real secrets, zero files at least 50 MiB. Diff whitespace check passed.

Verdict: public connectivity/configuration ready; **not yet validated for production**.
Only this document and ignored local configuration were changed in this follow-up.
No commit, push, deployment, production migration or application-code change.

## Repository verification

Current branch: `auth-session-history`. HEAD, local main and the local origin/main
reference all resolve to `87519f844374321afd89c75ab14c6e10fdbab4d3`. The auth work is
unstaged/untracked in this checkout; neither main's commit nor any branch ref was
changed by the review. Uncommitted files are not inherently isolated by a Git branch:
do not switch this dirty checkout to main and assume these edits disappear.

Reviewed AUTH-VALIDATION.md, DEPLOYMENT.md, auth.py, migrate_user_sessions.py,
user_sessions.py, frontend auth.ts/AuthShell.tsx, all session routers and their tests.
Corrected stale branch/UUID-access documentation; the implementation remains unchanged.

## Exact Supabase setup

Use Supabase for Auth only. Leave manuals, pgvector, sessions and image metadata in
Railway PostgreSQL, and image files on the Railway volume.

1. Enable email/password sign-in and allow new-user signup for the two-user test.
   Set minimum password length to at least 8 to match the form. Disable anonymous
   sign-in. OAuth, phone auth, MFA and a custom callback server are not required.
2. Use a **current/in-use ES256 or RS256 signing key**. A standby public key alone is
   insufficient: newly issued user tokens must use the asymmetric key. An old project
   still issuing HS256 tokens will be rejected by this backend. No signing secret or
   service-role key is needed. [Supabase signing-key documentation](https://supabase.com/docs/guides/auth/signing-keys).
3. Set Site URL to `https://fieldtrace-blush.vercel.app`.
4. Add these exact Redirect URLs (no wildcard preview domains):
   - `https://fieldtrace-blush.vercel.app`
   - `http://localhost:5173`
   - `http://127.0.0.1:5173`
5. Keep the normal confirmation email link using `{{ .ConfirmationURL }}`. Signup
   passes `emailRedirectTo: window.location.origin`. The installed SDK uses its
   default implicit flow and `detectSessionInUrl: true`, so the app root consumes
   the confirmation result. There is no `/auth/callback` or `/auth/confirm` route to
   register, and the Railway backend URL is not an auth redirect target. Ordinary
   password login does not redirect. Do not copy token-bearing confirmation URLs
   or authorization headers into reports. [Password flow](https://supabase.com/docs/guides/auth/passwords),
   [redirect configuration](https://supabase.com/docs/guides/auth/redirect-urls).
6. **Recommend email confirmation ON**, including the public hackathon demo. Register
   and confirm the presenter/test accounts in advance. For ordinary external user
   email addresses, configure and test custom SMTP: Supabase's default sender only
   delivers to project-team addresses and is unsuitable for arbitrary attendees.
   If delivery cannot be configured, that is a readiness blocker for this recommended
   setup. Confirmation OFF is a possible deliberate compromise for an isolated,
   supervised test project, not proof of email ownership; do not silently disable it.
   [Supabase SMTP restrictions](https://supabase.com/docs/guides/auth/auth-smtp).

The browser test server on port 5175 uses fake Supabase responses and needs no real
redirect registration. Add any different manual development origin explicitly only
if you actually use it. Public replay at `/?demo=true` requires no Supabase login and
makes no live FieldTrace/provider calls.

## Required variables

| Runtime | Variable | Value |
| --- | --- | --- |
| Railway backend | SUPABASE_URL | https://YOUR_PROJECT_REF.supabase.co |
| Railway backend | SUPABASE_JWT_AUDIENCE | authenticated (also the code default) |
| Vercel frontend | VITE_SUPABASE_URL | Same project URL |
| Vercel frontend | VITE_SUPABASE_ANON_KEY | Public publishable key, or legacy public anon key |

Prefer the publishable key for a new project; the existing variable name supports
it. The legacy anon API key and the algorithm signing user access tokens are distinct:
a legacy anon key does not make HS256 user tokens acceptable. No service-role key,
Supabase JWT shared secret or Supabase database password is required anywhere.
Existing provider keys and Railway DATABASE_URL remain server-side. Rebuild the frontend
after configuration. CORS must allow the actual frontend origin plus Authorization
and PATCH (the latter two are already implemented); CORS is not authorization.

## JWT audit

| Check | Result |
| --- | --- |
| Signature | PyJWT verification with ES256/RS256 allowlist; unsigned and wrong signatures rejected |
| Public keys | Fixed configured project HTTPS JWKS URL; kid selects a key; no token-supplied key URL is trusted |
| Cache/outage | JWKS cached 300 seconds; fetch timeout 5 seconds; unavailable key service fails closed with 503 |
| Issuer | Exact SUPABASE_URL + /auth/v1 |
| Audience | SUPABASE_JWT_AUDIENCE, default authenticated |
| Time claims | exp and iat required and validated; nbf validated if present |
| Subject | UUID parsed only after successful signature/claim verification |
| Role | authenticated only; anonymous users rejected |
| Bad input | Missing bearer or invalid/expired/malformed/oversized token returns 401 without echoing it |
| Owner injection | Session payloads forbid extra fields; user_id is exclusively the verified sub |

Authentication is local JWT verification, not a per-request online account lookup.
Deleted/disabled users or logged-out tokens can remain accepted until JWT expiry;
key revocation also depends on public-key caches. No claim of instantaneous revocation.
The browser SDK stores/refreshes tokens; XSS and compromised devices remain risks.

## Ownership / IDOR audit

Every session router has `Depends(session_access)`, which authenticates then calls
`owned_session`. SQL requires both session ID and owner_user_id. Creation/list/metadata/
rename also use explicit owner-scoped service queries. Ownership has no API mutation.

| Resource | Enforcement |
| --- | --- |
| Session fetch/list/rename | Verified owner SQL; list never includes ownerless/other-user rows |
| Equipment identify/confirm/reject/read | Parent owner check before OCR dependencies |
| Photo upload/list/analyze/file | Parent owner check; image must also belong to requested parent; path bounds retained |
| Visible findings/context | Parent owner check |
| Troubleshooting state/symptoms/run/follow-up | Parent owner check before provider dependencies |
| Saved run history | Parent owner check and run.session_id equality |
| Citation/source | Parent owner check, run parent equality, chunk must be a final citation in that run |

Unauthenticated requests return 401; User B with a valid token requesting User A's
resources returns 404, the same as missing resources. Production restrictions may
reject disabled batch/audit endpoints earlier with 403; this is not an ownership
success. Protected successful responses use private/no-store caching. UUID knowledge
alone never grants access in this implementation. Trusted server-side scripts are not
user-facing APIs; no database RLS policy was introduced.

## Railway migration audit and later command

The migration is additive and transactional with an advisory lock. It adds nullable
UUID owner_user_id and text session_name, the owned-name check constraint (1–100,
trimmed, non-null for owned sessions), an owner/updated_at/id history index and five
child-table timestamp triggers. It does not delete rows, drop tables, reset the DB,
change manual/vector tables, re-ingest, or assign legacy ownership. It replaces only
its named timestamp triggers and function on rerun. Existing created_at/updated_at
columns are preserved. Repeat invocation is covered by isolated PostgreSQL tests.

Legacy records remain ownerless and become inaccessible through the authenticated
backend; the migration alone cannot secure an old unauthenticated backend still serving
traffic. Do not roll back to that old backend after private user sessions exist.

**Safe for the expected existing Step 1–4 schema, subject to backup and preflight.**
This review has not re-inspected production schema drift or executed any SQL there.
Before approval, back up and verify all six parent/child tables exist, column types and
existing constraint/index definitions match this release. Apply during a quiet window:
ALTER TABLE, the normal index build and trigger replacement can block active writes.
A drifted object with the same name is not automatically repaired by IF NOT EXISTS.

Later, run this exact command in `/app` inside the **reviewed new Railway backend
image**, using its private DATABASE_URL, before it starts serving authenticated traffic:

```sh
PYTHONPATH=backend python -m app.db.migrate_user_sessions
```

It can be the one-time pre-deploy command for the approved release; the current
railway.json does not automatically run it. It is not usable from the old deployed
image, which lacks the new module. Do not run this against a new empty database before
the existing tables are initialized, or via `railway run` expecting remote execution.
No Railway migration command was executed during this review. Migration tests run only
in disposable local schemas as part of the expressly requested backend suite.

## Real two-user validation checklist (prepared, not yet executed)

Use the authenticated local build and a local database first, with a real Supabase
project. Keep the current production demo untouched. Use two separate browser profiles
or separate normal/private contexts and two real email addresses. Use an API client
that keeps bearer tokens only in local memory and reports status codes, not headers.

### User A

- Sign up, complete email confirmation, log out and log in with password.
- Type model/symptom before creating a case. Click Detect, enter `ACS880 Fault 5091`
  in the name dialog, confirm; verify drafts survived and exactly one case was created.
- Confirm ACS880-01 using typed model text. Save the symptom without a provider run
  through POST /sessions/A/troubleshooting/symptoms when using the API test client.
- Upload an authorized photo using Save photos without analysis. Do not click vision
  or Run troubleshooting during this unpaid auth check.
- Verify My Sessions, rename to `ACS880 Fault 5091 - follow-up`, refresh and reopen.
- Confirm saved equipment/symptom/photo persist, with no OCR, vision or reasoning POST.
- Record only A's session/image IDs and any already-existing A-owned run/citation IDs.
  As A, verify each actual resource being tested returns 200 (positive control).

### User B

- In the separate profile sign up/confirm/log in as B. GET /sessions must exclude A.
- With **B's valid bearer token**, call each route below using A's IDs. Expect 404:
  - GET /sessions/A
  - PATCH /sessions/A with {"session_name":"Unauthorized rename"}
  - GET /sessions/A/equipment
  - GET /sessions/A/images
  - GET /sessions/A/images/A_IMAGE/file
  - GET /sessions/A/visual-findings
  - GET /sessions/A/troubleshooting (includes saved evidence history)
  - GET /sessions/A/troubleshooting/runs/A_RUN
  - GET /sessions/A/troubleshooting/runs/A_RUN/sources/A_CHUNK
- Also test invalid/expired/missing tokens: expect 401. Typing a photo URL into a
  browser address bar normally sends no bearer and only tests 401, not B-vs-A ownership.
- Create B's own named case and confirm B can read it while still unable to list A's.
- Do not run paid provider actions. The automated suite already checks rejection of
  cross-user run/follow-up before any provider dependency executes.

### User A again

- Log out/login in A's profile, verify only A's cases, reopen the renamed case and
  confirm saved state. Check A still gets 200 for its image and B gets 404 for that
  same existing image. Verify no other user's data appears after account switching.
- Preserve the labeled public replay and verify it works signed out without API calls.
- Record method, sanitized resource ID, actor and status. Never save bearer tokens,
  passwords, confirmation fragments or raw HAR files containing credentials.

**Run/citation positive-control caveat:** a newly created unpaid case has no run or
citation. Random child IDs yielding 404 are not proof of isolation of an existing
source. Use an already existing A-owned result, or a separately approved explicitly
labeled fixture in the isolated local/staging database. Do not reassign production
legacy sessions, inject fake live evidence, or call a paid provider to fill the gap.
Keep the real saved-run/source positive-control checks pending until such data exists.

## Validation and release blockers

Backend: 194 passed (including local integration/corpus); frontend unit: 16 passed;
browser: 27 passed; production build passed. Repository scanner: 15 reviewed
placeholder/fixture/markup matches, no detected real credentials or large files.
`git diff --check` passed. Existing Starlette deprecations and Windows test-server
cleanup limitation remain; no application failures or paid calls. Static/mocked tests
are not represented as real Supabase account validation.

Proceed to real Supabase setup: **yes**. Proceed to production deployment: **not yet**.
Outstanding: actual project/key/SMTP configuration, real email confirmation and refresh,
two-user positive/negative checks, production backup/schema preflight, reviewed release
and coordinated migration/backend/frontend rollout. Keep existing rate limits and
provider budgets; signup access can still consume the shared demo budget.

## Final Git status

Branch: `auth-session-history`. All changes remain unstaged/untracked; nothing committed,
pushed or deployed. This review changed only AUTH-VALIDATION.md, DEPLOYMENT.md and
added SUPABASE-READINESS.md. Existing implementation changes are preserved.

```text
 M .env.example
 M README.md
 M backend/app/api/equipment.py
 M backend/app/api/inspection.py
 M backend/app/api/search.py
 M backend/app/api/troubleshooting.py
 M backend/app/api/viewer.py
 M backend/app/config.py
 M backend/app/demo_safety.py
 M backend/app/main.py
 M backend/app/models/equipment.py
 M backend/tests/conftest.py
 M backend/tests/test_api.py
 M backend/tests/test_demo_safety.py
 M backend/tests/test_deployment_config.py
 M backend/tests/test_equipment.py
 M backend/tests/test_troubleshooting.py
 M backend/tests/test_viewer.py
 M backend/tests/test_vision.py
 M docs/DEPLOYMENT.md
 M frontend/.env.example
 M frontend/e2e/workspace.spec.ts
 M frontend/package-lock.json
 M frontend/package.json
 M frontend/playwright.config.ts
 M frontend/src/App.tsx
 M frontend/src/api.ts
 M frontend/src/main.tsx
 M frontend/src/styles.css
 M frontend/src/types.ts
 M frontend/vitest.config.ts
 M requirements.lock.txt
 M requirements.txt
?? backend/app/auth.py
?? backend/app/db/migrate_user_sessions.py
?? backend/app/services/user_sessions.py
?? backend/tests/test_auth_sessions.py
?? docs/AUTH-VALIDATION.md
?? docs/SUPABASE-READINESS.md
?? frontend/e2e/auth-fixture.ts
?? frontend/e2e/auth.spec.ts
?? frontend/src/AuthShell.tsx
?? frontend/src/NameDialog.tsx
?? frontend/src/PrivatePhoto.tsx
?? frontend/src/auth.test.tsx
?? frontend/src/auth.ts
?? frontend/src/sessions.test.tsx
```
