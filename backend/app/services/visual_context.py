"""Prepare evidence for an explicit future search; never executes retrieval."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.equipment import Equipment
from app.models.vision import SessionImage, AggregatedVisualFinding
from app.services.equipment_sessions import load_session


def build_visual_retrieval_context(session_id, engine=None):
    if engine is None:
        from app.db.session import get_engine
        engine = get_engine()
    with Session(engine) as session:
        owner = load_session(session, session_id)
        equipment = session.get(Equipment, owner.confirmed_equipment_id) if owner.confirmed_equipment_id else None
        findings = session.scalars(select(AggregatedVisualFinding).where(
            AggregatedVisualFinding.session_id == session_id,
            AggregatedVisualFinding.equipment_id == owner.confirmed_equipment_id).order_by(AggregatedVisualFinding.id)).all()
        # Unconfirmed observations stay stored, but cannot be silently attributed
        # to a later confirmed model. Re-upload under confirmed identity if needed.
        parts = [f'{equipment.manufacturer} {equipment.model_name}'] if equipment else []
        items = [dict(aggregated_finding_id=str(f.id), issue_type=f.issue_type, location=f.location,
                      description=f.description, supporting_image_ids=f.supporting_image_ids) for f in findings]
        parts.extend('visible ' + f.issue_type.replace('_', ' ') + ' at ' + f.location for f in findings)
        return dict(session_id=str(session_id), equipment_id=owner.confirmed_equipment_id,
            equipment={'manufacturer': equipment.manufacturer, 'family': equipment.equipment_family, 'model': equipment.model_name} if equipment else None,
            visual_findings=items, text='; '.join(parts),
            retrieval_filters={'equipment_model': equipment.retrieval_model, 'equipment_family': equipment.retrieval_family} if equipment else None,
            user_notes=[{'image_id': str(i.id), 'note': i.user_note, 'source': 'user_report'} for i in session.scalars(
                select(SessionImage).where(SessionImage.session_id == session_id, SessionImage.equipment_id == owner.confirmed_equipment_id, SessionImage.user_note.is_not(None)))],
            scope='Visual component only; notes remain separate and are not verified observations.')


def visual_search_request(context, embedder, top_k=5):
    """Bound the optional query to the existing encoder budget without changing it.

    Full evidence is retained in context; return omitted IDs explicitly.
    """
    from app.schemas.search import SearchRequest
    if not context['equipment'] or not context['retrieval_filters']:
        raise ValueError('Confirmed equipment required')
    text = context['equipment']['manufacturer'] + ' ' + context['equipment']['model']
    omitted = []
    for finding in context['visual_findings']:
        addition = '; visible ' + finding['issue_type'].replace('_', ' ') + ' at ' + finding['location']
        if embedder.token_count(text + addition) <= embedder.max_tokens:
            text += addition
        else:
            omitted.append(finding['aggregated_finding_id'])
    return SearchRequest(query=text, top_k=top_k, **context['retrieval_filters']), omitted
