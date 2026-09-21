# Private GitHub handoff

## Local preparation results

No Git repository existed. Initialized `main`; no commit, staging, remote creation,
invitation or push was performed. All deliverable files are currently untracked.

Added: CONTRIBUTING.md, scripts/check_repository.py, this handoff, and
STEP1-2-REFERENCE.md (the previous detailed README).
Updated: README.md, .gitignore, .env.example and docker-compose.yml.
The Compose password must now be explicitly configured. No Step 1–5 application
behavior or supported catalog was changed; the existing local .env was preserved.

README covers architecture, supported documents, independent database setup,
pgvector/schema initialization, ingestion, backend/frontend commands, provider
switching, tests, troubleshooting, team workflow, team split and collaboration safety.
CONTRIBUTING asks for focused branches/PRs, review, testing and setup documentation;
it prohibits committing credentials and unrelated refactors.

## Secret and file review

Scanned tracked/commit-eligible text for provider tokens, private keys, credential
URLs, secret assignments and signed/private URL patterns. Also compared configured
local API key values against candidate files without displaying those values.
No real API token/private key or copy of the configured API keys was detected.
There is no Git history to scan because this is a newly initialized repository.

Heuristic findings were reviewed: placeholder connection strings in documentation
and .env.example, and explicit fake keys in mocked tests. The later pre-commit cleanup
removed the local database password from config.py and native setup. Both now use
POSTGRES_PASSWORD; an explicit DATABASE_URL remains authoritative for the backend.
Existing database credentials are not reset. No exposed real provider key requiring
rotation was found in the candidate source. Scanning is not a guarantee of absence.

Ignore rules exclude .env variants (except examples), key files, venvs, caches,
dependencies, build/test artifacts, database files, uploads, raw provider evaluation
JSON/screenshots, PDFs, logs, IDE and temporary files. No source/configuration examples
are hidden. No files were deleted. Licensed evaluation photos, manifests and the
curated frontend replay are included with provenance.

Candidates total about 4.8 MiB. Largest candidate: data/evaluation/images/photo-07.jpg
(1,401,692 bytes). No candidate reaches 50 MiB. The two excluded ABB PDFs are
5,668,760 and 5,385,048 bytes; download them via the official manifest rather than
including them in Git. Native PostgreSQL, model caches and npm/Python dependencies
stay outside Git. Raw provider audits remain local; old reports may reference those
excluded artifacts. Normal tests and replay do not require them.

Validation after password-configuration cleanup: **139 backend tests passed**, **4 frontend unit tests
passed**, **7 browser tests passed**, and the production frontend build passed.
Backend tests emitted two existing dependency deprecation warnings. Tests used the
existing local PostgreSQL/corpus; this was not a clean Docker installation test.

### Pre-commit database-password cleanup

- `backend/app/config.py`: removed the password-bearing default URL. Builds the
  default connection from POSTGRES_PASSWORD with URL encoding; explicit DATABASE_URL
  still wins. No implicit password remains. Password/URL are omitted from settings repr.
- `scripts/setup_native_postgres.py`: reads POSTGRES_PASSWORD from environment or
  private .env; uses it for PGPASSWORD, initdb and psycopg. Rejects missing/example or
  multiline values. Unique temporary password files are removed even on failure.
- `.env.example`: one required password placeholder; full URL is an optional override.
- Private ignored `.env`: added POSTGRES_PASSWORD using the already-configured database
  credential. Existing entries, database password and both provider keys were unchanged.
- Docker Compose already required POSTGRES_PASSWORD, so no further edit was needed;
  its configuration validation passed. README documents both setup methods.
- `backend/tests/test_database_config.py`: ten tests cover URL precedence, encoding,
  absence of a default password, native configuration and temporary-file cleanup.

Latest scanner: 128 candidate files, no large files. **11 review findings** remain:
two placeholder URLs (.env.example and README); eight fake API-key assignments in
existing provider tests; one generated test .env assignment in test_database_config.py.
The latter writes a freshly generated UUID value, not a hard-coded password.
No provider tokens/private keys were detected. There are no remaining password
literal findings in config.py or native setup. The scanner itself was not weakened
or given exclusions to suppress these results. Nothing was committed or pushed.

## Create and push the private repository yourself

Install GitHub CLI (`gh`) and run these from the project root. Replace YOUR_OWNER
with your GitHub username or organization. These commands have NOT been executed.

```powershell
Set-Location 'C:\Users\rleem\Documents\Codex\2026-09-10\https-www-hackerearth-com-community-challenges\abb-guardian'
.\.venv\Scripts\python.exe scripts/check_repository.py
git status --short
git add .
git diff --cached --stat
git diff --cached
```

Review the staged content before continuing. If Git identity is missing, configure
`git config user.name "Your Name"` and `git config user.email "YOUR_GITHUB_NOREPLY_EMAIL"`.
Use your actual GitHub-provided no-reply address or chosen commit email.

```powershell
git commit -m "Prepare FieldTrace prototype for team collaboration"
gh auth login
gh repo create YOUR_OWNER/fieldtrace --private --source=. --remote=origin
gh repo view YOUR_OWNER/fieldtrace --json nameWithOwner,isPrivate
# Confirm isPrivate is true before the first push.
git push -u origin main
```

The initial main commit establishes the repository; subsequent work belongs on
feature branches and reviewed pull requests. If a remote already exists when you
follow these instructions, inspect it first rather than creating a duplicate.
See the [official gh repo create reference](https://cli.github.com/manual/gh_repo_create).

## Add teammates

For a repository owned by your personal account:

1. Ask teammates for their GitHub usernames.
2. Open the private repository on GitHub, then **Settings**.
3. Under **Access**, choose **Collaborators**, then **Add people**.
4. Select the teammate and click **Add NAME to REPOSITORY**.
5. They accept the invitation, then clone and follow README using their own .env and database.
6. Repeat for each teammate. Keep secrets out of invitations, issues and PRs.

These steps follow [GitHub's collaborator guide](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository).
Organization repositories use organization/team access controls instead. Configure
main-branch PR/review protections where your account plan supports them; no remote
settings or protections were configured by this local task.
