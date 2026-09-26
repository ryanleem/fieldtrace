import json
from copy import deepcopy
from uuid import uuid4
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.config import Settings
from app.schemas.search import Evidence
from app.schemas.troubleshooting import TroubleshootingInput
from app.services.troubleshooting_pipeline import Pipeline, confidence
from app.services.troubleshooting_provider import OpenAITroubleshootingProvider, TroubleshootingUnavailable
from app.services.troubleshooting_query import construct_query
from app.services import troubleshooting_sessions as service
from app.services import equipment_sessions as equipment
from app.db.init_troubleshooting import initialize_troubleshooting
from app.models.equipment import EquipmentSession
from app.api import troubleshooting as api
from conftest import TestEmbedder as Embedder
from test_vision import inspection_db, upload, MockVision
from app.services.inspection_images import analyze_all


def context():
    return dict(equipment={'manufacturer': 'ABB', 'model': 'ACS880-01', 'family': 'ACS880 Drives'},
        retrieval_filters={'equipment_model': 'ACS880', 'equipment_family': 'ACS880 Drives'},
        inputs={'reported_symptoms': ['Overheating with fault 5091'], 'measurements': [],
                'checks_completed': [], 'ruled_out_causes': [], 'follow_up_answers': []},
        visual_findings=[{'description': 'Visible dust near ventilation', 'visual_confidence': 'high'}])


def evidence(rank=1):
    return Evidence(rank=rank, chunk_id=uuid4(), document_id=uuid4(), document_title='Fixture manual',
        source_url='https://example.test/manual.pdf', citation_url='https://example.test/manual.pdf#page=12',
        document_number='TEST', revision='A', equipment_model='ACS880', equipment_family='ACS880 Drives',
        page_number=12, printed_page_label='10', section_title='Cooling', content_type='text', chunk_index=0,
        chunk_text='Restricted airflow can cause overheating. Cooling passages must be unobstructed.',
        source_blocks=[], safety_context=[], extraction_notes=[], semantic_rank=rank, keyword_rank=rank)


class MockLLM:
    """Configurable deterministic replies, not an accuracy evaluation."""
    def __init__(self, *, strength='STRONG', relationship='CONSISTENT', unsupported=(), partial=None,
                 mutate=None, primary='Possible restricted airflow', candidate_extra=None):
        self.calls, self.strength, self.relationship = [], strength, relationship
        self.unsupported, self.partial, self.mutate = set(unsupported), partial or {}, mutate
        self.primary, self.extra = primary, candidate_extra

    def complete(self, stage, payload):
        self.calls.append((stage, deepcopy(payload)))
        if self.mutate: self.mutate(stage, payload)
        if stage == 'review':
            output = dict(chunks=[dict(chunk_id=e['chunk_id'], relevance='RELEVANT', issue='cooling',
                reason='Applicable cooling passage') for e in payload['evidence']],
                strength=self.strength, missing_information=[])
        elif stage == 'conflict':
            output = dict(relationship=self.relationship, chunk_ids=[e['chunk_id'] for e in payload['evidence']],
                          explanation='Fixture comparison')
        elif stage == 'candidate':
            cid = payload['evidence'][0]['chunk_id']
            output = dict(primary_cause=dict(label=self.primary, rationale='Restricted airflow is a documented possibility.', claim_ids=['p']),
                alternative_causes=[], technical_claims=[dict(claim_id='p', text='Airflow restriction can cause overheating.', citation_chunk_ids=[cid])],
                recommended_actions=[dict(action='Check cooling passages using the applicable manual procedure.', citation_chunk_ids=[cid])],
                next_question=None, missing_information=[])
            if self.extra: self.extra(output, cid)
        else:
            claim = payload['claim']
            output = dict(status='UNSUPPORTED' if claim in self.unsupported else 'PARTIAL' if claim in self.partial else 'SUPPORTED',
                explanation='Deterministic fixture verdict', revised_text=self.partial.get(claim))
        return dict(output=output, raw={'provider': 'test-mock'})


def pipeline(llm=None, rows=None, ctx=None):
    rows = rows if rows is not None else [evidence()]
    p = Pipeline(llm or MockLLM(), Embedder(), Settings(), lambda plan: rows)
    return p, p.execute(ctx or context())


