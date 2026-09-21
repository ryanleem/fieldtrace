import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.db.session import get_engine
from app.schemas.equipment import ConfirmEquipment, EquipmentState
from app.services.equipment_ocr import MAX_IMAGE_BYTES, get_ocr_provider
from app.services import equipment_sessions as service

router = APIRouter(prefix='/sessions', tags=['equipment identification'])


def call(operation, *args):
    try:
        return operation(*args)
    except service.SessionNotFound as error:
        raise HTTPException(404, str(error)) from error
    except service.StaleIdentification as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post('', response_model=EquipmentState, status_code=201)
def create():
    return service.create_session(get_engine())


@router.post('/{session_id}/equipment/identify', response_model=EquipmentState)
def identify(session_id: UUID, entered_equipment_text: str | None = Form(None),
             images: list[UploadFile] = File(default=[]),
             image_roles: str | None = Form(None), provider=Depends(get_ocr_provider)):
    """Multipart image_roles is a JSON array parallel to images; defaults to nameplate.

    Each call replaces identification inputs and clears any previous confirmation.
    Raw OCR injection is intentionally not exposed as a production API parameter.
    """
    if len(images) > 5:
        raise HTTPException(422, 'Upload at most five images')
    try:
        roles = json.loads(image_roles) if image_roles is not None else ['nameplate'] * len(images)
    except json.JSONDecodeError as error:
        raise HTTPException(422, 'image_roles must be a JSON array') from error
    if not isinstance(roles, list) or len(roles) != len(images) or any(role not in ['nameplate', 'equipment'] for role in roles):
        raise HTTPException(422, 'Provide one nameplate/equipment role per image')
    uploaded = [{'data': image.file.read(MAX_IMAGE_BYTES + 1), 'role': role} for image, role in zip(images, roles)]
    return call(service.identify, get_engine(), session_id, entered_equipment_text, uploaded, provider)


@router.post('/{session_id}/equipment/confirm', response_model=EquipmentState)
def confirm(session_id: UUID, request: ConfirmEquipment):
    return call(service.confirm, get_engine(), session_id, request)


@router.post('/{session_id}/equipment/reject', response_model=EquipmentState)
def reject(session_id: UUID):
    return call(service.reject, get_engine(), session_id)


@router.get('/{session_id}/equipment', response_model=EquipmentState)
def state(session_id: UUID):
    return call(service.get_state, get_engine(), session_id)
