import json
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from app.config import get_settings
from app.db.session import get_engine
from app.api.equipment import call
from app.services import inspection_images as service
from app.services.vision_provider import get_vision_provider
from app.services.visual_context import build_visual_retrieval_context

from app.auth import session_access, require_user

router = APIRouter(dependencies=[Depends(session_access)], prefix='/sessions', tags=['visual evidence'])


@router.post('/{session_id}/images', status_code=201)
def upload(session_id: UUID, images: list[UploadFile] = File(...),
           view_labels: str | None = Form(None), user_notes: str | None = Form(None), identification_flags: str | None = Form(None)):
    """view_labels and user_notes are JSON arrays parallel to images; null entries use defaults."""
    settings = get_settings()
    if len(images) > settings.max_inspection_images:
        raise HTTPException(422, 'Too many images')
    try:
        flags = json.loads(identification_flags) if identification_flags is not None else [None] * len(images)
        if not isinstance(flags,list) or len(flags)!=len(images) or any(flag is not None and type(flag) is not bool for flag in flags):
            raise ValueError('Invalid identification flags')
        labels = json.loads(view_labels) if view_labels is not None else [None] * len(images)
        notes = json.loads(user_notes) if user_notes is not None else [None] * len(images)
        if not isinstance(labels, list) or not isinstance(notes, list) or len(labels) != len(images) or len(notes) != len(images):
            raise ValueError('Metadata arrays must match image count')
    except (ValueError, TypeError) as error:
        raise HTTPException(422, 'Provide JSON view_labels/user_notes arrays matching image count') from error
    uploads = [dict(data=image.file.read(settings.max_inspection_image_bytes + 1),
                    original_filename=image.filename, view_label=label if label is not None else 'additional', user_note=note, use_for_identification=flag)
               for image, label, note, flag in zip(images, labels, notes, flags)]
    return call(service.upload_images, get_engine(), session_id, uploads, settings)


@router.get('/{session_id}/images')
def images(session_id: UUID):
    return call(service.list_images, get_engine(), session_id)


@router.post('/{session_id}/images/analyze-all')
def analyze_all(session_id: UUID, provider=Depends(get_vision_provider)):
    return call(service.analyze_all, get_engine(), session_id, provider, get_settings())


@router.post('/{session_id}/images/{image_id}/analyze')
def analyze(session_id: UUID, image_id: UUID, provider=Depends(get_vision_provider)):
    return call(service.analyze_image, get_engine(), session_id, image_id, provider, get_settings())


@router.get('/{session_id}/visual-findings')
def findings(session_id: UUID):
    return call(service.visual_state, get_engine(), session_id)


@router.get('/{session_id}/visual-context')
def context(session_id: UUID):
    return call(build_visual_retrieval_context, session_id, get_engine())


@router.delete('/{session_id}/images/{image_id}')
def remove(session_id: UUID, image_id: UUID, user_id: UUID = Depends(require_user)):
    return call(service.remove_image, get_engine(), session_id, image_id, user_id, get_settings())


from pydantic import BaseModel, ConfigDict
class IdentificationSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    use_for_identification: bool

@router.patch('/{session_id}/images/{image_id}/identification')
def select_identification(session_id: UUID, image_id: UUID, payload: IdentificationSelection, user_id: UUID = Depends(require_user)):
    from sqlalchemy.orm import Session
    from app.services.user_sessions import owned_query
    with Session(get_engine()) as db, db.begin():
        if db.scalar(owned_query(session_id,user_id).with_for_update()) is None:
            raise HTTPException(404, 'Session not found')
        row=call(service.load_image,db,session_id,image_id)
        row.use_for_identification=payload.use_for_identification
        db.flush()
        return service.image_dict(row)