def test_supported_primary_and_provenance():
    p, result = pipeline()
    assert result['confidence'] == 'HIGH'
    assert result['sources'][0]['page_number'] == 12
    assert result['sources'][0]['section_title'] == 'Cooling'
    assert 'chunk_text' not in json.dumps(result)
    assert p.audit['attempts'][0]['candidate']
    assert all(v['status'] == 'SUPPORTED' for v in p.audit['attempts'][0]['verifications'])


@pytest.mark.parametrize('revision', [False, True])
def test_verifier_admitted_gap_cannot_pass_even_after_rewrite(revision):
    class AdmittedGap:
        def __init__(self): self.calls = 0
        def complete(self, stage, payload):
            self.calls += 1
            if revision and self.calls == 1:
                return {'output': dict(status='PARTIAL', explanation='Only a portion follows.', revised_text='Narrower claim')}
            return {'output': dict(status='SUPPORTED', revised_text=None,
                explanation='While not explicitly stated in the cited chunks, corrosion may impact signal continuity.')}
    row=evidence().model_dump(mode='json');cid=row['chunk_id'];log=[]
    p=Pipeline(AdmittedGap(),Embedder(),Settings(),lambda _:[])
    assert p.verify('Corrosion may cause this fault.',[cid],{cid:row},log,'primary:rationale') == (None,False)
    assert log[-1]['status']=='UNSUPPORTED' and log[-1]['provider_status']=='SUPPORTED'


def test_admitted_gap_primary_still_uses_only_one_retry():
    class AdmittedGap(MockLLM):
        def complete(self, stage, payload):
            response=super().complete(stage,payload)
            if stage=='verify':response['output']['explanation']='The possibility is not directly supported by the supplied evidence.'
            return response
    p,result=pipeline(AdmittedGap())
    assert result['confidence']=='LOW' and result['primary_cause'] is None
    assert len(p.audit['attempts'])==2


def test_weak_evidence_skips_candidate_and_asks_targeted_question():
    llm = MockLLM(strength='WEAK')
    _, result = pipeline(llm)
    assert result['primary_cause'] is None and result['confidence'] == 'LOW'
    assert 'temperature' in result['next_question']
    assert not any(s == 'candidate' for s, _ in llm.calls)


def test_weak_evidence_does_not_call_optional_conflict_provider():
    class FailConflict(MockLLM):
        def complete(self, stage, payload):
            assert stage == 'review'
            return super().complete(stage, payload)
    llm = FailConflict(strength='WEAK')
    _, result = pipeline(llm, rows=[evidence(1), evidence(2), evidence(3)])
    assert result['status'] == 'insufficient_evidence' and result['confidence'] == 'LOW'
    assert [stage for stage, _ in llm.calls] == ['review']


@pytest.mark.corpus
def test_exact_fault_definition_outranks_repeated_mentions_and_catalog_boilerplate():
    from app.config import get_settings
    from app.db.session import get_engine
    from app.services.embeddings import get_embedder
    from app.services.troubleshooting_query import retrieve
    ctx = context(); ctx['inputs']['reported_symptoms'] = ['The drive reports fault code 5091.']; ctx['visual_findings'] = []
    embedder = get_embedder(); plan = construct_query(ctx, embedder)
    assert '5091' in plan['technical_keyword_queries'] and 'ACS880-01' not in plan['keyword_queries']
    assert 'ACS880-01' in plan['exact_keyword_terms'] and 'ACS880-01' in plan['filter_covered_terms']
    rows = retrieve(get_engine(), plan, embedder, get_settings())
    assert any(r.page_number == 525 and '5091 | Safe torque off' in r.chunk_text for r in rows[:3])


def test_no_evidence_never_calls_llm():
    llm = MockLLM()
    _, result = pipeline(llm, rows=[])
    assert result['status'] == 'insufficient_evidence' and llm.calls == []


