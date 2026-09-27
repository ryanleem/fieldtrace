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


# Only this middleware test module mocks signature verification. The auth suite
# separately tests real signed JWT validation, issuer, audience, expiry and role.
USERS = {'user-a': uuid4(), 'user-b': uuid4(), 'user-c': uuid4()}

@pytest.fixture(autouse=True)
def verified_test_tokens(monkeypatch):
    def verify(token, settings):
        if token not in USERS: raise HTTPException(401, 'Invalid sign-in')
        return USERS[token]
    monkeypatch.setattr('app.auth.verify_token', verify)


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

    return TestClient(app, headers={'Authorization':'Bearer user-a'}), calls


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
        assert client.get(f'/sessions/{uuid4()}/troubleshooting/runs/{uuid4()}?include_evidence=true').status_code == 401
        from app.auth import session_access
        main.app.dependency_overrides[session_access] = lambda: None
        assert client.get(f'/sessions/{uuid4()}/troubleshooting/runs/{uuid4()}?include_evidence=true').status_code == 403
        main.app.dependency_overrides.clear()
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


def test_shared_hourly_provider_budget_reproduces_five_minute_block(tmp_path, monkeypatch, caplog):
    clock=[100.0]
    monkeypatch.setattr('app.demo_safety.monotonic',lambda:clock[0])
    client,calls=probe(tmp_path,demo_provider_actions_per_hour=8)
    for _ in range(7):assert client.post('/sessions/a/equipment/identify').status_code==200
    assert client.post('/sessions/a/images/photo/analyze').status_code==200
    for path in ['/sessions/a/images','/sessions/a/equipment/confirm','/sessions/a/troubleshooting/symptoms']:
        assert client.post(path).status_code==200
    assert client.get('/sessions/a').status_code==200
    before=len(calls)
    response=client.post('/sessions/a/troubleshooting/run')
    assert response.status_code==429 and response.headers['Retry-After']=='3600'
    clock[0]+=301
    response=client.post('/sessions/b/troubleshooting/run',headers={'X-Forwarded-For':'100.64.0.22'})
    assert response.status_code==429 and response.headers['Retry-After']=='3299'
    assert len(calls)==before
    assert 'reason=provider_actions_global used=8 limit=8 window_seconds=3600' in caplog.text
    assert 'sessions/a' not in caplog.text and '100.64.' not in caplog.text
    clock[0]=3700
    assert client.post('/sessions/a/troubleshooting/run').status_code==200


@pytest.mark.parametrize('status',[401,403,404])
def test_auth_or_ownership_denials_do_not_spend_provider_capacity(tmp_path,status):
    app=FastAPI();configure_safety(app,Settings(_env_file=None,app_env='production',uploads_dir=tmp_path,demo_provider_actions_per_hour=1,demo_provider_actions_per_user_per_hour=1))
    allowed=[False];calls=[]
    @app.post('/sessions/a/troubleshooting/run')
    def endpoint():
        if not allowed[0]:raise HTTPException(status)
        calls.append(True);return {'ok':True}
    client=TestClient(app,headers={'Authorization':'Bearer user-a'})
    for _ in range(2):assert client.post('/sessions/a/troubleshooting/run').status_code==status
    allowed[0]=True
    assert client.post('/sessions/a/troubleshooting/run').status_code==200
    assert client.post('/sessions/a/troubleshooting/run').status_code==429
    assert len(calls)==1


def test_body_rejection_releases_provider_reservation_but_not_write_budget(tmp_path):
    client,calls=probe(tmp_path,demo_provider_actions_per_hour=1,demo_writes_per_hour=2)
    path='/sessions/a/troubleshooting/run'
    assert client.post(path,content=b'x',headers={'Content-Length':'999999'}).status_code==413
    assert client.post(path).status_code==200
    response=client.post('/sessions/a/troubleshooting/symptoms')
    assert response.status_code==429 and response.headers['Retry-After']=='3600'
    assert len(calls)==1


def test_minute_retry_after_and_rejected_retries_do_not_extend_window(tmp_path,monkeypatch):
    clock=[100.0];monkeypatch.setattr('app.demo_safety.monotonic',lambda:clock[0])
    client,_=probe(tmp_path,demo_requests_per_minute=1)
    assert client.get('/ok').status_code==200
    clock[0]=130.1
    assert client.get('/ok').headers['Retry-After']=='30'
    clock[0]=160.0
    assert client.get('/ok').status_code==200


def test_provider_failure_still_charged_and_concurrency_released():
    async def exercise():
        async def endpoint(scope,receive,send):raise RuntimeError('private')
        async def receive():return {'type':'http.request','body':b''}
        sent=[]
        async def send(message):sent.append(message)
        guard=DemoSafetyMiddleware(endpoint,Settings(_env_file=None,app_env='production',demo_provider_actions_per_hour=1))
        scope={'type':'http','method':'POST','path':'/sessions/a/troubleshooting/run','headers':[(b'authorization',b'Bearer user-a')]}
        await guard(scope,receive,send)
        assert sent[0]['status']==503 and guard.active==0 and not guard.writing
        sent.clear();await guard(scope,receive,send)
        assert sent[0]['status']==429
    asyncio.run(exercise())


