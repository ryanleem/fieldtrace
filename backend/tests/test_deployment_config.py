"""Deployment boundary tests; no external services or provider calls."""
import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.config import Settings


@pytest.mark.parametrize('scheme', ['postgres', 'postgresql', 'postgresql+psycopg'])
def test_cloud_database_preserves_ssl_and_encoded_credentials(scheme):
    suffix = 'fixture:encoded%40value@db.example.test:5432/guardian?sslmode=require&application_name=fieldtrace'
    settings = Settings(_env_file=None, database_url=scheme+'://'+suffix, postgres_password='unused')
    assert settings.database_url == 'postgresql+psycopg://'+suffix
    assert make_url(settings.database_url).query['sslmode'] == 'require'


def test_local_database_password_fallback():
    settings = Settings(_env_file=None, database_url='', postgres_password='local-example')
    url = make_url(settings.database_url)
    assert (url.host, url.port, url.password, url.drivername) == ('127.0.0.1', 55432, 'local-example', 'postgresql+psycopg')


def test_cors_csv_and_empty_list():
    settings = Settings(_env_file=None, cors_allowed_origins=' https://frontend.example.test, http://localhost:5173,https://frontend.example.test, ')
    assert settings.cors_origins == ['https://frontend.example.test', 'http://localhost:5173']
    assert Settings(_env_file=None, cors_allowed_origins='').cors_origins == []


@pytest.mark.parametrize('origin', ['*', 'https://*.example.test', 'null', 'https://example.test/path', 'https://example.test?x=1', 'https://example.test:bad'])
def test_cors_rejects_non_origins(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_allowed_origins=origin)


def test_cloud_upload_alias_preserves_existing_setting(monkeypatch, tmp_path):
    monkeypatch.setenv('UPLOADS_DIR', str(tmp_path/'old'))
    assert Settings(_env_file=None).uploads_dir == tmp_path/'old'
    monkeypatch.setenv('UPLOAD_ROOT', str(tmp_path/'cloud'))
    assert Settings(_env_file=None).uploads_dir == tmp_path/'cloud'


def test_app_cors_allows_only_configured_origin_without_starting_database(monkeypatch):
    from app import main
    from app.config import get_settings
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', 'https://frontend.example.test')
    get_settings.cache_clear()
    import importlib
    importlib.reload(main)
    # Exercise the actual app middleware on a probe, without its DB/model lifespan.
    probe = FastAPI()
    probe.user_middleware = list(main.app.user_middleware)
    client = TestClient(probe)
    headers = {'Origin': 'https://frontend.example.test', 'Access-Control-Request-Method': 'PATCH',
               'Access-Control-Request-Headers': 'content-type,authorization'}
    try:
        allowed = client.options('/sessions', headers=headers)
        assert allowed.status_code == 200
        assert allowed.headers['access-control-allow-origin'] == headers['Origin']
        assert 'access-control-allow-credentials' not in allowed.headers
        headers['Origin'] = 'https://untrusted.example.test'
        denied = client.options('/sessions', headers=headers)
        assert denied.status_code == 400
        assert 'access-control-allow-origin' not in denied.headers
    finally:
        monkeypatch.delenv('CORS_ALLOWED_ORIGINS')
        get_settings.cache_clear()
        importlib.reload(main)


@pytest.mark.parametrize('port', ['9000', '0', 'invalid'])
def test_cloud_start_port_without_starting_server(monkeypatch, port):
    monkeypatch.delenv('APP_ENV', raising=False)
    path = Path(__file__).resolve().parents[2]/'scripts/start_backend.py'
    spec = importlib.util.spec_from_file_location('cloud_start', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://db.example.test/fixture')
    monkeypatch.setenv('PORT', port)
    calls = []
    monkeypatch.setattr(module.os, 'execv', lambda *args: calls.append(args))
    monkeypatch.setattr(module.os, 'chdir', lambda *args: None)
    if port == '9000':
        module.main()
        assert calls[0][1][-4:] == ['--host', '0.0.0.0', '--port', '9000']
        assert module.os.environ['APP_ENV'] == 'production'
        assert calls[0][1][calls[0][1].index('--workers') + 1] == '1'
    else:
        with pytest.raises(SystemExit, match='PORT'):
            module.main()
        assert not calls