def test_unsupported_nonessential_and_action_are_removed():
    def extra(c, cid):
        c['technical_claims'].append(dict(claim_id='bad', text='Winding failure is confirmed.', citation_chunk_ids=[cid]))
    llm = MockLLM(candidate_extra=extra, unsupported=['Winding failure is confirmed.',
        'Check cooling passages using the applicable manual procedure.'])
    _, result = pipeline(llm)
    assert [c['claim_id'] for c in result['technical_claims']] == ['p']
    assert result['recommended_actions'] == []


@pytest.mark.parametrize('unsupported', ['Airflow restriction can cause overheating.', 'Possible restricted airflow',
                                       'Restricted airflow is a documented possibility.'])
def test_unsupported_primary_claim_label_or_rationale_retries_once(unsupported):
    def alternative(c, cid):
        c['alternative_causes'] = [dict(label='Supported alternative', rationale='Fixture rationale', claim_ids=['a'])]
        c['technical_claims'].append(dict(claim_id='a', text='Other supported claim', citation_chunk_ids=[cid]))
    p, result = pipeline(MockLLM(unsupported=[unsupported], candidate_extra=alternative))
    assert len(p.audit['attempts']) == 2
    assert p.audit['attempts'][0]['query'] != p.audit['attempts'][1]['query']
    assert result['primary_cause'] is None and result['alternative_causes'] == []
    assert result['confidence'] == 'LOW'


def test_retry_can_recover_without_promoting_alternative():
    class Recover(MockLLM):
        def complete(self, stage, payload):
            if stage == 'candidate' and payload['retry']: self.unsupported.clear()
            return super().complete(stage, payload)
    p, result = pipeline(Recover(unsupported=['Possible restricted airflow']))
    assert len(p.audit['attempts']) == 2 and result['primary_cause']


def test_partial_rewrite_is_checked_again_and_caps_confidence():
    original, revised = 'Airflow restriction can cause overheating.', 'Restricted airflow is a possible contributor.'
    llm = MockLLM(partial={original: revised})
    p, result = pipeline(llm)
    assert result['technical_claims'][0]['text'] == revised and result['confidence'] == 'MEDIUM'
    assert any(v['key'] == 'p:revision' for v in p.audit['attempts'][0]['verifications'])


def test_unsupported_rewrite_cannot_reach_answer():
    p, result = pipeline(MockLLM(partial={'Airflow restriction can cause overheating.': 'Unjustified rewrite'},
                                unsupported=['Unjustified rewrite']))
    assert len(p.audit['attempts']) == 2 and result['primary_cause'] is None


def test_verified_rewrites_cannot_turn_information_fields_into_advice():
    question = 'Have cooling passages already been checked?'
    missing = 'Information needed: Existing temperature measurement'
    def extra(c, cid):
        c['next_question'] = question
        c['missing_information'] = ['Existing temperature measurement']
    llm = MockLLM(candidate_extra=extra, partial={question:'Check cooling passages.', missing:'Inspect the machine.'})
    _, result = pipeline(llm)
    assert result['next_question'].endswith('?') and result['next_question'] != 'Check cooling passages.'
    assert result['question_sources'] == [] and result['missing_information'] == []
    assert result['confidence'] == 'MEDIUM'


@pytest.mark.parametrize('relationship', ['CONFLICTING', 'DIFFERENT_APPLICABILITY'])
def test_conflict_surfaced_caps_confidence_and_suppresses_actions(relationship):
    _, result = pipeline(MockLLM(relationship=relationship), rows=[evidence(1), evidence(2), evidence(3), evidence(4)])
    assert result['confidence'] == 'MEDIUM' and not result['recommended_actions']
    assert result['conflicts'][0]['relationship'] == relationship
    assert len(result['conflicts'][0]['citation_chunk_ids']) == 3


def test_unconfirmed_equipment_and_low_visual_confidence_cap():
    ctx = context(); ctx['equipment'] = None
    _, result = pipeline(ctx=ctx)
    assert result['confidence'] == 'MEDIUM' and not result['recommended_actions']
    ctx = context(); ctx['visual_findings'][0]['visual_confidence'] = 'low'
    assert pipeline(ctx=ctx)[1]['confidence'] == 'MEDIUM'


