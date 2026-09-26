"""Owner-scoped session metadata. Legacy ownerless rows are never auto-claimed."""
from uuid import UUID
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from app.models.equipment import EquipmentSession, Equipment
from app.models.troubleshooting import TroubleshootingSession
from app.services.equipment_sessions import serialize


class SessionName(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    session_name: str = Field(min_length=1, max_length=100)


def owned_query(session_id, user_id):
    return select(EquipmentSession).where(EquipmentSession.id == session_id,
                                          EquipmentSession.owner_user_id == user_id)


def load_owned(db, session_id, user_id):
    row = db.scalar(owned_query(session_id, user_id))
    if row is None:
        raise HTTPException(404, 'Session not found')
    return row


def owned_session(engine, session_id, user_id):
    with Session(engine) as db:
        load_owned(db, session_id, user_id)


def metadata(db, row):
    equipment = db.get(Equipment, row.confirmed_equipment_id) if row.confirmed_equipment_id else None
    trace = db.get(TroubleshootingSession, row.id)
    current = trace and trace.equipment_revision == row.identification_revision
    inputs = trace.inputs if current else {}
    result = trace.current.get('result', {}) if current else {}
    return dict(id=row.id, session_id=row.id, session_name=row.session_name,
                created_at=row.created_at, updated_at=row.updated_at,
                confirmed_model=equipment.model_name if equipment else None,
                symptom_summary='; '.join(inputs.get('reported_symptoms', [])[-2:])[:240],
                confidence=result.get('confidence'), result_status=result.get('status', 'not_run'))


def create(engine, user_id: UUID, payload: SessionName):
    with Session(engine) as db, db.begin():
        row = EquipmentSession(owner_user_id=user_id, session_name=payload.session_name)
        db.add(row); db.flush()
        return {**serialize(db, row).model_dump(), **metadata(db, row)}


def list_owned(engine, user_id, limit=50, offset=0):
    with Session(engine) as db:
        rows = db.scalars(select(EquipmentSession).where(EquipmentSession.owner_user_id == user_id)
                          .order_by(EquipmentSession.updated_at.desc(), EquipmentSession.id.desc())
                          .limit(limit).offset(offset)).all()
        return [metadata(db, row) for row in rows]


def get_owned(engine, session_id, user_id):
    with Session(engine) as db:
        return metadata(db, load_owned(db, session_id, user_id))


def rename(engine, session_id, user_id, payload):
    with Session(engine) as db, db.begin():
        row = load_owned(db, session_id, user_id)
        row.session_name = payload.session_name
        row.updated_at = func.now()
        db.flush(); db.refresh(row)
        return metadata(db, row)


def delete_owned(engine, session_id, user_id, settings):
    """Commit owner-scoped cascading deletion before best-effort file cleanup.

    Never remove files if the transaction fails. Only recorded UUID image files
    directly under this session directory are eligible; never recursively delete.
    """
    from app.models.vision import SessionImage
    from pathlib import Path
    import logging

    with Session(engine) as db, db.begin():
        row = db.scalar(owned_query(session_id, user_id).with_for_update())
        if row is None:
            raise HTTPException(404, 'Session not found')
        images = [(image.id, image.stored_path) for image in db.scalars(
            select(SessionImage).where(SessionImage.session_id == session_id))]
        db.execute(delete(EquipmentSession).where(EquipmentSession.id == session_id,
                                                  EquipmentSession.owner_user_id == user_id))

    failed = 0
    for image_id, stored_path in images:
        try:
            root = settings.uploads_dir.resolve()
            directory = root / str(session_id)
            relative = Path(stored_path)
            if relative.parent != Path(str(session_id)) or relative.name not in {
                    f'{image_id}.jpg', f'{image_id}.png', f'{image_id}.webp'}:
                raise ValueError('Invalid stored image path')
            path = root / relative
            # Reject symlinks/junctions to other sessions or outside the root.
            if directory.resolve() != directory or path.resolve() != path:
                raise ValueError('Redirected upload path')
            path.unlink(missing_ok=True)
        except (OSError, ValueError, RuntimeError):
            failed += 1
    if failed:
        logging.getLogger(__name__).warning('Session %s deleted; %s image files require administrator cleanup', session_id, failed)
    return {'deleted': True, 'file_cleanup_pending': bool(failed)}


class DraftMeasurement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(default='temperature', max_length=80)
    value: str = Field(default='', max_length=80)
    unit: str = Field(default='C', max_length=80)
    location: str = Field(default='', max_length=80)


class WorkspaceDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: str = Field(default='', max_length=1000)
    symptom: str = Field(default='', max_length=1200)
    followup: str = Field(default='', max_length=1200)
    entry_type: Literal['answer', 'check', 'measurement'] = 'answer'
    measurement: DraftMeasurement = Field(default_factory=lambda: DraftMeasurement())


def session_draft(engine, session_id, user_id, payload=None):
    from app.services.troubleshooting_sessions import state_row
    with Session(engine) as db, db.begin():
        owner = db.scalar(owned_query(session_id, user_id).with_for_update())
        if owner is None:
            raise HTTPException(404, 'Session not found')
        row = db.get(TroubleshootingSession, session_id)
        if payload is not None:
            row = row or state_row(db, owner)
            row.inputs = {**row.inputs, 'workspace_draft': payload.model_dump()}
            owner.updated_at = func.now()
        saved = row.inputs.get('workspace_draft') if row else None
        return WorkspaceDraft.model_validate(saved) if saved is not None else WorkspaceDraft(
            model=owner.entered_equipment_text or '',
            symptom=(row.inputs.get('reported_symptoms') or [''])[-1] if row else '')
