import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query

from app.db.session import get_engine
from app.config import get_settings
from app.schemas.equipment import ConfirmEquipment, EquipmentState
from app.services.equipment_ocr import MAX_IMAGE_BYTES, get_ocr_provider
from app.services import equipment_sessions as service

from app.auth import require_user, session_access
from app.services import user_sessions
from app.services.equipment_visual import get_equipment_visual_provider

router = APIRouter(prefix='/sessions', tags=['equipment identification'], dependencies=[Depends(session_access)])


def call(operation, *args):
    try:
        return operation(*args)
    except service.SessionNotFound as error:
        raise HTTPException(404, str(error)) from error
    except service.StaleIdentification as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post('', status_code=201)
def create(payload: user_sessions.SessionName, user_id: UUID = Depends(require_user)):
    return user_sessions.create(get_engine(), user_id, payload)


@router.get('')
def history(user_id: UUID = Depends(require_user), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return user_sessions.list_owned(get_engine(), user_id, limit, offset)


@router.get('/{session_id}')
def metadata(session_id: UUID, user_id: UUID = Depends(require_user)):
    return user_sessions.get_owned(get_engine(), session_id, user_id)


@router.patch('/{session_id}')
def rename(session_id: UUID, payload: user_sessions.SessionName, user_id: UUID = Depends(require_user)):
    return user_sessions.rename(get_engine(), session_id, user_id, payload)


@router.get('/{session_id}/draft')
def get_draft(session_id: UUID, user_id: UUID = Depends(require_user)):
    return user_sessions.session_draft(get_engine(), session_id, user_id)


@router.put('/{session_id}/draft')
def save_draft(session_id: UUID, payload: user_sessions.WorkspaceDraft, user_id: UUID = Depends(require_user)):
    return user_sessions.session_draft(get_engine(), session_id, user_id, payload)


@router.delete('/{session_id}')
def delete_session(session_id: UUID, user_id: UUID = Depends(require_user)):
    return user_sessions.delete_owned(get_engine(), session_id, user_id, get_settings())


@router.post('/{session_id}/equipment/identify', response_model=EquipmentState)
def identify(session_id: UUID, entered_equipment_text: str | None = Form(None),
             images: list[UploadFile] = File(default=[]),
             image_roles: str | None = Form(None), saved_image_ids: str | None = Form(None), use_visual: bool = Form(False),
             provider=Depends(get_ocr_provider), visual_provider=Depends(get_equipment_visual_provider)):
    """Multipart image_roles is a JSON array parallel to images; defaults to nameplate.

    Each call replaces identification inputs and clears any previous confirmation.
    Raw OCR injection is intentionally not exposed as a production API parameter.
    """
    if len(images) > 30:
        raise HTTPException(422, 'Select at most thirty identification images')
    try:
        roles = json.loads(image_roles) if image_roles is not None else ['nameplate'] * len(images)
    except json.JSONDecodeError as error:
        raise HTTPException(422, 'image_roles must be a JSON array') from error
    if not isinstance(roles, list) or len(roles) != len(images) or any(role not in ['nameplate', 'equipment'] for role in roles):
        raise HTTPException(422, 'Provide one nameplate/equipment role per image')
    uploaded = [{'data': image.file.read(MAX_IMAGE_BYTES + 1), 'role': role} for image, role in zip(images, roles)]
    try:
        if saved_image_ids is None:
            from sqlalchemy import select, or_
            from sqlalchemy.orm import Session
            from app.models.vision import SessionImage
            from sqlalchemy import inspect
            with Session(get_engine()) as db:
                saved = [str(i) for i in db.scalars(select(SessionImage.id).where(SessionImage.session_id==session_id,
                    or_(SessionImage.use_for_identification.is_(True), SessionImage.use_for_identification.is_(None) & (SessionImage.view_label=='nameplate'))))] if inspect(get_engine()).has_table('session_images') else []
        else:
            saved = json.loads(saved_image_ids)
        if not isinstance(saved, list) or len(saved) + len(uploaded) > 30:
            raise ValueError('Select at most thirty identification photos')
        saved = [UUID(value) for value in saved]
    except (ValueError, TypeError, AttributeError) as error:
        raise HTTPException(422, 'Provide up to thirty saved image UUIDs') from error
    if saved:
        from sqlalchemy.orm import Session
        from app.services.inspection_images import load_image, image_path
        with Session(get_engine()) as db:
            for image_id in saved:
                row = call(load_image, db, session_id, image_id)
                try:
                    with image_path(get_settings(), row).open('rb') as handle:
                        uploaded.append({'data': handle.read(MAX_IMAGE_BYTES + 1), 'role': 'nameplate' if row.view_label == 'nameplate' else 'equipment'})
                except (OSError, ValueError) as error:
                    raise HTTPException(422, 'Saved identification photo is unavailable') from error
    return call(service.identify, get_engine(), session_id, entered_equipment_text, uploaded, provider, visual_provider if use_visual else None)


@router.post('/{session_id}/equipment/confirm', response_model=EquipmentState)
def confirm(session_id: UUID, request: ConfirmEquipment):
    return call(service.confirm, get_engine(), session_id, request)


@router.post('/{session_id}/equipment/reject', response_model=EquipmentState)
def reject(session_id: UUID):
    return call(service.reject, get_engine(), session_id)


@router.get('/{session_id}/equipment', response_model=EquipmentState)
def state(session_id: UUID):
    return call(service.get_state, get_engine(), session_id)