@pytest.mark.parametrize('ids', [[], ['invented-id']])
def test_missing_or_unknown_citations_never_reach_output(ids):
    def extra(c, cid): c['technical_claims'][0]['citation_chunk_ids'] = ids
    _, result = pipeline(MockLLM(candidate_extra=extra))
    assert result['primary_cause'] is None and result['technical_claims'] == []


def test_verifier_gets_only_explicit_citations_not_context_or_other_evidence():
    rows, llm = [evidence(1), evidence(2)], MockLLM()
    pipeline(llm, rows=rows)
    for stage, payload in llm.calls:
        if stage == 'verify':
            assert set(payload) == {'claim', 'evidence'}
            assert [e['chunk_id'] for e in payload['evidence']] == [str(rows[0].chunk_id)]


def test_completed_checks_and_ruled_out_causes_respected():
    ctx = context(); ctx['inputs']['checks_completed'] = ['Check cooling passages using the applicable manual procedure.']
    assert not pipeline(ctx=ctx)[1]['recommended_actions']
    ctx['inputs']['ruled_out_causes'] = ['Possible restricted airflow']
    assert pipeline(ctx=ctx)[1]['primary_cause'] is None


def test_query_preserves_identifiers_and_full_visual_context():
    ctx = context()
    ctx['inputs']['follow_up_answers'] = ['Terminal X1:2 and PE; parameter 31.22; "Motor nominal current"']
    ctx['inputs']['measurements'] = [dict(name='Temperature', value='92', unit='C', location='housing')]
    ctx['inputs']['confirmed_observations'] = ['Fan spinning']
    plan = construct_query(ctx, Embedder())
    assert {'ACS880-01', '5091', '31.22', 'X1:2', 'PE', '92 C', 'Motor nominal current'} <= set(plan['exact_keyword_terms'])
    assert 'Visible dust' in plan['semantic_query'] and 'Fan spinning' in plan['semantic_query']
    assert plan['retrieval_filters']['equipment_model'] == 'ACS880'


def test_bounded_query_reports_omitted_context_without_truncating_identifiers():
    ctx = context(); ctx['inputs']['reported_symptoms'] += ['long ' * 1000]
    plan = construct_query(ctx, Embedder())
    assert Embedder().token_count(plan['semantic_query']) <= 256
    assert plan['omitted_semantic_context'] and '5091' in plan['exact_keyword_terms']


@pytest.mark.parametrize('kind', ['malformed', 'missing_chunk', 'bad_conflict'])
def test_invalid_provider_contract_fails_cleanly(kind):
    class Bad(MockLLM):
        def complete(self, stage, payload):
            result = super().complete(stage, payload)
            if kind == 'malformed': result['output'] = 'not JSON'
            if kind == 'missing_chunk' and stage == 'review': result['output']['chunks'] = []
            if kind == 'bad_conflict' and stage == 'conflict': result['output']['chunk_ids'] = ['unknown']
            return result
    with pytest.raises(TroubleshootingUnavailable): pipeline(Bad(), rows=[evidence(1), evidence(2)])


def test_provider_wire_contract_and_no_vision():
    def handler(request):
        body = json.loads(request.content)
        assert str(request.url) == 'https://api.openai.com/v1/responses'
        assert body['store'] is False and body['text']['format']['strict']
        assert 'image' not in body['input']
        schema = body['text']['format']['schema']
        assert set(schema['required']) == set(schema['properties'])
        return httpx.Response(200, json=dict(status='completed', output=[dict(type='message', content=[
            dict(type='output_text', text=json.dumps(dict(status='SUPPORTED', explanation='test', revised_text=None)))])]))
    provider = OpenAITroubleshootingProvider(Settings(openai_api_key='test-secret'), httpx.MockTransport(handler))
    assert provider.complete('verify', {'claim': 'test', 'evidence': []})['output']['status'] == 'SUPPORTED'


def test_conflict_wire_schema_requires_all_input_ids():
    ids = [str(uuid4()) for _ in range(3)]
    def handler(request):
        body = json.loads(request.content)
        schema = body['text']['format']['schema']['properties']['chunk_ids']
        assert schema['minItems'] == schema['maxItems'] == 3
        assert schema['items']['enum'] == ids
        output = dict(relationship='CONSISTENT', chunk_ids=ids, explanation='Fixture')
        return httpx.Response(200, json={'status':'completed','output':[{'type':'message','content':[
            {'type':'output_text','text':json.dumps(output)}]}]})
    provider = OpenAITroubleshootingProvider(Settings(openai_api_key='test-secret'), httpx.MockTransport(handler))
    assert provider.complete('conflict', {'evidence':[{'chunk_id':cid} for cid in ids]})['output']['chunk_ids'] == ids


