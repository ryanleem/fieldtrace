from dataclasses import asdict
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.equipment import Equipment, EquipmentSession
from app.schemas.equipment import EquipmentState
from app.services.equipment_fusion import fuse_identity
from app.services.equipment_ocr import decode_image
from app.services.equipment_parsing import parse_fields


class SessionNotFound(LookupError):
    pass


class StaleIdentification(ValueError):
    pass


def load_session(session, session_id, lock=False):
    query = select(EquipmentSession).where(EquipmentSession.id == session_id)
    if lock:
        query = query.with_for_update()
    record = session.scalar(query)
    if record is None:
        raise SessionNotFound('Session not found')
    return record


def serialize(session, record):
    equipment = session.get(Equipment, record.confirmed_equipment_id) if record.confirmed_equipment_id else None
    candidates = record.ranked_candidates
    selected = next((item for item in candidates if item['candidate_id'] == record.confirmed_equipment_id), None)
    if record.confirmation_status == 'CONFIRMED':
        prompt = None
    elif record.confirmation_status == 'SUGGESTED':
        prompt = f"Did you mean ABB {candidates[0]['candidate_model']}? Confirm the catalog model before using equipment filters."
    else:
        prompt = 'Equipment is unconfirmed. Provide a clearer nameplate image or an exact model number.'
    if record.confirmation_status!='CONFIRMED' and record.identification_evidence.get('summary'):
        prompt=record.identification_evidence['summary']['to_confirm']
    return EquipmentState(
        identification=record.identification_evidence.get('summary', {}),
        session_id=record.id, entered_equipment_text=record.entered_equipment_text,
        raw_ocr_text=record.raw_ocr_text, parsed_ocr_fields=record.parsed_ocr_fields,
        ocr_results=record.ocr_results, input_identifiers=record.input_identifiers,
        ranked_candidates=candidates, selected_candidate=record.selected_candidate,
        confirmed_equipment_id=record.confirmed_equipment_id, confirmation_status=record.confirmation_status,
        identification_revision=record.identification_revision, mismatch_warnings=record.mismatch_warnings,
        confidence=record.identification_evidence.get('summary', {}).get('confidence') or (selected['match_level'] if selected else (candidates[0]['match_level'] if candidates else None)), confirmation_prompt=prompt,
        confirmed_equipment_family=equipment.equipment_family if equipment else None,
        confirmed_model=equipment.model_name if equipment else None,
        retrieval_filters={'equipment_model': equipment.retrieval_model, 'equipment_family': equipment.retrieval_family} if equipment else None,
    )


def create_session(engine):
    with Session(engine) as session, session.begin():
        record = EquipmentSession()
        session.add(record)
        session.flush()
        return serialize(session, record)


def get_state(engine, session_id):
    with Session(engine) as session:
        return serialize(session, load_session(session, session_id))


