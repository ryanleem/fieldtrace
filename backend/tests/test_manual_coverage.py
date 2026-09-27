"""Coverage gates use actual indexed evidence; fixtures are not accuracy claims."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from app.api import troubleshooting as api
from app.config import Settings
from app.models import DocumentChunk
from app.models.equipment import Equipment, EquipmentSession
from app.models.troubleshooting import TroubleshootingSession
from app.schemas.document import IngestRequest
from app.schemas.troubleshooting import TroubleshootingInput
from app.services import troubleshooting_sessions as service
from app.services.ingestion import ingest
from app.services.manual_coverage import indexed_manual_coverage
from app.services.troubleshooting_pipeline import Pipeline
from test_retrieval import make_pdf
from test_troubleshooting import context, evidence, MockLLM, troubleshooting_db
from test_vision import inspection_db


FILTERS = {'equipment_model': 'ACS880', 'equipment_family': 'ACS880 Drives'}


@pytest.fixture
def coverage_db():
    # Only the relational columns used by EXISTS are needed. This exercises real
    # SQL without emulating PostgreSQL's vector, FTS, or ingestion behavior.
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE documents (id TEXT PRIMARY KEY, equipment_model TEXT, equipment_family TEXT, chunks_created INTEGER)'))
        connection.execute(text('CREATE TABLE document_pages (document_id TEXT, page_number INTEGER)'))
        connection.execute(text('CREATE TABLE document_chunks (id TEXT PRIMARY KEY, document_id TEXT, page_number INTEGER)'))
    with Session(engine) as db:
        yield db
    engine.dispose()


def add_index(db, model='ACS880', family='ACS880 Drives', *, chunk=True, page=True, counter=1):
    document_id = uuid4().hex
    db.execute(text('INSERT INTO documents VALUES (:id, :model, :family, :counter)'),
               dict(id=document_id, model=model, family=family, counter=counter))
    if page:
        db.execute(text('INSERT INTO document_pages VALUES (:id, 1)'), dict(id=document_id))
    if chunk:
        db.execute(text('INSERT INTO document_chunks VALUES (:chunk, :id, 1)'),
                   dict(chunk=uuid4().hex, id=document_id))


@pytest.mark.parametrize('model,family,chunk,page,counter,expected', [
    ('ACS880', 'ACS880 Drives', True, True, 1, True),
    ('ACS580', 'ACS880 Drives', True, True, 1, False),
    ('ACS880', 'Other family', True, True, 1, False),
    ('ACS880', 'ACS880 Drives', False, True, 99, False),
    ('ACS880', 'ACS880 Drives', True, False, 99, False),
    ('ACS880', 'ACS880 Drives', True, True, 0, True),
])
def test_coverage_uses_retrievable_chunks_not_document_counter(coverage_db, model, family, chunk, page, counter, expected):
    add_index(coverage_db, model, family, chunk=chunk, page=page, counter=counter)
    assert indexed_manual_coverage(coverage_db, FILTERS) is expected


def test_filters_require_model_and_family_in_the_same_document(coverage_db):
    add_index(coverage_db, model='ACS880', family='Wrong family')
    add_index(coverage_db, model='Wrong model', family='ACS880 Drives')
    assert not indexed_manual_coverage(coverage_db, FILTERS)


def test_family_only_filter_and_empty_filter_match_retrieval_semantics(coverage_db):
    add_index(coverage_db, model=None, family='Induction Motors and Generators')
    assert indexed_manual_coverage(coverage_db, {'equipment_model': None,
        'equipment_family': 'Induction Motors and Generators'})
    assert not indexed_manual_coverage(coverage_db, {'equipment_model': '',
        'equipment_family': 'Induction Motors and Generators'})


class ForbiddenDependency:
    def __getattr__(self, name):
        raise AssertionError(f'Dependency must not be used: {name}')


def forbidden_retrieval(*args, **kwargs):
    raise AssertionError('No retrieval call is allowed without indexed coverage')


def test_missing_manual_stops_before_embedding_retrieval_and_provider():
    ctx = dict(context(), manual_coverage=False)
    pipeline = Pipeline(ForbiddenDependency(), ForbiddenDependency(), Settings(), forbidden_retrieval)
    result = pipeline.execute(ctx)
    assert result['status'] == 'insufficient_evidence'
    assert result['confidence'] == 'LOW'
    assert result['primary_cause'] is None
    assert result['recommended_actions'] == result['sources'] == []
    assert 'no indexed manual' in result['message']
    assert 'manual' in result['next_question']
    assert result['missing_information']
    assert pipeline.audit['calls'] == pipeline.audit['attempts'] == []


def test_workspace_draft_is_excluded_from_snapshot_and_coverage_changes_fingerprint(coverage_db):
    equipment = SimpleNamespace(manufacturer='ABB', model_name='ACS880-01',
        equipment_family='ACS880 Drives', retrieval_model='ACS880', retrieval_family='ACS880 Drives')
    owner = SimpleNamespace(id=uuid4(), identification_revision=1,
        confirmed_equipment_id='abb-acs880-01', raw_ocr_text='')
    row = SimpleNamespace(revision=1, inputs={'reported_symptoms': ['Overheating'],
        'workspace_draft': {'symptom': 'Unsubmitted symptom'}})
    class SnapshotDB:
        def get(self, model, key):
            assert model is Equipment
            return equipment
        def scalars(self, query):
            return SimpleNamespace(all=lambda: [])
        def scalar(self, query):
            return coverage_db.scalar(query)
    db = SnapshotDB()
    before = service.snapshot(db, owner, row)
    assert before['manual_coverage'] is False
    assert set(before['inputs']) == set(service.FIELDS)
    row.inputs['workspace_draft'] = {'symptom': 'Edited draft'}
    assert service.fingerprint(service.snapshot(db, owner, row)) == service.fingerprint(before)
    add_index(coverage_db)
    after = service.snapshot(db, owner, row)
    assert after['manual_coverage'] is True
    assert service.fingerprint(after) != service.fingerprint(before)
    owner.confirmed_equipment_id = None
    assert service.snapshot(db, owner, row)['manual_coverage'] is None


@pytest.mark.parametrize('path,payload', [('/run', None), ('/follow-up', {'answer': 'Fan spinning'})])
def test_unauthenticated_requests_cannot_reach_coverage_or_dependencies(monkeypatch, path, payload):
    app = FastAPI(); app.include_router(api.router)
    def forbidden():
        raise AssertionError('Unauthenticated request reached a dependency')
    app.dependency_overrides[api.get_troubleshooting_provider] = forbidden
    app.dependency_overrides[api.get_embedder] = forbidden
    monkeypatch.setattr(service, 'indexed_manual_coverage', forbidden)
    response = TestClient(app).post(f'/sessions/{uuid4()}/troubleshooting{path}', json=payload)
    assert response.status_code == 401


def seed_manual(settings, engine, embedder):
    make_pdf(settings.manuals_dir, 'coverage-fixture.pdf', 'Synthetic fixture: restricted airflow may cause overheating.')
    ingest(engine, IngestRequest(filename='coverage-fixture.pdf', title='Coverage fixture',
        equipment_model='ACS880', equipment_family='ACS880 Drives'), embedder, settings)


@pytest.mark.integration
def test_no_coverage_persists_without_dependencies_then_added_manual_invalidates_result(troubleshooting_db, monkeypatch):
    engine, settings, sid, embedder = troubleshooting_db
    service.update(engine, sid, TroubleshootingInput(reported_symptoms=['Overheating']))
    monkeypatch.setattr(service, 'retrieve', forbidden_retrieval)
    state = service.run(engine, sid, ForbiddenDependency(), ForbiddenDependency(), settings)
    assert state['result']['status'] == 'insufficient_evidence'
    assert state['retrieved_evidence_history'][0]['status'] == 'insufficient_evidence'
    seed_manual(settings, engine, embedder)
    assert service.get_state(engine, sid)['result']['status'] == 'stale'


@pytest.mark.integration
def test_injected_retriever_preserves_database_fingerprint_and_saved_draft(troubleshooting_db):
    engine, settings, sid, embedder = troubleshooting_db
    service.update(engine, sid, TroubleshootingInput(reported_symptoms=['Overheating']))
    with Session(engine) as db, db.begin():
        row = db.get(TroubleshootingSession, sid)
        row.inputs = {**row.inputs, 'workspace_draft': {'symptom': 'Unsubmitted'}}
    llm = MockLLM()
    result = service.run(engine, sid, llm, embedder, settings, lambda plan: [evidence()])
    assert result['result']['status'] == 'suspected_cause'
    assert result['workspace_draft']['symptom'] == 'Unsubmitted'
    assert llm.calls[0][1]['context']['manual_coverage'] is None
    with Session(engine) as db, db.begin():
        owner = db.get(EquipmentSession, sid)
        row = db.get(TroubleshootingSession, sid)
        ctx = service.snapshot(db, owner, row)
        assert ctx['manual_coverage'] is False
        assert row.current['context_fingerprint'] == service.fingerprint(ctx)
        row.inputs = {**row.inputs, 'workspace_draft': {'symptom': 'Draft changed'}}
    assert service.get_state(engine, sid)['result']['status'] == 'suspected_cause'
    with Session(engine) as db, db.begin():
        db.get(EquipmentSession, sid).identification_revision += 1
    state = service.update(engine, sid, TroubleshootingInput(reported_symptoms=['New issue']))
    assert state['workspace_draft']['symptom'] == 'Draft changed'
    assert state['reported_symptoms'] == ['New issue']


@pytest.mark.integration
def test_removed_indexed_chunks_invalidates_previous_result(troubleshooting_db, monkeypatch):
    engine, settings, sid, embedder = troubleshooting_db
    seed_manual(settings, engine, embedder)
    service.update(engine, sid, TroubleshootingInput(reported_symptoms=['Overheating']))
    monkeypatch.setattr(service, 'retrieve', lambda *args: [evidence()])
    state = service.run(engine, sid, MockLLM(), embedder, settings)
    assert state['result']['status'] == 'suspected_cause'
    with Session(engine) as db, db.begin():
        db.execute(delete(DocumentChunk))
    assert service.get_state(engine, sid)['result']['status'] == 'stale'


@pytest.mark.corpus
def test_real_catalog_acs880_coverage_and_absent_drive_manuals():
    from app.db.session import get_engine
    with Session(get_engine()) as db:
        for model, expected in [('abb-acs880-01', True), ('abb-acs580-01', False), ('abb-ach580-01', False)]:
            equipment = db.get(Equipment, model)
            assert equipment is not None
            filters = dict(equipment_model=equipment.retrieval_model or None,
                           equipment_family=equipment.retrieval_family)
            assert indexed_manual_coverage(db, filters) is expected
