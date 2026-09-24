import json
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from app.config import get_settings
from app.db.session import get_engine
from app.api.equipment import call
from app.services import inspection_images as service
from app.services.vision_provider import get_vision_provider
from app.services.visual_context import build_visual_retrieval_context

from app.auth import session_access

router = APIRouter(dependencies=[Depends(session_access)], prefix='/sessions', tags=['visual evidence'])


@router.post('/{session_id}/images', status_code=201)
def upload(session_id: UUID, images: list[UploadFile] = File(...),
           view_labels: str | None = Form(None), user_notes: str | None = Form(None)):
    """view_labels and user_notes are JSON arrays parallel to images; null entries use defaults."""
    settings = get_settings()
    if len(images) > settings.max_inspection_images:
        raise HTTPException(422, 'Too many images')
    try:
        labels = json.loads(view_labels) if view_labels is not None else [None] * len(images)
        notes = json.loads(user_notes) if user_notes is not None else [None] * len(images)
        if not isinstance(labels, list) or not isinstance(notes, list) or len(labels) != len(images) or len(notes) != len(images):
            raise ValueError('Metadata arrays must match image count')
    except (ValueError, TypeError) as error:
        raise HTTPException(422, 'Provide JSON view_labels/user_notes arrays matching image count') from error
    uploads = [dict(data=image.file.read(settings.max_inspection_image_bytes + 1),
                    original_filename=image.filename, view_label=label if label is not None else 'additional', user_note=note)
               for image, label, note in zip(images, labels, notes)]
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
