"""Database configuration contracts; no database or provider calls."""
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url

from app.config import Settings


@pytest.fixture
def clean_database_env(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('POSTGRES_PASSWORD', raising=False)


def test_environment_password_is_encoded_and_not_in_repr(clean_database_env, monkeypatch):
    value = uuid4().hex + '@:/% spaces'
    monkeypatch.setenv('POSTGRES_PASSWORD', value)
    settings = Settings(_env_file=None)
    url = make_url(settings.database_url)
    assert url.password == value and url.port == 55432 and url.database == 'guardian'
    assert value not in repr(settings) and settings.database_url not in repr(settings)


def test_explicit_database_url_wins(clean_database_env, monkeypatch):
    monkeypatch.setenv('POSTGRES_PASSWORD', uuid4().hex)
    explicit = 'postgresql+psycopg://other@localhost:5433/custom'
    assert Settings(_env_file=None, database_url=explicit).database_url == explicit


def test_no_implicit_password(clean_database_env):
    assert make_url(Settings(_env_file=None).database_url).password is None


@pytest.fixture
def native(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'scripts/setup_native_postgres.py'
    spec = importlib.util.spec_from_file_location('native_database_setup', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.delenv('POSTGRES_PASSWORD', raising=False)
    return module


def test_native_dotenv_and_environment_precedence(native, tmp_path, monkeypatch):
    local_value, override = uuid4().hex, uuid4().hex
    (tmp_path / '.env').write_text('POSTGRES_PASSWORD=' + local_value, encoding='utf-8')
    assert native.configured_password() == local_value
    monkeypatch.setenv('POSTGRES_PASSWORD', override)
    assert native.configured_password() == override


@pytest.mark.parametrize('value', [None, '', 'REPLACE_WITH_LOCAL_DB_PASSWORD', 'line\nbreak'])
def test_native_rejects_missing_placeholder_or_multiline(native, monkeypatch, value):
    if value is not None:
        monkeypatch.setenv('POSTGRES_PASSWORD', value)
    with pytest.raises(ValueError, match='POSTGRES_PASSWORD'):
        native.configured_password()


@pytest.mark.parametrize('fail', [False, True])
def test_init_password_file_always_removed(native, tmp_path, fail):
    value = uuid4().hex
    try:
        with native.initialization_password_file(value, tmp_path) as path:
            assert path.read_text(encoding='utf-8') == value + '\n'
            if fail:
                raise RuntimeError('simulated initdb failure')
    except RuntimeError:
        assert fail
    assert not path.exists()