def test_cancelled_request_releases_concurrency():
    async def exercise():
        entered=asyncio.Event()
        async def endpoint(scope,receive,send):entered.set();await asyncio.Event().wait()
        async def receive():return {'type':'http.request','body':b''}
        async def send(message):pass
        guard=DemoSafetyMiddleware(endpoint,Settings(_env_file=None,app_env='production'))
        task=asyncio.create_task(guard({'type':'http','method':'POST','path':'/sessions/a/troubleshooting/run','headers':[(b'authorization',b'Bearer user-a')]},receive,send))
        await entered.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert guard.active==0 and not guard.writing
        assert len(guard.providers)==1
    asyncio.run(exercise())


def test_production_cors_exposes_retry_after_without_trusting_proxy_headers():
    from app.main import app
    from fastapi.middleware.cors import CORSMiddleware
    cors=next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    assert cors.kwargs['expose_headers']==['Retry-After']
    assert 'Authorization' in cors.kwargs['allow_headers']
    assert '*' not in cors.kwargs['allow_origins']


def test_default_user_allowance_supports_full_workflows_independently(tmp_path):
    client,calls=probe(tmp_path)
    for _ in range(10):
        assert client.post('/sessions/b/images/photo/analyze',headers={'Authorization':'Bearer user-b'}).status_code==200
    for i in range(30):
        assert client.post(f'/sessions/a-{i}/troubleshooting/run').status_code==200
    assert client.post('/sessions/new/troubleshooting/run',headers={'X-Forwarded-For':'another-ip'}).status_code==429
    assert client.post('/sessions/b/troubleshooting/run',headers={'Authorization':'Bearer user-b'}).status_code==200
    assert len(calls)==41


def test_global_ceiling_is_shared_across_verified_users(tmp_path,caplog):
    client,calls=probe(tmp_path,demo_provider_actions_per_hour=4)
    for token in ['user-a','user-b']:
        for _ in range(2):assert client.post('/sessions/any/troubleshooting/run',headers={'Authorization':'Bearer '+token}).status_code==200
    response=client.post('/sessions/third/troubleshooting/run',headers={'Authorization':'Bearer user-c'})
    assert response.status_code==429 and response.headers['Retry-After']=='3600'
    assert 'reason=provider_actions_global' in caplog.text
    assert all(str(uid) not in caplog.text for uid in USERS.values())
    assert len(calls)==4


def test_user_window_retry_and_rotated_token_use_verified_identity(tmp_path,monkeypatch,caplog):
    clock=[100.0];monkeypatch.setattr('app.demo_safety.monotonic',lambda:clock[0])
    monkeypatch.setitem(USERS,'rotated-a',USERS['user-a'])
    client,calls=probe(tmp_path,demo_provider_actions_per_user_per_hour=2)
    assert client.post('/sessions/one/troubleshooting/run').status_code==200
    assert client.post('/sessions/two/images/image/analyze').status_code==200
    clock[0]=401.2
    response=client.post('/sessions/three/troubleshooting/follow-up',headers={'Authorization':'Bearer rotated-a'})
    assert response.status_code==429 and response.headers['Retry-After']=='3299'
    assert 'reason=provider_actions_user' in caplog.text
    assert client.post('/sessions/other/troubleshooting/run',headers={'Authorization':'Bearer user-b'}).status_code==200
    clock[0]=3700
    assert client.post('/sessions/one/troubleshooting/run').status_code==200
    assert len(calls)==4


def test_unauthenticated_requests_cannot_select_or_spend_user_budget(tmp_path):
    client,calls=probe(tmp_path,demo_provider_actions_per_user_per_hour=1,demo_provider_actions_per_hour=1,demo_writes_per_hour=4)
    client.headers.pop('authorization')
    path='/sessions/a/troubleshooting/run'
    assert client.post(path,headers={'X-Forwarded-For':'100.64.0.4','owner_user_id':str(USERS['user-a'])}).status_code==401
    assert client.post(path,headers={'Authorization':'Bearer forged-token'}).status_code==401
    assert client.get('/public').status_code==200
    assert client.post(path,headers={'Authorization':'Bearer user-a'}).status_code==200
    assert client.post(path).status_code==401
    assert client.post(path).status_code==429  # unauthenticated writes still bounded
    assert len(calls)==2


def test_verified_uuid_reused_without_rechecking_jwt(tmp_path,monkeypatch):
    from fastapi import Depends
    from app.auth import require_user
    verified=[]
    def verify(token,settings):verified.append(token);return USERS['user-a']
    monkeypatch.setattr('app.auth.verify_token',verify)
    app=FastAPI();configure_safety(app,Settings(_env_file=None,app_env='production',uploads_dir=tmp_path))
    @app.post('/sessions/a/troubleshooting/run')
    def endpoint(user=Depends(require_user)):return {'user':str(user)}
    client=TestClient(app)
    assert client.post('/sessions/a/troubleshooting/run',headers={'Authorization':'Bearer user-a'}).json()=={'user':str(USERS['user-a'])}
    assert verified==['user-a']
