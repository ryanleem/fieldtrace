from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app.config import Settings, get_settings
from app.db.init_db import initialize


def authenticated_client(app, monkeypatch, engine, session_id=None):
    """Existing route regressions now use a verified test identity and real SQL ownership."""
    from app import auth
    from app.models.equipment import EquipmentSession
    from sqlalchemy.orm import Session
    user = uuid4()
    monkeypatch.setattr(auth, 'get_engine', lambda: engine)
    app.dependency_overrides[auth.require_user] = lambda: user
    if session_id:
        with Session(engine) as db, db.begin():
            row = db.get(EquipmentSession, session_id)
            row.owner_user_id, row.session_name = user, 'Regression session'
    return user


class TestEmbedder:
    """Deterministic fixture vectors only; never used for real-corpus evaluation."""
    dimensions = 384
    max_tokens = 256

    def token_count(self, text):
        return len(text.split())

    def encode(self, texts, query=False):
        return [[1.0] + [0.0] * (self.dimensions-1) for _ in texts]


def pytest_addoption(parser):
    parser.addoption("--integration", action="store_true", help="Run isolated-schema PostgreSQL integration tests")
    parser.addoption("--corpus", action="store_true", help="Run read-only real-corpus tests")


def pytest_collection_modifyitems(config, items):
    for item in items:
        for marker in ("integration", "corpus"):
            if marker in item.keywords and not config.getoption(f"--{marker}"):
                item.add_marker(pytest.mark.skip(reason=f"Requires --{marker}"))


@pytest.fixture
def isolated_db(tmp_path):
    url = get_settings().database_url
    admin = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema},public", "connect_timeout": 5})
    engine = engine.execution_options(schema_translate_map={None: schema})
    settings = Settings(database_url=url, embedding_model="test-fixture", embedding_revision=None,
                        manuals_dir=tmp_path / "manuals", processed_dir=tmp_path / "processed")
    settings.manuals_dir.mkdir()
    embedder = TestEmbedder()
    try:
        initialize(engine, embedder, settings)
        yield engine, settings, embedder
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
