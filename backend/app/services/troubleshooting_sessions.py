"""Additive diagnostic state with revision checks around slow external calls."""
import hashlib
import json
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.equipment import Equipment
from app.models.vision import AggregatedVisualFinding, SessionImage
from app.models.troubleshooting import TroubleshootingSession, TroubleshootingRun
from app.services.equipment_sessions import load_session, StaleIdentification, SessionNotFound
from app.services.troubleshooting_pipeline import Pipeline, insufficient
from app.services.troubleshooting_query import retrieve

FIELDS = ('reported_symptoms', 'technician_notes', 'measurements', 'checks_completed',
          'ruled_out_causes', 'confirmed_observations', 'follow_up_answers')


def state_row(db, owner):
    row = db.get(TroubleshootingSession, owner.id)
    if row is None:
        row = TroubleshootingSession(session_id=owner.id, equipment_revision=owner.identification_revision,
                                     revision=0, inputs={k: [] for k in FIELDS}, current={})
        db.add(row)
        db.flush()
    return row


def snapshot(db, owner, row):
    equipment = db.get(Equipment, owner.confirmed_equipment_id) if owner.confirmed_equipment_id else None
    findings = db.scalars(select(AggregatedVisualFinding).where(
        AggregatedVisualFinding.session_id == owner.id,
        AggregatedVisualFinding.equipment_id == owner.confirmed_equipment_id).order_by(AggregatedVisualFinding.id)).all()
    notes = db.scalars(select(SessionImage).where(SessionImage.session_id == owner.id,
        SessionImage.equipment_id == owner.confirmed_equipment_id).order_by(SessionImage.id)).all()
    return dict(session_id=str(owner.id), equipment_revision=owner.identification_revision,
        revision=row.revision, inputs=row.inputs,
        equipment=dict(manufacturer=equipment.manufacturer, model=equipment.model_name,
                       family=equipment.equipment_family) if equipment else None,
        retrieval_filters=dict(equipment_model=equipment.retrieval_model or None,
                               equipment_family=equipment.retrieval_family) if equipment else {},
        ocr_text=(owner.raw_ocr_text or '')[:8000],
        visual_findings=[dict(aggregated_finding_id=str(f.id), issue_type=f.issue_type,
            location=f.location, description=f.description, visual_confidence=f.visual_confidence,
            supporting_image_ids=f.supporting_image_ids) for f in findings],
        image_user_notes=[dict(image_id=str(i.id), note=i.user_note, source='user_report')
                          for i in notes if i.user_note])


def fingerprint(context):
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()


def update(engine, session_id, payload):
    with Session(engine) as db, db.begin():
        owner = load_session(db, session_id, lock=True)
        row = state_row(db, owner)
        if payload.expected_revision is not None and payload.expected_revision != row.revision:
            raise StaleIdentification('Troubleshooting inputs changed; reload session')
        data = dict(row.inputs) if row.equipment_revision == owner.identification_revision else {k: [] for k in FIELDS}
        values = payload.model_dump(exclude={'expected_revision', 'answer'})
        if payload.answer:
            values['follow_up_answers'] = [payload.answer]
        for key, items in values.items():
            data[key] = list(data.get(key, []))
            for item in items:
                if item not in data[key]: data[key].append(item)
            if len(data[key]) > 60:
                raise ValueError('Maximum 60 entries per session input field')
        row.inputs, row.current = data, {}
        row.equipment_revision = owner.identification_revision
        row.revision += 1
        row.run_token = None
    return get_state(engine, session_id)


def get_state(engine, session_id):
    with Session(engine) as db, db.begin():
        owner = load_session(db, session_id, lock=True)
        row = state_row(db, owner)
        context = snapshot(db, owner, row)
        stale = row.equipment_revision != owner.identification_revision or (
            row.current and row.current.get('context_fingerprint') != fingerprint(context))
        result = insufficient(context, 'stale' if stale else 'not_run') if stale or not row.current else row.current['result']
        runs = db.scalars(select(TroubleshootingRun).where(TroubleshootingRun.session_id == session_id)
                          .order_by(TroubleshootingRun.created_at)).all()
        return dict(session_id=str(session_id), revision=row.revision, equipment=context['equipment'],
            **({k: [] for k in FIELDS} if stale and row.equipment_revision != owner.identification_revision else row.inputs),
            result=result, current_primary_cause=result['primary_cause'], alternatives=result['alternative_causes'],
            actions=result['recommended_actions'], next_question=result['next_question'],
            confidence=result['confidence'], conflicts=result['conflicts'],
            current_alternative_causes=result['alternative_causes'], current_recommended_actions=result['recommended_actions'],
            current_next_question=result['next_question'], current_confidence=result['confidence'], current_conflicts=result['conflicts'],
            retrieved_evidence_history=[dict(run_id=str(r.id), status=r.status,
                created_at=r.created_at.isoformat(), sources=r.final.get('sources', [])) for r in runs])


def run(engine, session_id, provider, embedder, settings, retriever=None):
    token = uuid4()
    with Session(engine) as db, db.begin():
        owner = load_session(db, session_id, lock=True)
        row = state_row(db, owner)
        if row.equipment_revision != owner.identification_revision:
            raise StaleIdentification('Equipment changed; submit inputs for the current equipment')
        if row.run_token and row.run_started_at and row.run_started_at > datetime.now() - timedelta(hours=1):
            raise StaleIdentification('A troubleshooting run is already in progress')
        context = snapshot(db, owner, row)
        stamp = fingerprint(context)
        row.run_token, row.run_started_at = token, datetime.now()
    pipeline = Pipeline(provider, embedder, settings, retriever or (lambda plan: retrieve(engine, plan, embedder, settings)))
    try:
        result = pipeline.execute(context)
    except Exception:
        # Failed calls cannot turn previous findings into a new successful answer.
        result = insufficient(context, 'failed')
        pipeline.audit['error'] = 'Retrieval or structured provider call failed; no diagnosis generated'
    stale = False
    with Session(engine) as db, db.begin():
        owner = load_session(db, session_id, lock=True)
        row = state_row(db, owner)
        stale = row.run_token != token or stamp != fingerprint(snapshot(db, owner, row))
        record = TroubleshootingRun(session_id=session_id, input_revision=context['revision'],
            equipment_revision=context['equipment_revision'], context_fingerprint=stamp,
            status='stale' if stale else result['status'], audit=pipeline.audit,
            final=insufficient(context, 'stale') if stale else result)
        db.add(record)
        if row.run_token == token:
            row.run_token = None
            if not stale: row.current = dict(context_fingerprint=stamp, result=result)
    if stale: raise StaleIdentification('Session changed during analysis; result discarded')
    return get_state(engine, session_id)


def get_run(engine, session_id, run_id, include_evidence=False):
    with Session(engine) as db:
        load_session(db, session_id)
        row = db.get(TroubleshootingRun, run_id)
        if not row or row.session_id != session_id: raise SessionNotFound('Run not found in session')
        result = dict(run_id=str(row.id), status=row.status, result=row.final)
        if include_evidence:
            result.update(audit=row.audit, warning='Debug audit contains unverified candidates; not technician advice')
        return result
