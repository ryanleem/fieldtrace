import io
import json
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import inspection
from app.config import Settings
from app.db.init_equipment import initialize_equipment
from app.db.init_vision import initialize_vision
from app.models.vision import SessionImage, VisualFinding
from app.schemas.equipment import ConfirmEquipment
from app.schemas.vision import VisibleFinding, VisionResult
from app.services import equipment_sessions as equipment
from app.services import inspection_images as service
from app.services.visual_aggregation import aggregate
from app.services.visual_context import build_visual_retrieval_context, visual_search_request
from app.services.vision_provider import OpenAIVisionProvider, VisionImage, VISION_PROMPT, get_vision_provider


def photo(format='PNG'):
    buffer = io.BytesIO()
    Image.new('RGB', (32, 32), 'gray').save(buffer, format=format)
    return buffer.getvalue()


def finding(**changes):
    return dict(issue_type='corrosion', location='lower terminal enclosure',
                description='Visible orange-brown corrosion on the lower terminal enclosure.',
                severity='medium', visual_confidence='high', **changes)


class MockVision:
    def __init__(self, findings=None, callback=None, malformed=False):
        self.findings = [finding()] if findings is None else findings
        self.calls = []
        self.callback = callback
        self.malformed = malformed

    def analyze_equipment_image(self, image, context, *, strict=False):
        self.calls.append((context, strict))
        if self.callback:
            self.callback()
        return {'output': 'not json' if self.malformed else {'image_summary': 'Visible equipment surfaces.', 'findings': self.findings},
                'raw': {'provider': 'deterministic-test-mock', 'request_id': 'mock-1'}}


@pytest.fixture
def inspection_db(isolated_db, tmp_path):
    engine, settings, embedder = isolated_db
    settings.uploads_dir = tmp_path / 'uploads'
    initialize_equipment(engine)
    initialize_vision(engine)
    state = equipment.create_session(engine)
    equipment.identify(engine, state.session_id, 'ABB ACS880-01', [], None)
    equipment.confirm(engine, state.session_id, ConfirmEquipment(equipment_id='abb-acs880-01'))
    return engine, settings, state.session_id, embedder


def upload(engine, settings, sid, **kwargs):
    return service.upload_images(engine, sid, [dict(data=photo()+kwargs.pop('extra_bytes', b''), original_filename='../../name.png', **kwargs)], settings)[0]


def test_normalization_and_no_invented_box():
    f = VisibleFinding(**{**finding(), 'issue_type': 'rust'})
    assert f.issue_type == 'corrosion' and f.bounding_region is None
    assert VisibleFinding(**{**finding(), 'issue_type': 'odd_surface_texture'}).issue_type == 'unknown_visible_abnormality'


@pytest.mark.parametrize('field,value', [('severity', 'critical'), ('visual_confidence', 0.95),
    ('bounding_region', {'x': .9, 'y': .1, 'width': .2, 'height': .2}),
    ('description', 'Bearing is failing'), ('issue_type', 'internal_winding_damage'),
    ('description', 'Replace this component'), ('description', 'Safe to operate'),
    ('description', 'Electrical fault confirmed'), ('description', 'Overheating caused by excessive load')])
def test_invalid_and_diagnostic_output_rejected(field, value):
    with pytest.raises(ValueError):
        VisibleFinding(**{**finding(), field: value})


def test_provider_retry_and_failure():
    provider = MockVision(malformed=True)
    result, raw, error = service.run_vision(provider, VisionImage(photo(), 'image/png'), {})
    assert result is None and len(raw) == 2 and error
    assert [strict for _, strict in provider.calls] == [False, True]
    provider = MockVision([dict(finding(), description='Bearing failure detected')])
    assert service.run_vision(provider, VisionImage(photo(), 'image/png'), {})[0] is None


def test_strict_retry_can_recover():
    class Recover:
        def analyze_equipment_image(self, image, context, *, strict=False):
            return {'output': {'image_summary': 'No clear abnormality visible.', 'findings': []} if strict else '{', 'raw': {}}
    result, raw, error = service.run_vision(Recover(), VisionImage(photo(), 'image/png'), {})
    assert result.findings == [] and len(raw) == 2 and error is None


@pytest.mark.parametrize('format', ['PNG', 'JPEG', 'WEBP'])
def test_image_formats(format):
    assert service.validate_image(photo(format), Settings())[0].startswith('image/')