def identify(engine, session_id, entered_text, images, provider, visual_provider=None):
    if len(images) > 30:
        raise ValueError('Select at most thirty identification images')
    if entered_text is not None and len(entered_text) > 500:
        raise ValueError('Equipment text must be at most 500 characters')
    # Read revision before expensive OCR; stale concurrent identify/confirm is rejected.
    with Session(engine) as session:
        previous = load_session(session, session_id)
        previous_revision = previous.identification_revision
        cached = {(r.get("sha256"), r.get("role")): r for r in previous.ocr_results}
        old_evidence = previous.identification_evidence
        catalog = [{column.name: getattr(row, column.name) for column in Equipment.__table__.columns}
                   for row in session.scalars(select(Equipment)).all()]
    results = []
    prepared = []
    seen = set()
    from io import BytesIO
    from app.services.vision_provider import VisionImage
    for image in images:
        digest = hashlib.sha256(image['data']).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        index = len(results)
        role = image.get('role', 'nameplate')
        if role not in {'nameplate', 'equipment'}:
            raise ValueError('Image role must be nameplate or equipment')
        decoded = decode_image(image['data'])
        result_dict = dict(cached[(digest, role)]) if (digest, role) in cached else asdict(provider.extract(decoded))
        stream = BytesIO()
        decoded = decoded.convert('RGB')
        decoded.thumbnail((1800,1800))
        decoded.save(stream, format='JPEG', quality=90)
        prepared.append(VisionImage(stream.getvalue(), 'image/jpeg'))
        result_dict.update(image_index=index, role=role,
                           sha256=hashlib.sha256(image['data']).hexdigest(),
                           processed_image_size=list(decoded.size),
                           parsed=parse_fields(result_dict['raw_text']))
        results.append(result_dict)
    visual = None
    error = None
    baseline = fuse_identity(entered_text, results, catalog)
    strong_plate = any(s['source'].startswith('nameplate') and s['points']>=90
                       for c in baseline['ranked_candidates'] for s in c['matched_signals'])
    if visual_provider and prepared and not strong_plate:
        try:
            hashes = [r['sha256'] for r in results]
            visual = old_evidence.get('visual') if hashes==old_evidence.get('selected_image_hashes') else None
            visual = visual or visual_provider.extract(prepared, catalog, results)
        except Exception:
            error = 'Visual identification unavailable. Readable text is still shown; try clearer photos or retry identification.'
    ranking = fuse_identity(entered_text, results, catalog, visual)
    if error:
        ranking['identification_evidence']['summary']['provider_error'] = error
    raw_text = '\n\n'.join(result['raw_text'] for result in results)
    # Aggregate only unambiguous fields; per-image originals always remain available.
    parsed = {}
    keys = list(parse_fields('')['fields'])
    for key in keys:
        values = {result['parsed']['fields'][key] for result in results if result['parsed']['fields'][key] is not None}
        parsed[key] = next(iter(values)) if len(values) == 1 else None
        if len(values) > 1:
            ranking['mismatch_warnings'].append(f'Different {key} values detected across images; aggregate field left null.')
    with Session(engine) as session, session.begin():
        record = load_session(session, session_id, lock=True)
        if record.identification_revision != previous_revision:
            raise StaleIdentification('Session changed during OCR; reload current state and retry.')
        record.entered_equipment_text = entered_text
        record.raw_ocr_text = raw_text
        record.parsed_ocr_fields = parsed
        record.ocr_results = results
        for key, value in ranking.items():
            setattr(record, key, value)
        record.identification_revision += 1
        record.selected_candidate = ranking['ranked_candidates'][0]['candidate_id'] if ranking['confirmation_status'] == 'SUGGESTED' else None
        record.confirmed_equipment_id = None  # New evidence requires fresh explicit confirmation.
        session.flush()
        return serialize(session, record)


def confirm(engine, session_id, request):
    with Session(engine) as session, session.begin():
        record = load_session(session, session_id, lock=True)
        if request.identification_revision is not None and request.identification_revision != record.identification_revision:
            raise StaleIdentification('Identification has changed; review the latest candidates before confirmation.')
        if record.confirmation_status == 'REJECTED':
            raise ValueError('Run identification again before confirming a rejected session')
        if request.equipment_id not in {item['candidate_id'] for item in record.ranked_candidates}:
            raise ValueError('Confirm only a candidate returned by the current identification')
        candidate=next(item for item in record.ranked_candidates if item['candidate_id']==request.equipment_id)
        if candidate.get('confirmable') is False:
            raise ValueError('Family-level evidence does not establish this subtype; provide a readable model label or exact model text')
        if session.get(Equipment, request.equipment_id) is None:
            raise ValueError('Equipment is not in the prototype catalog')
        record.selected_candidate = request.equipment_id
        record.confirmed_equipment_id = request.equipment_id
        record.confirmation_status = 'CONFIRMED'
        # Increment to invalidate in-flight OCR and old confirmation payloads.
        record.identification_revision += 1
        session.flush()
        return serialize(session, record)


def reject(engine, session_id):
    with Session(engine) as session, session.begin():
        record = load_session(session, session_id, lock=True)
        record.confirmed_equipment_id = None
        record.selected_candidate = None
        record.confirmation_status = 'REJECTED'
        record.identification_revision += 1
        session.flush()
        return serialize(session, record)


def confirmed_search_request(state, query, top_k=5):
    from app.schemas.search import SearchRequest
    if state.confirmation_status != 'CONFIRMED' or not state.retrieval_filters:
        raise ValueError('Explicit equipment confirmation is required before using session retrieval filters')
    return SearchRequest(query=query, top_k=top_k, **state.retrieval_filters)
