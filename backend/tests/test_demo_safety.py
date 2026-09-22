"""Public boundary tests with in-process fake endpoints; no paid calls."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import Settings
from app.demo_safety import DemoSafetyMiddleware, configure_safety
from app.services.inspection_images import image_path


def probe(tmp_path, **overrides):
    settings = Settings(_env_file=None, app_env='production', uploads_dir=tmp_path, **overrides)
    app = FastAPI()
    configure_safety(app, settings)
    calls = []

    @app.api_route('/{path:path}', methods=['GET', 'POST'])
    def endpoint(path: str):
        calls.append(path)
        if path == 'exception':
            raise RuntimeError('PRIVATE_CONNECTION_STRING')
        if path == 'handled':
            raise HTTPException(422, 'PRIVATE_CONNECTION_STRING')
        return {'ok': True}

    return TestClient(app), calls


def test_global_provider_budget_ignores_forwarded_ips(tmp_path):
    client, calls = probe(tmp_path, demo_provider_actions_per_hour=2)
    assert client.post('/sessions/a/troubleshooting/run').status_code == 200
    assert client.post('/sessions/b/images/c/analyze').status_code == 200
    response = client.post('/sessions/d/troubleshooting/follow-up', headers={'X-Forwarded-For': 'different'})
    assert response.status_code == 429 and response.headers['Retry-After']
    assert len(calls) == 2


@pytest.mark.parametrize('path', ['/documents/ingest', '/sessions/a/images/analyze-all'])
def test_public_admin_and_batch_paths_blocked(tmp_path, path):
    client, calls = probe(tmp_path)
    assert client.post(path).status_code == 403
    assert not calls


@pytest.mark.parametrize('path', ['exception', 'handled'])
def test_error_responses_hide_exception_and_release_slot(tmp_path, path):
    client, calls = probe(tmp_path)
    response = client.post('/'+path)
    assert response.status_code in (422, 503)
    assert 'PRIVATE' not in response.text
    assert client.post('/ok').status_code == 200


def test_declared_and_actual_size_limits(tmp_path):
    client, calls = probe(tmp_path)
    assert client.post('/ok', content=b'x', headers={'Content-Length': '99999999'}).status_code == 413
    assert client.post('/ok', content=b'x'*65537, headers={'Content-Length': '1'}).status_code == 413
    assert not calls


def test_chunked_body_is_bounded_before_endpoint(tmp_path):
    calls, sent = [], []

    async def endpoint(*args):
        calls.append(True)

    guard = DemoSafetyMiddleware(endpoint, Settings(_env_file=None, app_env='production'))
    messages = iter([{'type': 'http.request', 'body': b'x'*40000, 'more_body': True},
                     {'type': 'http.request', 'body': b'x'*40000, 'more_body': False}])

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    asyncio.run(guard({'type': 'http', 'method': 'POST', 'path': '/search', 'headers': []}, receive, send))
    assert sent[0]['status'] == 413 and not calls


def test_storage_budget_includes_existing_files_and_new_body(tmp_path):
    (tmp_path/'existing.jpg').write_bytes(b'x'*1000)
    client, calls = probe(tmp_path, demo_upload_quota_bytes=1024)
    response = client.post('/sessions/a/images', files={'images': ('image.jpg', b'x'*100, 'image/jpeg')})
    assert response.status_code == 507 and not calls


def test_read_and_write_budgets_and_health(tmp_path):
    client, calls = probe(tmp_path, demo_requests_per_minute=2, demo_writes_per_hour=1)
    assert client.post('/sessions').status_code == 200
    assert client.post('/sessions').status_code == 429
    assert client.get('/ok').status_code == 200
    assert client.get('/ok').status_code == 429
    assert client.get('/health').status_code == 200


def test_concurrent_writes_cannot_bypass_guard():
    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()
        sent = []

        async def endpoint(scope, receive, send):
            entered.set()
            await release.wait()

        async def receive():
            return {'type': 'http.request', 'body': b''}

        async def send(message):
            sent.append(message)

        guard = DemoSafetyMiddleware(endpoint, Settings(_env_file=None, app_env='production'))
        scope = {'type': 'http', 'method': 'POST', 'path': '/sessions', 'headers': []}
        first = asyncio.create_task(guard(scope, receive, send))
        await entered.wait()
        await guard(scope, receive, send)
        assert sent[0]['status'] == 429
        release.set()
        await first
        assert not guard.writing and guard.active == 0

    asyncio.run(exercise())


def test_validation_does_not_echo_input(tmp_path):
    class Input(BaseModel):
        number: int

    app = FastAPI()
    configure_safety(app, Settings(_env_file=None, app_env='production'))

    @app.post('/input')
    def endpoint(value: Input):
        return value

    response = TestClient(app).post('/input', json={'number': 'PRIVATE_CONNECTION_STRING'})
    assert response.status_code == 422 and 'PRIVATE' not in response.text


def test_production_docs_and_audits_disabled(monkeypatch):
    import importlib
    from app import main
    from app.config import get_settings
    monkeypatch.setenv('APP_ENV', 'production')
    get_settings.cache_clear()
    try:
        importlib.reload(main)
        client = TestClient(main.app)  # No context manager: do not initialize DB/models.
        for path in ['/docs', '/redoc', '/openapi.json']:
            assert client.get(path).status_code == 404
        assert client.get(f'/sessions/{uuid4()}/troubleshooting/runs/{uuid4()}?include_evidence=true').status_code == 403
        assert client.post('/documents/ingest').status_code == 403
    finally:
        monkeypatch.delenv('APP_ENV')
        get_settings.cache_clear()
        importlib.reload(main)


@pytest.mark.parametrize('stored_path', ['../outside.jpg', '/outside.jpg', 'other-session/image.jpg'])
def test_stored_image_must_resolve_inside_own_session(tmp_path, stored_path):
    with pytest.raises(ValueError, match='Invalid stored image path'):
        image_path(Settings(_env_file=None, uploads_dir=tmp_path),
                   SimpleNamespace(session_id=uuid4(), stored_path=stored_path))


def test_local_development_retains_tools():
    app = FastAPI()
    configure_safety(app, Settings(_env_file=None, app_env='development'))

    @app.post('/documents/ingest')
    def ingest():
        return {'ok': True}

    client = TestClient(app)
    assert client.get('/docs').status_code == 200
    assert client.post('/documents/ingest').status_code == 200
