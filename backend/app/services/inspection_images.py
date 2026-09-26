import io
import hashlib
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.equipment import Equipment
from app.models.vision import SessionImage, VisualFinding, AggregatedVisualFinding
from app.schemas.vision import ImageInput, VisionResult
from app.services.equipment_sessions import load_session, SessionNotFound, StaleIdentification
from app.services.visual_aggregation import aggregate
from app.services.vision_provider import VisionImage, VisionUnavailable

FORMATS = {'JPEG': ('image/jpeg', '.jpg'), 'PNG': ('image/png', '.png'), 'WEBP': ('image/webp', '.webp')}


def validate_image(data, settings):
    if len(data) > settings.max_inspection_image_bytes:
        raise ValueError('Image exceeds configured byte limit')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in FORMATS:
                    raise ValueError('Accepted image types: JPEG, PNG, WEBP')
                if image.width * image.height > settings.max_inspection_image_pixels:
                    raise ValueError('Image exceeds configured pixel limit')
                if getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('Animated images are not supported')
                mime, extension = FORMATS[image.format]
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
        return mime, extension
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError('Corrupt or unreadable image') from error


def row_dict(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def image_dict(row, raw=False):
    data = row_dict(row)
    for field in ('analysis_token', 'analysis_started_at', 'stored_path'):
        data.pop(field)
    if not data.get('content_sha256'):
        try:
            data['content_sha256'] = hashlib.sha256(image_path(get_settings(), row).read_bytes()).hexdigest()
        except (OSError, ValueError):
            pass
    if not raw:
        data.pop('raw_vision_results')
    return data


def image_path(settings, record):
    root = settings.uploads_dir.resolve()
    path = (root / record.stored_path).resolve()
    if not path.is_relative_to(root / str(record.session_id)):
        raise ValueError('Invalid stored image path')
    return path


def upload_images(engine, session_id, uploads, settings=None):
    settings = settings or get_settings()
    if not uploads or len(uploads) > settings.max_inspection_images:
        raise ValueError('Provide images within the configured session limit')
    validated = []
    for upload in uploads:
        metadata = ImageInput(view_label=upload.get('view_label', 'additional'), user_note=upload.get('user_note'))
        mime, extension = validate_image(upload['data'], settings)
        filename = upload.get('original_filename') or 'image'
        if len(filename) > 255 or any(ord(c) < 32 for c in filename):
            raise ValueError('Invalid original filename metadata')
        validated.append((upload, metadata, mime, extension, filename))
    written = []
    try:
        with Session(engine) as session, session.begin():
            owner = load_session(session, session_id, lock=True)
            count = session.scalar(select(func.count()).select_from(SessionImage).where(SessionImage.session_id == session_id))
            existing = list(session.scalars(select(SessionImage).where(SessionImage.session_id == session_id).order_by(SessionImage.created_at, SessionImage.id)))
            by_hash = {row.content_sha256: row for row in existing if row.content_sha256}
            for row in existing:
                if row.content_sha256 is None:
                    try:
                        digest = hashlib.sha256(image_path(settings, row).read_bytes()).hexdigest()
                    except (OSError, ValueError):
                        continue
                    if digest not in by_hash:
                        row.content_sha256 = digest
                        by_hash[digest] = row
            created = []
            for upload, metadata, mime, extension, filename in validated:
                digest = hashlib.sha256(upload['data']).hexdigest()
                if digest in by_hash:
                    created.append(by_hash[digest])
                    continue
                if count >= settings.max_inspection_images:
                    raise ValueError('Session image limit exceeded')
                count += 1
                image_id = uuid4()
                record = SessionImage(id=image_id, content_sha256=digest, use_for_identification=upload.get('use_for_identification') if upload.get('use_for_identification') is not None else metadata.view_label=='nameplate', session_id=session_id, equipment_id=owner.confirmed_equipment_id,
                    view_label=metadata.view_label, user_note=metadata.user_note, original_filename=filename,
                    stored_path=f'{session_id}/{image_id}{extension}', mime_type=mime)
                path = image_path(settings, record)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as handle:
                    written.append(path)
                    handle.write(upload['data'])
                session.add(record)
                created.append(record)
                by_hash[digest] = record
            session.flush()
            result = [image_dict(row) for row in created]
        return result
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise


def load_image(session, session_id, image_id):
    row = session.scalar(select(SessionImage).where(SessionImage.session_id == session_id, SessionImage.id == image_id))
    if row is None:
        raise SessionNotFound('Image not found in this session')
    return row


def rebuild_aggregates(session, session_id):
    rows = session.execute(select(VisualFinding, SessionImage.equipment_id).join(SessionImage, VisualFinding.image_id == SessionImage.id)
                           .where(VisualFinding.session_id == session_id).order_by(VisualFinding.created_at, VisualFinding.id)).all()
    session.execute(delete(AggregatedVisualFinding).where(AggregatedVisualFinding.session_id == session_id))
    for value in aggregate([dict(row_dict(f), equipment_id=e) for f, e in rows], session_id):
        session.add(AggregatedVisualFinding(**value))
    session.flush()


def run_vision(provider, image, context):
    attempts = []
    for retry in (False, True):
        try:
            response = provider.analyze_equipment_image(image, context, strict=retry)
        except VisionUnavailable as error:
            return None, attempts, str(error)
        except Exception:
            return None, attempts, 'Vision adapter failed'
        attempts.append(response)
        try:
            output = response['output']
            parsed = VisionResult.model_validate_json(output) if isinstance(output, str) else VisionResult.model_validate(output)
            if not getattr(provider, 'supports_localization', False) and any(f.bounding_region is not None for f in parsed.findings):
                raise ValueError('This adapter does not support reliable localization')
            return parsed, attempts, None
        except (ValidationError, ValueError, KeyError, TypeError):
            continue
    return None, attempts, 'Vision response rejected: malformed or outside visible-observation scope'


def analyze_image(engine, session_id, image_id, provider, settings=None):
    settings = settings or get_settings()
    token = uuid4()
    with Session(engine) as session, session.begin():
        owner = load_session(session, session_id, lock=True)
        record = load_image(session, session_id, image_id)
        if record.analysis_status in {'completed', 'no_clear_abnormality'}:
            return analysis_result(session, record)
        now = datetime.now(timezone.utc)
        # A bounded lease permits explicit retry after process interruption.
        started = record.analysis_started_at
        if started and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if record.analysis_status == 'analyzing' and started and started > now - timedelta(seconds=2 * settings.vision_timeout_seconds + 60):
            raise StaleIdentification('Image analysis is already running')
        if record.equipment_id is not None and record.equipment_id != owner.confirmed_equipment_id:
            raise StaleIdentification('Image belongs to a previous equipment confirmation; use a matching session')
        revision = owner.identification_revision
        record.equipment_id = owner.confirmed_equipment_id
        equipment = session.get(Equipment, record.equipment_id) if record.equipment_id else None
        context = dict(manufacturer=equipment.manufacturer if equipment else None,
                       equipment_family=equipment.equipment_family if equipment else None,
                       model=equipment.model_name if equipment else None,
                       view_label=record.view_label, user_note=record.user_note)
        record.analysis_status, record.analysis_token, record.analysis_started_at = 'analyzing', token, now
        record.analysis_error = None
        path = image_path(settings, record)
    try:
        data = path.read_bytes()
        validate_image(data, settings)
        # Orient and strip metadata for provider; original remains on disk.
        with Image.open(io.BytesIO(data)) as original:
            prepared = ImageOps.exif_transpose(original).convert('RGB')
            prepared.thumbnail((2200, 2200))
            stream = io.BytesIO()
            prepared.save(stream, format='JPEG', quality=95)
        result, raw, error = run_vision(provider, VisionImage(stream.getvalue(), 'image/jpeg'), context)
    except (OSError, ValueError):
        result, raw, error = None, [], 'Stored image could not be read or validated'
    with Session(engine) as session, session.begin():
        owner = load_session(session, session_id, lock=True)
        record = load_image(session, session_id, image_id)
        if record.analysis_token != token:
            raise StaleIdentification('Analysis lease superseded; reload the image')
        record.raw_vision_results = record.raw_vision_results + [{'context': context, 'attempts': raw}]
        if owner.identification_revision != revision:
            result, error = None, 'Equipment confirmation changed during analysis; retry after reviewing the session'
        record.analysis_token = None
        record.analysis_error = error
        if result is None:
            record.analysis_status = 'failed'
        else:
            record.image_summary = result.image_summary
            record.analysis_status = 'completed' if result.findings else 'no_clear_abnormality'
            for finding in result.findings:
                session.add(VisualFinding(session_id=session_id, image_id=image_id, **finding.model_dump()))
        session.flush()
        rebuild_aggregates(session, session_id)
        return analysis_result(session, record)


def analysis_result(session, record):
    return {'image': image_dict(record), 'findings': [row_dict(row) for row in session.scalars(
        select(VisualFinding).where(VisualFinding.image_id == record.id).order_by(VisualFinding.id))]}


def list_images(engine, session_id):
    with Session(engine) as session:
        load_session(session, session_id)
        return [image_dict(row) for row in session.scalars(select(SessionImage).where(SessionImage.session_id == session_id)
                                                          .order_by(SessionImage.created_at, SessionImage.id))]


def visual_state(engine, session_id, include_raw=False):
    with Session(engine) as session:
        owner = load_session(session, session_id)
        images = [image_dict(row, raw=include_raw) for row in session.scalars(select(SessionImage).where(SessionImage.session_id == session_id).order_by(SessionImage.created_at, SessionImage.id))]
        return dict(session_id=session_id, confirmed_equipment_id=owner.confirmed_equipment_id,
            uploaded_images=images, image_view_labels={str(i['id']): i['view_label'] for i in images},
            image_user_notes={str(i['id']): i['user_note'] for i in images},
            image_analysis_status={str(i['id']): i['analysis_status'] for i in images},
            normalized_visual_findings=[row_dict(f) for f in session.scalars(select(VisualFinding).where(VisualFinding.session_id == session_id).order_by(VisualFinding.id))],
            aggregated_visual_findings=[row_dict(f) for f in session.scalars(select(AggregatedVisualFinding).where(AggregatedVisualFinding.session_id == session_id).order_by(AggregatedVisualFinding.id))],
            scope='Visual evidence only. Absence of visible evidence does not establish equipment condition.')


def analyze_all(engine, session_id, provider, settings=None):
    images = list_images(engine, session_id)
    results = []
    for image in images:
        if image['analysis_status'] == 'pending':
            try:
                results.append(analyze_image(engine, session_id, image['id'], provider, settings))
            except StaleIdentification as error:
                results.append({'image_id': image['id'], 'error': str(error)})
    return {'results': results, 'aggregated_visual_findings': visual_state(engine, session_id)['aggregated_visual_findings']}


def remove_image(engine, session_id, image_id, user_id, settings):
    from app.services.user_sessions import owned_query
    from fastapi import HTTPException
    from app.models.troubleshooting import TroubleshootingSession
    with Session(engine) as db, db.begin():
        owner = db.scalar(owned_query(session_id, user_id).with_for_update())
        if owner is None:
            raise HTTPException(404, 'Session not found')
        record = load_image(db, session_id, image_id)
        stored_path = record.stored_path
        db.execute(delete(SessionImage).where(SessionImage.id == image_id, SessionImage.session_id == session_id))
        db.flush()
        rebuild_aggregates(db, session_id)
        trace = db.get(TroubleshootingSession, session_id)
        if trace:
            trace.current = {}
            trace.run_token = None
            trace.revision += 1
    pending = False
    try:
        root = settings.uploads_dir.resolve()
        relative = Path(stored_path)
        if relative.parent != Path(str(session_id)) or relative.name not in {f'{image_id}.jpg', f'{image_id}.png', f'{image_id}.webp'}:
            raise ValueError('Invalid stored image path')
        path = root / relative
        if path.resolve() != path or path.parent.resolve() != path.parent:
            raise ValueError('Redirected upload path')
        path.unlink(missing_ok=True)
    except (OSError, ValueError, RuntimeError):
        pending = True
    return {'deleted': True, 'file_cleanup_pending': pending}