def test_review_wire_schema_requires_expected_count_and_known_ids():
    ids = [str(uuid4()) for _ in range(8)]
    def handler(request):
        schema = json.loads(request.content)['text']['format']['schema']
        assert schema['properties']['chunks']['minItems'] == schema['properties']['chunks']['maxItems'] == 8
        assert schema['$defs']['EvidenceRating']['properties']['chunk_id']['enum'] == ids
        output = dict(chunks=[dict(chunk_id=cid, relevance='NOT_RELEVANT', issue='fixture', reason='Fixture') for cid in ids],
                      strength='WEAK', missing_information=[])
        return httpx.Response(200, json={'status':'completed','output':[{'type':'message','content':[
            {'type':'output_text','text':json.dumps(output)}]}]})
    provider = OpenAITroubleshootingProvider(Settings(openai_api_key='test-secret'), httpx.MockTransport(handler))
    assert len(provider.complete('review', {'evidence':[{'chunk_id':cid} for cid in ids]})['output']['chunks']) == 8


@pytest.mark.parametrize('status,payload', [(429, {'error': 'test-secret'}), (200, {'status': 'incomplete'}),
    (200, {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]})])
def test_provider_errors_do_not_leak_credentials(status, payload):
    provider = OpenAITroubleshootingProvider(Settings(openai_api_key='test-secret'),
        httpx.MockTransport(lambda r: httpx.Response(status, json=payload)))
    with pytest.raises(TroubleshootingUnavailable) as error: provider.complete('verify', {})
    assert 'test-secret' not in str(error.value)


@pytest.fixture
def troubleshooting_db(inspection_db):
    engine, settings, sid, embedder = inspection_db
    initialize_troubleshooting(engine)
    return engine, settings, sid, embedder


@pytest.mark.integration
def test_session_visual_context_followup_persistence_and_no_ocr_vision(troubleshooting_db, monkeypatch):
    engine, settings, sid, embedder = troubleshooting_db
    upload(engine, settings, sid, view_label='front', user_note='Noise here')
    analyze_all(engine, sid, MockVision(), settings)
    service.update(engine, sid, TroubleshootingInput(reported_symptoms=['Motor overheating']))
    def forbidden(*a, **k): raise AssertionError('OCR/vision must not run')
    monkeypatch.setattr(equipment, 'identify', forbidden)
    monkeypatch.setattr('app.services.inspection_images.analyze_all', forbidden)
    captured = []
    def retriever(plan): captured.append(plan); return [evidence()]
    first = service.run(engine, sid, MockLLM(), embedder, settings, retriever)
    service.update(engine, sid, TroubleshootingInput(answer='Fan is spinning',
        measurements=[dict(name='temperature', value='92', unit='C', location='housing')], checks_completed=['Fan observed spinning']))
    second = service.run(engine, sid, MockLLM(), embedder, settings, retriever)
    assert 'corrosion' in captured[0]['semantic_query'] and 'Noise here' in captured[0]['semantic_query']
    assert 'Fan is spinning' in captured[1]['semantic_query'] and '92 C' in captured[1]['exact_keyword_terms']
    assert second['follow_up_answers'] == ['Fan is spinning']
    assert first['equipment'] == second['equipment'] and len(second['retrieved_evidence_history']) == 2
    rid = second['retrieved_evidence_history'][0]['run_id']
    from uuid import UUID
    assert 'audit' not in service.get_run(engine, sid, UUID(rid))
    assert service.get_run(engine, sid, UUID(rid), True)['audit']['calls']
    with Session(engine) as db:
        assert db.get(EquipmentSession, sid).confirmed_equipment_id == 'abb-acs880-01'


