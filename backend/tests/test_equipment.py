from dataclasses import asdict
from io import BytesIO
import json
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ROOT
from app.db.init_equipment import initialize_equipment
from app.models.equipment import Equipment, EquipmentSession
from app.schemas.equipment import ConfirmEquipment
from app.services.equipment_matching import rank_equipment
from app.services.equipment_ocr import OCRResult, decode_image
from app.services.equipment_parsing import extract_identifiers, normalize_identifier, parse_fields
from app.services.equipment_sessions import (confirm, confirmed_search_request, create_session, get_state,
                                             identify, reject, StaleIdentification)

CATALOG = json.loads((ROOT / 'data/equipment_catalog.json').read_text())['equipment']
OCR_TEXT = 'ABB\nTYPE: ACS880-01-07A2-3\n400 V\n7.2 A\n3 kW\n50 Hz\nSERIAL: DEMO123456'


class MockOCR:
    """Explicit fixture provider; no mock-text endpoint in the production API."""
    def __init__(self, text=OCR_TEXT):
        self.text = text

    def extract(self, image):
        return OCRResult(self.text, 'mock-test-fixture')


def image_bytes():
    stream = BytesIO()
    Image.new('RGB', (300, 200), 'white').save(stream, format='PNG')
    return stream.getvalue()


def ocr_observation(text=OCR_TEXT, role='nameplate'):
    return {'raw_text': text, 'role': role, 'parsed': parse_fields(text)}


def test_parse_raw_and_structured_fields_without_invention():
    parsed = parse_fields(OCR_TEXT)
    assert parsed['fields'] == {'manufacturer': 'ABB', 'equipment_family': 'ACS880',
        'model_number': 'ACS880-01-07A2-3', 'type_code': 'ACS880-01-07A2-3', 'serial_number': 'DEMO123456',
        'voltage': '400 V', 'current': '7.2 A', 'power': '3 kW', 'frequency': '50 Hz', 'fault_display_code': None}
    assert parsed['raw_values']['model_number'] == 'ACS880-01-07A2-3'
    assert all(value is None for value in parse_fields('unreadable image')['fields'].values())
    assert parse_fields('Fault code: A4F6')['fields']['fault_display_code'] == 'A4F6'
    assert parse_fields('Serial number:\nVOLTAGE')['fields']['serial_number'] is None
    assert parse_fields('FAULT CODE')['fields']['fault_display_code'] is None


def test_conservative_normalization_preserves_raw():
    raw = 'acs 88O – O1-07A2-3'
    normalized = normalize_identifier(raw)
    assert normalized['raw'] == raw and normalized['normalized'] == 'ACS880-01-07A2-3'
    assert len(normalized['normalization_notes']) == 2
    assert normalize_identifier('SERIAL-OO123')['normalized'] == 'SERIAL-OO123'
    assert extract_identifiers(raw)[0]['raw'] == raw


def test_exact_match_and_family_match_levels():
    result = rank_equipment('ACS880-01', [], CATALOG)
    assert result['ranked_candidates'][0]['candidate_id'] == 'abb-acs880-01'
    assert result['ranked_candidates'][0]['match_level'] == 'HIGH'
    family = rank_equipment('ACS880', [], CATALOG)['ranked_candidates'][0]
    assert family['match_level'] == 'MEDIUM'
    assert 'subtype not established' in family['explanation']


def test_ocr_wins_over_conflicting_typed_family_and_requires_confirmation():
    result = rank_equipment('ACS580', [ocr_observation()], CATALOG)
    assert result['confirmation_status'] == 'SUGGESTED'
    top = result['ranked_candidates'][0]
    assert top['candidate_id'] == 'abb-acs880-01' and top['match_level'] == 'HIGH'
    assert any('ACS580' in warning for warning in result['mismatch_warnings'])


def test_no_match_and_closest_three_are_only_catalog_entries():
    result = rank_equipment('unrecognizable industrial equipment', [ocr_observation('')], CATALOG)
    assert result['confirmation_status'] == 'UNCONFIRMED' and not result['ranked_candidates']
    approximate = rank_equipment('ACS58', [], CATALOG)
    assert approximate['confirmation_status'] == 'UNCONFIRMED'
    assert len(approximate['ranked_candidates']) == 3
    assert {candidate['candidate_id'] for candidate in approximate['ranked_candidates']} == {item['id'] for item in CATALOG}
    unsupported = rank_equipment('ACS880-07', [], CATALOG)
    assert unsupported['confirmation_status'] == 'UNCONFIRMED'
    assert all(row['match_level'] == 'LOW' for row in unsupported['ranked_candidates'])