@pytest.mark.parametrize('data', [b'not an image', photo('GIF'), photo()[:40], b'x' * 1025])
def test_bad_image_bytes(data):
    with pytest.raises(ValueError):
        service.validate_image(data, Settings(max_inspection_image_bytes=1024))


def test_aggregation_preserves_location_and_equipment():
    sid = uuid4()
    rows = [dict(finding(), id=uuid4(), image_id=uuid4(), equipment_id='acs880') for _ in range(2)]
    rows[1]['location'] = 'Lower terminal housing'
    merged = aggregate(rows, sid)
    assert len(merged) == 1 and len(merged[0]['supporting_image_ids']) == 2
    for key, value in [('location', 'upper terminal housing'), ('equipment_id', 'acs580'), ('issue_type', 'crack')]:
        changed = [rows[0], dict(rows[1], **{key: value})]
        assert len(aggregate(changed, sid)) == 2
    assert len(aggregate([rows[0], dict(rows[1], image_id=rows[0]['image_id'])], sid)) == 2
    assert len(aggregate([dict(r, location='unknown') for r in rows], sid)) == 2


@pytest.mark.integration
def test_upload_metadata_limits_and_atomicity(inspection_db):
    engine, settings, sid, _ = inspection_db
    record = upload(engine, settings, sid, view_label='close_up', user_note='This area gets hot')
    assert record['session_id'] == sid and record['equipment_id'] == 'abb-acs880-01'
    assert record['view_label'] == 'close_up' and record['user_note'] == 'This area gets hot'
    assert record['original_filename'] == '../../name.png' and record['created_at']
    with Session(engine) as db:
        row = db.get(SessionImage, record['id'])
        path = service.image_path(settings, row)
        assert path.is_file() and path.name == str(row.id) + '.png'
    with pytest.raises(ValueError):
        service.upload_images(engine, sid, [dict(data=photo()), dict(data=b'bad')], settings)
    assert len(service.list_images(engine, sid)) == 1
    settings.max_inspection_images = 1
    with pytest.raises(ValueError):
        upload(engine, settings, sid, extra_bytes=b'different')
    assert len(list(settings.uploads_dir.rglob('*.png'))) == 1


@pytest.mark.integration
def test_analysis_raw_notes_confirmation_and_multi_view(inspection_db):
    engine, settings, sid, _ = inspection_db
    before = equipment.get_state(engine, sid)
    one = upload(engine, settings, sid, view_label='front', user_note='I hear noise here')
    two = upload(engine, settings, sid, view_label='close_up', extra_bytes=b'other angle')
    provider = MockVision()
    result = service.analyze_all(engine, sid, provider, settings)
    assert len(result['aggregated_visual_findings']) == 1
    assert set(result['aggregated_visual_findings'][0]['supporting_image_ids']) == {str(one['id']), str(two['id'])}
    assert provider.calls[0][0]['model'] == 'ACS880-01'
    assert equipment.get_state(engine, sid) == before
    state = service.visual_state(engine, sid, include_raw=True)
    assert state['uploaded_images'][0]['raw_vision_results'][0]['attempts'][0]['raw']['request_id'] == 'mock-1'
    assert all('noise' not in f['description'] and f['bounding_region'] is None for f in state['normalized_visual_findings'])
    assert service.analyze_all(engine, sid, provider, settings)['results'] == []
    service.analyze_image(engine, sid, one['id'], provider, settings)
    assert len(provider.calls) == 2  # successful repeat is idempotent


@pytest.mark.integration
def test_empty_failed_and_cross_session(inspection_db):
    engine, settings, sid, _ = inspection_db
    record = upload(engine, settings, sid)
    other = equipment.create_session(engine).session_id
    with pytest.raises(equipment.SessionNotFound):
        service.analyze_image(engine, other, record['id'], MockVision(), settings)
    result = service.analyze_image(engine, sid, record['id'], MockVision(malformed=True), settings)
    assert result['image']['analysis_status'] == 'failed' and result['findings'] == []
    result = service.analyze_image(engine, sid, record['id'], MockVision([]), settings)
    assert result['image']['analysis_status'] == 'no_clear_abnormality' and result['findings'] == []


@pytest.mark.integration
def test_equipment_change_during_analysis_discards_findings(inspection_db):
    engine, settings, sid, _ = inspection_db
    record = upload(engine, settings, sid)
    provider = MockVision(callback=lambda: equipment.reject(engine, sid))
    result = service.analyze_image(engine, sid, record['id'], provider, settings)
    assert result['image']['analysis_status'] == 'failed' and result['findings'] == []
    assert equipment.get_state(engine, sid).confirmation_status == 'REJECTED'
    assert service.visual_state(engine, sid, True)['uploaded_images'][0]['raw_vision_results']