@pytest.mark.integration
@pytest.mark.parametrize('change', ['input', 'equipment', 'visual'])
def test_changes_during_run_discard_stale_answer(troubleshooting_db, change):
    engine, settings, sid, embedder = troubleshooting_db
    service.update(engine, sid, TroubleshootingInput(reported_symptoms=['Overheating']))
    changed = []
    def mutate(stage, payload):
        if changed: return
        changed.append(True)
        if change == 'input': service.update(engine, sid, TroubleshootingInput(answer='New observation'))
        elif change == 'equipment':
            with Session(engine) as db, db.begin(): db.get(EquipmentSession, sid).identification_revision += 1
        else:
            upload(engine, settings, sid, user_note='New information')
    with pytest.raises(equipment.StaleIdentification):
        service.run(engine, sid, MockLLM(mutate=mutate), embedder, settings, lambda p: [evidence()])
    state = service.get_state(engine, sid)
    assert state['current_primary_cause'] is None
    assert state['retrieved_evidence_history'][0]['status'] == 'stale'


@pytest.mark.integration
def test_provider_failure_persisted_without_fake_answer(troubleshooting_db):
    engine, settings, sid, embedder = troubleshooting_db
    class Failed:
        def complete(self, *args): raise RuntimeError('provider-secret')
    state = service.run(engine, sid, Failed(), embedder, settings, lambda p: [evidence()])
    assert state['result']['status'] == 'failed' and state['confidence'] == 'LOW'
    assert state['current_primary_cause'] is None and 'provider-secret' not in json.dumps(state)


@pytest.mark.integration
def test_api_update_symptom_followup_and_revision_conflict(troubleshooting_db, monkeypatch):
    engine, settings, sid, embedder = troubleshooting_db
    # The public route uses the database corpus, unlike explicitly injected
    # service retrievers. Seed genuine indexed coverage before mocking search.
    from test_retrieval import make_pdf
    from app.schemas.document import IngestRequest
    from app.services.ingestion import ingest
    make_pdf(settings.manuals_dir, 'api-fixture.pdf', 'Synthetic manual: restricted airflow may cause overheating.')
    ingest(engine, IngestRequest(filename='api-fixture.pdf', title='API fixture',
        equipment_model='ACS880', equipment_family='ACS880 Drives'), embedder, settings)
    app = FastAPI(); app.include_router(api.router)
    from conftest import authenticated_client
    authenticated_client(app, monkeypatch, engine, sid)
    monkeypatch.setattr(api, 'get_engine', lambda: engine)
    monkeypatch.setattr(api, 'get_settings', lambda: settings)
    monkeypatch.setattr(service, 'retrieve', lambda *args: [evidence()])
    app.dependency_overrides[api.get_troubleshooting_provider] = lambda: MockLLM()
    app.dependency_overrides[api.get_embedder] = lambda: embedder
    client = TestClient(app); root = f'/sessions/{sid}/troubleshooting'
    assert client.put(root, json={}).status_code == 200
    assert client.post(root + '/symptoms', json={'symptom': 'Motor overheating'}).status_code == 200
    assert client.post(root + '/run').json()['current_primary_cause']
    response = client.post(root + '/follow-up', json={'answer': 'Fan spinning'})
    assert response.status_code == 200 and response.json()['follow_up_answers'] == ['Fan spinning']
    assert client.put(root, json={'expected_revision': 0}).status_code == 409
    assert client.get(root).json()['equipment']['model'] == 'ACS880-01'


@pytest.mark.integration
def test_context_retrieval_uses_existing_filters_and_both_channels(troubleshooting_db):
    from test_retrieval import make_pdf
    from app.schemas.document import IngestRequest
    from app.services.ingestion import ingest
    from app.services.troubleshooting_query import retrieve
    engine, settings, sid, embedder = troubleshooting_db
    for name, model, family in [('drive', 'ACS880', 'ACS880 Drives'), ('other', 'OTHER', 'Other family')]:
        make_pdf(settings.manuals_dir, name + '.pdf', 'Synthetic fixture: overheating fault 5091 at terminal X13.')
        ingest(engine, IngestRequest(filename=name + '.pdf', title=name, equipment_model=model,
                                    equipment_family=family), embedder, settings)
    plan = construct_query(context(), embedder)
    rows = retrieve(engine, plan, embedder, settings)
    assert rows and all(r.equipment_model == 'ACS880' for r in rows)
    assert all(r.semantic_rank and r.keyword_rank for r in rows)
    assert any('5091' in r.chunk_text for r in rows)