def test_secondary_equipment_image_and_normalization_do_not_claim_high():
    result = rank_equipment(None, [ocr_observation(role='equipment')], CATALOG)
    assert result['ranked_candidates'][0]['match_level'] == 'MEDIUM'
    corrected = rank_equipment(None, [ocr_observation('ACS88O-O1')], CATALOG)
    assert corrected['ranked_candidates'][0]['match_level'] == 'MEDIUM'
    assert not rank_equipment(None, [ocr_observation('')], CATALOG)['ranked_candidates']


def test_multiple_ocr_family_mismatch_is_visible():
    result = rank_equipment(None, [ocr_observation('ACS880-01'), ocr_observation('ACS580-01')], CATALOG)
    assert result['mismatch_warnings']
    assert result['ranked_candidates'][0]['match_level'] == 'MEDIUM'


def test_low_quality_recognition_downgrades_identification():
    observation = ocr_observation('ACS880-01')
    observation['lines'] = [{'text': 'ACS880-01', 'recognition_score': 0.55}]
    result = rank_equipment(None, [observation], CATALOG)
    assert result['ranked_candidates'][0]['match_level'] == 'MEDIUM'


def test_invalid_images_rejected():
    with pytest.raises(ValueError):
        decode_image(b'not an image')
    with pytest.raises(ValueError):
        decode_image(b'')


@pytest.fixture
def equipment_db(isolated_db):
    engine, _, _ = isolated_db
    initialize_equipment(engine)
    return engine


@pytest.mark.integration
def test_session_persistence_confirmation_rejection_and_invalidation(equipment_db):
    engine = equipment_db
    initial = create_session(engine)
    assert initial.confirmation_status == 'UNCONFIRMED'
    with pytest.raises(ValueError):
        confirmed_search_request(initial, 'fault tracing')
    suggested = identify(engine, initial.session_id, 'ACS580', [{'data': image_bytes(), 'role': 'nameplate'}], MockOCR())
    assert suggested.raw_ocr_text == OCR_TEXT
    assert suggested.parsed_ocr_fields['model_number'] == 'ACS880-01-07A2-3'
    assert get_state(engine, initial.session_id).model_dump() == suggested.model_dump()
    assert suggested.confirmed_equipment_id is None and suggested.retrieval_filters is None
    confirmed = confirm(engine, initial.session_id, ConfirmEquipment(equipment_id='abb-acs880-01', identification_revision=suggested.identification_revision))
    assert confirmed.confirmation_status == 'CONFIRMED'
    assert confirmed.confirmed_model == 'ACS880-01'
    persisted = get_state(engine, initial.session_id)
    assert persisted.confirmed_equipment_id == 'abb-acs880-01'
    assert confirmed_search_request(persisted, 'fault tracing').equipment_model == 'ACS880'
    assert confirmed_search_request(persisted, 'fault tracing').equipment_family == 'ACS880 Drives'
    with pytest.raises(StaleIdentification):
        confirm(engine, initial.session_id, ConfirmEquipment(equipment_id='abb-acs880-01', identification_revision=suggested.identification_revision))
    no_match = identify(engine, initial.session_id, None, [{'data': image_bytes()+b'unreadable'}], MockOCR(''))
    assert no_match.confirmation_status == 'UNCONFIRMED' and no_match.confirmed_equipment_id is None
    with pytest.raises(ValueError):
        confirm(engine, initial.session_id, ConfirmEquipment(equipment_id='not-in-catalog'))
    identified = identify(engine, initial.session_id, 'ACS880', [], MockOCR())
    rejected = reject(engine, initial.session_id)
    assert rejected.confirmation_status == 'REJECTED' and rejected.retrieval_filters is None
    with pytest.raises(ValueError):
        confirm(engine, initial.session_id, ConfirmEquipment(equipment_id='abb-acs880-01'))


