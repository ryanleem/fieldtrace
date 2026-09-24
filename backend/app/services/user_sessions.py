"""Owner-scoped session metadata. Legacy ownerless rows are never auto-claimed."""
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
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
