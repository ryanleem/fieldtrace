"""Provider contracts: no paid calls, same parsing and session integration."""
import json

import httpx
import pytest

from app.config import Settings
from app.services import vision_provider as adapters
from app.services.inspection_images import run_vision
from test_vision import photo, finding, inspection_db, upload


def response(output=None, finish='STOP'):
    output = output or {'image_summary': 'No obvious visible abnormality detected in this image.', 'findings': []}
    return {'modelVersion': 'gemini-2.5-flash', 'candidates': [{'finishReason': finish,
            'content': {'parts': [{'text': json.dumps(output)}]}}]}


def provider(handler):
    return adapters.GeminiVisionProvider(
        Settings(_env_file=None, gemini_api_key='test-only'), httpx.MockTransport(handler))


def run(adapter):
    return run_vision(adapter, adapters.VisionImage(photo(), 'image/png'),
                      {'view_label': 'close_up', 'user_note': 'bearing failure reported by user'})


def test_gemini_wire_and_normalization():
    def handler(request):
        body = json.loads(request.content)
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert request.url.path.endswith('/gemini-2.5-flash:generateContent')
        assert not request.url.query and request.headers['x-goog-api-key'] == 'test-only'
        assert 'Authorization' not in request.headers
        assert body['systemInstruction']['parts'][0]['text'] == adapters.VISION_PROMPT
        parts = body['contents'][0]['parts']
        assert json.loads(parts[0]['text'])['orientation_only']['view_label'] == 'close_up'
        assert parts[1]['inlineData']['mimeType'] == 'image/png'
        assert parts[1]['inlineData']['data']
        config = body['generationConfig']
        assert config['responseMimeType'] == 'application/json'
        schema = config['responseJsonSchema']['$defs']['VisibleFinding']['properties']
        assert schema['bounding_region'] == {'type': 'null'}
        assert schema['severity']['enum'] == ['low', 'medium', 'high']
        return httpx.Response(200, json=response({'image_summary': 'Visible surface deposits.',
            'findings': [dict(finding(), issue_type='rust')]}))
    result, raw, error = run(provider(handler))
    assert not error and result.findings[0].issue_type == 'corrosion'
    assert result.findings[0].bounding_region is None
    assert raw[0]['raw']['modelVersion'] == 'gemini-2.5-flash'
    assert 'bearing' not in result.model_dump_json()


def test_gemini_clean_image_is_not_health_claim():
    result, _, error = run(provider(lambda r: httpx.Response(200, json=response())))
    assert not error and result.findings == []
    assert result.image_summary == 'No obvious visible abnormality detected in this image.'


@pytest.mark.parametrize('payload', [response(finish='MAX_TOKENS'), response(finish='SAFETY'),
    {'promptFeedback': {'blockReason': 'SAFETY'}}, {'candidates': []},
    response({'image_summary': 'Visible equipment.', 'findings': [dict(finding(), description='Internal short circuit')]}),
    response({'image_summary': 'Visible equipment.', 'findings': [dict(finding(), description='Winding failure')]}),
    response({'image_summary': 'Visible equipment.', 'findings': [dict(finding(), severity='critical')]}),
    response({'image_summary': 'Visible equipment.', 'findings': [dict(finding(), bounding_region={'x': .1, 'y': .1, 'width': .2, 'height': .2})]})])
def test_gemini_rejects_partial_blocked_and_out_of_scope(payload):
    result, raw, error = run(provider(lambda r: httpx.Response(200, json=payload)))
    assert result is None and error and len(raw) == 2


def test_gemini_strict_retry():
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        payload = response()
        if len(calls) == 1:
            payload['candidates'][0]['content']['parts'][0]['text'] = '{'
        return httpx.Response(200, json=payload)
    result, raw, error = run(provider(handler))
    assert result is not None and not error and len(raw) == 2
    assert 'Strict retry' in calls[1]['systemInstruction']['parts'][0]['text']


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_gemini_http_failures_no_findings_or_secret_leak(status):
    result, raw, error = run(provider(lambda r: httpx.Response(status, json={'error': {'message': 'test-only secret payload'}})))
    assert result is None and raw == [] and error == f'Gemini vision request failed ({status})'


def test_gemini_connection_failure():
    def handler(request):
        raise httpx.ReadTimeout('test-only secret payload', request=request)
    assert run(provider(handler)) == (None, [], 'Gemini vision request failed (connection)')


def test_gemini_missing_key_and_settings_redaction():
    settings = Settings(_env_file=None, gemini_api_key=None)
    def forbidden(request):
        pytest.fail('Missing key must not make an HTTP request')
    assert run(adapters.GeminiVisionProvider(settings, httpx.MockTransport(forbidden)))[2] == 'Set GEMINI_API_KEY to run vision analysis'
    settings.gemini_api_key = 'test-only-secret'
    assert 'test-only-secret' not in repr(settings)
    assert 'gemini_api_key' not in settings.model_dump()


def test_provider_selection_and_independent_models(monkeypatch):
    monkeypatch.setenv('VISION_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_VISION_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('VISION_MODEL', 'gpt-4.1-mini-2025-04-14')
    settings = Settings(_env_file=None)
    monkeypatch.setattr(adapters, 'get_settings', lambda: settings)
    assert isinstance(adapters.get_vision_provider(), adapters.GeminiVisionProvider)
    assert adapters.configured_vision_model(settings) == 'gemini-2.5-flash'
    settings.vision_provider = 'openai'
    assert isinstance(adapters.get_vision_provider(), adapters.OpenAIVisionProvider)
    assert adapters.configured_vision_model(settings) == 'gpt-4.1-mini-2025-04-14'
    settings.vision_provider = 'invalid'
    with pytest.raises(adapters.VisionUnavailable):
        adapters.get_vision_provider()


def test_gemini_unknown_taxonomy_normalizes_without_guessing():
    result, _, error = run(provider(lambda r: httpx.Response(200, json=response(
        {'image_summary': 'Visible surface.', 'findings': [dict(finding(), issue_type='odd_surface_texture')]}))))
    assert not error and result.findings[0].issue_type == 'unknown_visible_abnormality'


def test_gemini_invalid_http_json_is_clean_failure():
    assert run(provider(lambda r: httpx.Response(200, text='not json'))) == (
        None, [], 'Gemini vision request failed (connection)')


@pytest.mark.integration
def test_gemini_persists_source_and_aggregates_without_changing_confirmation(inspection_db):
    from app.services import inspection_images as images, equipment_sessions as equipment
    engine, settings, sid, _ = inspection_db
    before = equipment.get_state(engine, sid)
    first = upload(engine, settings, sid, view_label='front')
    second = upload(engine, settings, sid, view_label='close_up', user_note='Noise here')
    adapter = provider(lambda r: httpx.Response(200, json=response({'image_summary': 'Visible deposits.', 'findings': [finding()]})))
    result = images.analyze_all(engine, sid, adapter, settings)
    assert equipment.get_state(engine, sid) == before
    assert set(result['aggregated_visual_findings'][0]['supporting_image_ids']) == {str(first['id']), str(second['id'])}
    state = images.visual_state(engine, sid, include_raw=True)
    assert all(f['source'] == 'vision_model' for f in state['normalized_visual_findings'])
    assert len(state['normalized_visual_findings']) == 2
    assert state['uploaded_images'][0]['raw_vision_results'][0]['attempts'][0]['raw']['modelVersion'] == 'gemini-2.5-flash'