@pytest.mark.integration
def test_context_builds_existing_search_request(inspection_db):
    engine, settings, sid, embedder = inspection_db
    record = upload(engine, settings, sid, user_note='Oil yesterday')
    service.analyze_image(engine, sid, record['id'], MockVision(), settings)
    context = build_visual_retrieval_context(sid, engine)
    assert context['text'] == 'ABB ACS880-01; visible corrosion at lower terminal enclosure'
    assert 'Oil' not in context['text'] and context['user_notes'][0]['source'] == 'user_report'
    request, omitted = visual_search_request(context, embedder)
    assert request.equipment_model == 'ACS880' and omitted == []
    from app.services.hybrid_search import search_all
    result = search_all(engine, request, embedder, settings)
    assert 'hybrid' in result


@pytest.mark.integration
def test_api_upload_analyze_get_and_bad_metadata(inspection_db, monkeypatch):
    engine, settings, sid, _ = inspection_db
    monkeypatch.setattr(inspection, 'get_engine', lambda: engine)
    monkeypatch.setattr(inspection, 'get_settings', lambda: settings)
    app = FastAPI()
    app.include_router(inspection.router)
    from conftest import authenticated_client
    authenticated_client(app, monkeypatch, engine, sid)
    app.dependency_overrides[get_vision_provider] = lambda: MockVision()
    with TestClient(app) as client:
        files = [('images', ('front.png', photo(), 'image/png')), ('images', ('detail.png', photo()+b'detail', 'image/png'))]
        response = client.post(f'/sessions/{sid}/images', files=files,
                               data={'view_labels': '["front","close_up"]', 'user_notes': '[null,"Noise here"]'})
        assert response.status_code == 201, response.text
        assert len(response.json()) == 2
        assert next(i for i in client.get(f'/sessions/{sid}/images').json() if i['id'] == response.json()[1]['id'])['user_note'] == 'Noise here'
        assert client.post(f'/sessions/{sid}/images/analyze-all').status_code == 200
        state = client.get(f'/sessions/{sid}/visual-findings').json()
        assert len(state['normalized_visual_findings']) == 2
        assert 'raw_vision_results' not in state['uploaded_images'][0]
        assert client.get(f'/sessions/{sid}/visual-context').json()['equipment']['model'] == 'ACS880-01'
        assert client.post(f'/sessions/{sid}/images', files=files, data={'view_labels': '["bad"]'}).status_code == 422
        assert client.post(f'/sessions/{sid}/images', files={'images': ('bad.gif', photo('GIF'), 'image/png')}).status_code == 422


def test_openai_wire_contract_mocked():
    def handler(request):
        body = json.loads(request.content)
        assert body['store'] is False and body['text']['format']['strict'] is True
        assert body['input'][0]['content'][1]['image_url'].startswith('data:image/png;base64,')
        assert 'orientation_only' in body['input'][0]['content'][0]['text']
        assert body['instructions'] == VISION_PROMPT
        return httpx.Response(200, json={'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': '{"image_summary":"No clear abnormality visible.","findings":[]}'}]}]})
    provider = OpenAIVisionProvider(Settings(openai_api_key='test-not-a-secret'), httpx.MockTransport(handler))
    result, raw, error = service.run_vision(provider, VisionImage(photo(), 'image/png'), {'view_label': 'front'})
    assert not result.findings and not error and raw


@pytest.mark.integration
def test_diagnostic_attempt_preserved_only_in_audit(inspection_db):
    engine, settings, sid, _ = inspection_db
    record = upload(engine, settings, sid)
    provider = MockVision([dict(finding(), description='Internal winding damage detected')])
    result = service.analyze_image(engine, sid, record['id'], provider, settings)
    assert result['image']['analysis_status'] == 'failed' and result['findings'] == []
    state = service.visual_state(engine, sid)
    assert state['aggregated_visual_findings'] == []
    assert 'winding' not in json.dumps(state, default=str)
    assert 'winding' in json.dumps(service.visual_state(engine, sid, True), default=str)