@pytest.mark.corpus
def test_real_motor_demo_retrieval_and_verified_citations():
    import importlib.util
    from app.config import ROOT, get_settings
    from app.db.session import get_engine
    from app.services.embeddings import get_embedder
    from app.services.troubleshooting_query import retrieve
    spec = importlib.util.spec_from_file_location('step4_demo', ROOT / 'scripts/demo_troubleshooting.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    ctx = context()
    ctx.update(equipment={'manufacturer': 'ABB', 'model': 'induction motor', 'family': 'Induction Motors and Generators'},
               retrieval_filters={'equipment_model': None, 'equipment_family': 'Induction Motors and Generators'},
               visual_findings=[{'description': 'Heavy dust and dirt on cooling ventilation openings', 'visual_confidence': 'high'}])
    ctx['inputs']['reported_symptoms'] = ['Motor overheating']
    ctx['inputs']['confirmed_observations'] = ['Open-air cooling design confirmed in project documentation']
    settings, embedder = get_settings(), get_embedder()
    p = Pipeline(module.DemoLLM(), embedder, settings, lambda plan: retrieve(get_engine(), plan, embedder, settings))
    result = p.execute(ctx)
    assert result['primary_cause']['label'] == module.LABEL and result['confidence'] == 'MEDIUM'
    assert result['conflicts'][0]['relationship'] == 'COMPLEMENTARY'
    assert all(s['page_number'] == 89 and s['document_number'] == '3BFP 000 050 R0101' for s in result['sources'])
    retrieved = {e['chunk_id'] for e in p.audit['attempts'][0]['evidence']}
    assert all(cid in retrieved for c in result['technical_claims'] for cid in c['citation_chunk_ids'])


def test_call_budget_and_missing_input_confidence_policy():
    p = Pipeline(MockLLM(), Embedder(), Settings(troubleshooting_max_llm_calls=4), lambda plan: [evidence()])
    with pytest.raises(TroubleshootingUnavailable, match='budget'): p.execute(context())
    factors = dict(primary_supported=True, strong_evidence=True, strong_retrieval=True, conflict=False,
                   equipment_confirmed=True, low_visual_confidence=False, missing_count=0, partial=False)
    assert confidence(**factors) == 'HIGH'
    for key in ('primary_supported', 'strong_evidence'):
        assert confidence(**dict(factors, **{key: False})) == 'LOW'
    assert confidence(**dict(factors, missing_count=1)) == 'MEDIUM'
    assert confidence(**dict(factors, strong_retrieval=False)) == 'MEDIUM'


def test_partially_applicable_primary_cannot_borrow_high_confidence_from_other_chunk():
    class PartialPrimary(MockLLM):
        def complete(self, stage, payload):
            response = super().complete(stage, payload)
            if stage == 'review': response['output']['chunks'][0]['relevance'] = 'PARTIALLY_RELEVANT'
            return response
    _, result = pipeline(PartialPrimary(), rows=[evidence(1), evidence(2)])
    assert result['confidence'] == 'MEDIUM'


@pytest.mark.integration
def test_completed_result_becomes_stale_and_new_equipment_resets_inputs(troubleshooting_db):
    engine, settings, sid, embedder = troubleshooting_db
    service.update(engine, sid, TroubleshootingInput(reported_symptoms=['Overheating']))
    service.run(engine, sid, MockLLM(), embedder, settings, lambda p: [evidence()])
    upload(engine, settings, sid, user_note='New observation')
    assert service.get_state(engine, sid)['result']['status'] == 'stale'
    with Session(engine) as db, db.begin(): db.get(EquipmentSession, sid).identification_revision += 1
    assert service.get_state(engine, sid)['reported_symptoms'] == []
    state = service.update(engine, sid, TroubleshootingInput(reported_symptoms=['Different issue']))
    assert state['reported_symptoms'] == ['Different issue']
    assert len(state['retrieved_evidence_history']) == 1