@pytest.mark.integration
def test_api_multipart_identify_and_confirm(equipment_db, monkeypatch):
    from app.api import equipment as api
    from app.services.equipment_ocr import get_ocr_provider
    monkeypatch.setattr(api, 'get_engine', lambda: equipment_db)
    app = FastAPI()
    app.include_router(api.router)
    from conftest import authenticated_client
    authenticated_client(app, monkeypatch, equipment_db, None)
    app.dependency_overrides[get_ocr_provider] = lambda: MockOCR()
    with TestClient(app) as client:
        session_id = client.post('/sessions', json={'session_name': 'Equipment test'}).json()['session_id']
        path = f'/sessions/{session_id}/equipment'
        response = client.post(path + '/identify', data={'entered_equipment_text': 'ACS580'},
                               files=[('images', ('plate.png', image_bytes(), 'image/png'))])
        assert response.status_code == 200, response.text
        state = response.json()
        assert state['confidence'] == 'HIGH' and state['mismatch_warnings']
        confirmed = client.post(path + '/confirm', json={'equipment_id': 'abb-acs880-01', 'identification_revision': state['identification_revision']})
        assert confirmed.status_code == 200
        assert client.get(path).json()['confirmed_equipment_id'] == 'abb-acs880-01'
        assert client.post(path + '/confirm', json={'equipment_id': 'fabricated-model'}).status_code == 422
        assert client.post(path + '/identify', data={'image_roles': '["invalid"]'}, files=[('images', ('x.png', image_bytes()))]).status_code == 422
        assert client.post(path + '/identify', files=[('images', ('x.png', b'bad'))]).status_code == 422
        assert client.get(f'/sessions/{uuid4()}/equipment').status_code == 404


@pytest.mark.integration
def test_multiple_images_keep_sources_and_ambiguous_fields_null(equipment_db):
    class SequentialOCR:
        def __init__(self):
            self.texts = iter(['ABB\nACS880-01\n400 V', 'ABB\nACS580-01\n480 V'])

        def extract(self, image):
            return OCRResult(next(self.texts), 'mock-multi-image')

    state = create_session(equipment_db)
    state = identify(equipment_db, state.session_id, None,
                     [{'data': image_bytes(), 'role': 'nameplate'}, {'data': image_bytes()+b'other view', 'role': 'equipment'}],
                     SequentialOCR())
    assert len(state.ocr_results) == 2
    assert state.ocr_results[0]['raw_text'] == 'ABB\nACS880-01\n400 V'
    assert state.ocr_results[1]['raw_text'] == 'ABB\nACS580-01\n480 V'
    assert state.parsed_ocr_fields['voltage'] is None and state.parsed_ocr_fields['model_number'] is None
    assert state.confidence == 'MEDIUM' and state.confirmed_equipment_id is None
    assert any('voltage' in message for message in state.mismatch_warnings)


@pytest.mark.corpus
def test_confirmed_equipment_filters_existing_real_retrieval():
    from app.db.session import get_engine
    from app.services.embeddings import get_embedder
    from app.services.hybrid_search import search_all
    engine = get_engine()
    initialize_equipment(engine)
    state = create_session(engine)
    try:
        identified = identify(engine, state.session_id, 'ACS580', [{'data': image_bytes()}], MockOCR())
        confirmed = confirm(engine, state.session_id, ConfirmEquipment(equipment_id=identified.ranked_candidates[0]['candidate_id']))
        result = search_all(engine, confirmed_search_request(confirmed, 'fault tracing'), get_embedder())
        assert result['hybrid'] and result['semantic'] and result['keyword']
        for mode in result.values():
            assert all(item.equipment_model == 'ACS880' and item.equipment_family == 'ACS880 Drives' for item in mode)
        assert any(497 <= item.page_number <= 544 for item in result['hybrid'])
        identify(engine, state.session_id, 'ACS580-01', [], MockOCR())
        other = confirm(engine, state.session_id, ConfirmEquipment(equipment_id='abb-acs580-01'))
        absent = search_all(engine, confirmed_search_request(other, 'fault tracing'), get_embedder())
        assert all(not rows for rows in absent.values())  # Never broaden into ACS880 when a catalog family has no corpus.
    finally:
        with Session(engine) as session, session.begin():
            session.delete(session.get(EquipmentSession, state.session_id))


@pytest.mark.parametrize('weak_text', ['not sure', 'unknown', "won't run", '', 'something is wrong'])
def test_vague_text_never_degrades_valid_nameplate(weak_text):
    strong = rank_equipment('', [ocr_observation()], CATALOG)
    actual = rank_equipment(weak_text, [ocr_observation()], CATALOG)
    assert actual == strong
    assert actual['ranked_candidates'][0]['candidate_id'] == 'abb-acs880-01'
    assert actual['ranked_candidates'][0]['match_level'] == 'HIGH'