@pytest.mark.integration
def test_unconfirmed_images_and_later_confirmation(inspection_db):
    engine, settings, _, _ = inspection_db
    sid = equipment.create_session(engine).session_id
    record = upload(engine, settings, sid)
    assert record['equipment_id'] is None
    provider = MockVision()
    service.analyze_image(engine, sid, record['id'], provider, settings)
    assert provider.calls[0][0]['model'] is None
    equipment.identify(engine, sid, 'ACS880-01', [], None)
    equipment.confirm(engine, sid, ConfirmEquipment(equipment_id='abb-acs880-01'))
    assert build_visual_retrieval_context(sid, engine)['visual_findings'] == []
    # Pending unconfirmed uploads can acquire the current confirmation at analysis.
    second = upload(engine, settings, sid, extra_bytes=b'confirmed view')
    service.analyze_image(engine, sid, second['id'], provider, settings)
    assert len(build_visual_retrieval_context(sid, engine)['visual_findings']) == 1


@pytest.mark.integration
def test_analysis_lease_and_retry_after_missing_file(inspection_db):
    engine, settings, sid, _ = inspection_db
    record = upload(engine, settings, sid)
    with Session(engine) as db:
        service.image_path(settings, db.get(SessionImage, record['id'])).unlink()
    provider = MockVision()
    assert service.analyze_image(engine, sid, record['id'], provider, settings)['image']['analysis_status'] == 'failed'
    assert provider.calls == []


def test_query_budget_reports_omissions():
    class SmallEncoder:
        max_tokens = 12
        def token_count(self, value):
            return len(value.split())
    context = dict(equipment={'manufacturer': 'ABB', 'model': 'ACS880-01'},
                   retrieval_filters={'equipment_model': 'ACS880', 'equipment_family': 'ACS880 Drives'},
                   visual_findings=[dict(aggregated_finding_id=str(i), issue_type='corrosion', location='lower terminal enclosure') for i in range(10)])
    request, omitted = visual_search_request(context, SmallEncoder())
    assert len(omitted) == 9 and SmallEncoder().token_count(request.query) <= 12


def test_adapter_cannot_invent_localization():
    provider = MockVision([dict(finding(), bounding_region={'x': .1, 'y': .2, 'width': .3, 'height': .4})])
    assert service.run_vision(provider, VisionImage(photo(), 'image/png'), {})[0] is None
    provider.supports_localization = True
    assert service.run_vision(provider, VisionImage(photo(), 'image/png'), {})[0].findings[0].bounding_region.x == .1


def test_provider_http_errors_redact_response_details():
    def handler(request):
        return httpx.Response(429, json={'error': {'message': 'sensitive example payload'}})
    provider = OpenAIVisionProvider(Settings(openai_api_key='test-not-a-secret'), httpx.MockTransport(handler))
    result, raw, error = service.run_vision(provider, VisionImage(photo(), 'image/png'), {})
    assert result is None and raw == [] and error == 'Vision provider request failed (429)'


def test_bounds_and_pixel_limit():
    valid = dict(finding(), bounding_region={'x': .1, 'y': .2, 'width': .3, 'height': .4})
    assert VisibleFinding(**valid).bounding_region.x == .1
    with pytest.raises(ValueError, match='pixel'):
        service.validate_image(photo(), Settings(max_inspection_image_pixels=10))


@pytest.mark.corpus
def test_visual_context_reaches_real_abb_corpus(tmp_path):
    from app.db.session import get_engine
    from app.services.embeddings import get_embedder
    from app.services.hybrid_search import search_all
    from app.models.equipment import EquipmentSession
    engine = get_engine()
    initialize_equipment(engine)
    initialize_vision(engine)
    sid = equipment.create_session(engine).session_id
    settings = Settings(uploads_dir=tmp_path / 'uploads')
    try:
        equipment.identify(engine, sid, 'ACS880-01', [], None)
        equipment.confirm(engine, sid, ConfirmEquipment(equipment_id='abb-acs880-01'))
        record = upload(engine, settings, sid)
        provider = MockVision([dict(finding(), issue_type='dust_buildup', location='ventilation openings', description='Visible dust buildup around ventilation openings.')])
        service.analyze_image(engine, sid, record['id'], provider, settings)
        context = build_visual_retrieval_context(sid, engine)
        request, omitted = visual_search_request(context, get_embedder())
        result = search_all(engine, request, get_embedder())
        assert result['hybrid'] and result['semantic'] and not omitted
        assert all(row.equipment_model == 'ACS880' and row.equipment_family == 'ACS880 Drives' for rows in result.values() for row in rows)
        assert all(row.page_number > 0 and row.citation_url for row in result['hybrid'])
    finally:
        with Session(engine) as db, db.begin():
            db.delete(db.get(EquipmentSession, sid))
