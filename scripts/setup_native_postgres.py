"""Optional Windows-only, project-local database. Docker Compose is preferred.

EDB PostgreSQL distribution plus a checksum-pinned community Windows pgvector
build. No services, system installation, or changes to existing databases.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import zipfile
import tempfile
from contextlib import contextmanager

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work/native-postgres"
PG_URL = "https://get.enterprisedb.com/postgresql/postgresql-17.11-3-windows-x64-binaries.zip"
VECTOR_URL = "https://github.com/andreiramani/pgvector_pgsql_windows/releases/download/0.8.6_17/vector.v0.8.6-pg17.zip"
VECTOR_SHA = "420388e9e9f05d92f06d6967ce8772483629b27a66ca9255925fa0fdd445438e"


def configured_password():
    # Read only this setting; do not load or modify provider-key environment variables.
    password = os.environ.get('POSTGRES_PASSWORD')
    if password is None:
        password = dotenv_values(ROOT / '.env').get('POSTGRES_PASSWORD')
    if not password or password == 'REPLACE_WITH_LOCAL_DB_PASSWORD':
        raise ValueError('Set POSTGRES_PASSWORD in your private .env or environment before native database setup')
    if any(char in password for char in ('\r', '\n', '\x00')):
        raise ValueError('POSTGRES_PASSWORD must not contain line breaks or null characters')
    return password


@contextmanager
def initialization_password_file(password, directory):
    # initdb requires a file; create a unique temporary file and remove it on failure too.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='init-password-',
                                     suffix='.txt', dir=directory, delete=False) as handle:
        path = Path(handle.name)
    try:
        path.write_text(password + '\n', encoding='utf-8')
        yield path
    finally:
        path.unlink(missing_ok=True)


def download(url, name):
    path = WORK / name
    if not path.exists():
        print(f"Downloading {url}", flush=True)
        with httpx.stream("GET", url, follow_redirects=True, timeout=180) as response:
            response.raise_for_status()
            with path.with_suffix(".part").open("wb") as output:
                for block in response.iter_bytes():
                    output.write(block)
        path.with_suffix(".part").replace(path)
    return path


def main():
    if os.name != "nt":
        raise SystemExit("Use docker compose up -d --wait on this platform")
    password = configured_password()
    WORK.mkdir(parents=True, exist_ok=True)
    pg = download(PG_URL, "postgres.zip")
    vector = download(VECTOR_URL, "vector.zip")
    digest = hashlib.sha256(vector.read_bytes()).hexdigest()
    if digest != VECTOR_SHA:
        raise ValueError("pgvector archive checksum mismatch")
    if not (WORK / "pgsql/bin/pg_ctl.exe").exists():
        with zipfile.ZipFile(pg) as archive:
            for name in archive.namelist():
                if name.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
                    archive.extract(name, WORK)
    with zipfile.ZipFile(vector) as archive:
        for name in archive.namelist():
            leaf = Path(name).name
            if leaf == "vector.dll":
                target = WORK / "pgsql/lib" / leaf
            elif leaf.startswith("vector") and leaf.endswith((".sql", ".control")):
                target = WORK / "pgsql/share/extension" / leaf
            else:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    (WORK / "downloads.json").write_text(json.dumps({
        "postgres": {"url": PG_URL, "sha256": hashlib.sha256(pg.read_bytes()).hexdigest(),
                     "checksum_note": "Observed download hash, not publisher-verified"},
        "pgvector": {"url": VECTOR_URL, "sha256": digest,
                     "checksum_note": "Verified against GitHub release asset digest"},
    }, indent=2))
    binary = WORK / "pgsql/bin"
    data = WORK / "data"
    env = dict(os.environ, PGPASSWORD=password)
    flags = subprocess.CREATE_NO_WINDOW
    def run(*args, check=True):
        result = subprocess.run([str(binary / args[0]), *map(str, args[1:])],
                                env=env, capture_output=True, text=True, creationflags=flags)
        print(result.stdout + result.stderr, end="", flush=True)
        if check:
            result.check_returncode()
        return result
    if not (data / "PG_VERSION").exists():
        with initialization_password_file(password, WORK) as pwfile:
            run("initdb.exe", "-D", data, "-U", "guardian", "--encoding=UTF8",
                "--locale=C", "--auth=scram-sha-256", "--pwfile", pwfile)
    if run("pg_ctl.exe", "-D", data, "status", check=False).returncode != 0:
        start = run("pg_ctl.exe", "-D", data, "-l", WORK / "postgres.log",
                    "-o", "-p 55432 -h 127.0.0.1", "-w", "start", check=False)
        if start.returncode and "restricted token" in start.stderr:
            # pg_ctl cannot nest restricted Windows tokens in some sandboxes.
            # Run the standard server directly, under the same existing sandbox/user.
            with (WORK / "postgres.log").open("ab") as log:
                subprocess.Popen([str(binary / "postgres.exe"), "-D", str(data),
                                  "-p", "55432", "-h", "127.0.0.1"],
                                 stdout=log, stderr=log, env=env, creationflags=flags)
            for _ in range(15):
                ready = run("pg_isready.exe", "-h", "127.0.0.1", "-p", "55432", check=False)
                if ready.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("PostgreSQL did not start; inspect work/native-postgres/postgres.log")
        elif start.returncode:
            start.check_returncode()
    import psycopg
    with psycopg.connect(host='127.0.0.1', port=55432, user='guardian',
                        password=password, dbname='postgres', autocommit=True) as connection:
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname='guardian'").fetchone():
            connection.execute("CREATE DATABASE guardian")
    print("PostgreSQL ready on 127.0.0.1:55432", flush=True)


if __name__ == "__main__":
    main()
