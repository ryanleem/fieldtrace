"""Two query channels over existing Step 1 search functions; no new search engine."""
import re
from sqlalchemy.orm import Session
from app.db.init_db import assert_compatible
from app.schemas.search import SearchRequest
from app.services.semantic_search import semantic_search
from app.services.keyword_search import keyword_search
from app.services.hybrid_search import reciprocal_rank_fusion
from app.services.query_normalization import retrieval_query


def construct_query(context, embedder, refinement=None):
    inputs = context['inputs']
    equipment = context.get('equipment') or {}
    parts = [' '.join(str(equipment.get(k) or '') for k in ('manufacturer', 'model', 'family')).strip()]
    for key in ('reported_symptoms', 'follow_up_answers', 'confirmed_observations', 'checks_completed',
                'ruled_out_causes', 'technician_notes'):
        parts.extend(f'{key.replace("_", " ")}: {v}' for v in inputs.get(key, []))
    parts.extend('measurement: ' + ' '.join(m[k] for k in ('name', 'value', 'unit', 'location'))
                 for m in inputs.get('measurements', []))
    parts.extend('visible: ' + f['description'] for f in context.get('visual_findings', []))
    parts.extend('image user note (unverified): ' + n['note'] for n in context.get('image_user_notes', []))
    if refinement: parts.insert(1, refinement)
    # Preserve exact punctuation/case in the full context and keyword channel.
    all_text = ' ; '.join(parts + [context.get('ocr_text', '')])
    exact = list(dict.fromkeys(re.findall(r'[+-]?[\w]+(?:[-./:][\w]+)*', all_text)))
    exact = [v for v in exact if any(c.isdigit() for c in v) or (v.isupper() and len(v) > 1)]
    # Manufacturer boilerplate occurs throughout manuals and is already a filter/context.
    exact = [v for v in exact if v.casefold() != str(equipment.get('manufacturer', '')).casefold()]
    exact += re.findall(r'["\u201c]([^"\u201d]+)["\u201d]', all_text)
    exact += [m['value'] + ' ' + m['unit'] for m in inputs.get('measurements', [])]
    exact = list(dict.fromkeys(exact))
    query, omitted = '', []
    for part in filter(None, parts):
        addition = ('; ' if query else '') + part
        if len(query + addition) <= 2000 and embedder.token_count(query + addition) <= embedder.max_tokens:
            query += addition
        else:
            omitted.append(part)
    if not query:
        query = 'equipment troubleshooting'
    # Disjoint technical terms should not require every identifier/measurement to
    # co-occur in one chunk. Each unchanged FTS call retains its own exact term.
    prose = ' '.join(inputs.get('reported_symptoms', []) + inputs.get('follow_up_answers', []) +
                     [f['description'] for f in context.get('visual_findings', [])])
    prose = ' '.join(v for v in prose.split() if not any(c.isdigit() for c in v))[:1800]
    filters = context.get('retrieval_filters') or {}
    if prose: prose = retrieval_query(SearchRequest(query=prose, **filters))
    redundant = {str(equipment.get(k, '')).casefold() for k in ('manufacturer', 'model', 'family')}
    redundant |= {str(v).casefold() for v in filters.values() if v}
    technical = [term for term in exact if term.casefold() not in redundant]
    keyword_queries = list(dict.fromkeys(technical + ([prose] if prose else [])))[:9]
    # Confirmation already enforces model identity in SQL. Remove its full catalog
    # spelling as well as the retrieval alias from the executed embedding query.
    semantic = query
    if filters.get('equipment_model') and equipment.get('model'):
        semantic = semantic.replace(equipment['model'], '')
    return {'semantic_query': query, 'exact_keyword_terms': exact, 'keyword_queries': keyword_queries,
            'technical_keyword_queries': [term for term in technical if term in keyword_queries],
            'filter_covered_terms': [term for term in exact if term.casefold() in redundant],
            'executed_semantic_query': retrieval_query(SearchRequest(query=semantic, **filters)),
            'omitted_semantic_context': omitted,
            'unsearched_exact_terms': [v for v in technical if v not in keyword_queries],
            'retrieval_filters': context.get('retrieval_filters') or {}}


def retrieve(engine, plan, embedder, settings):
    request = SearchRequest(query=plan.get('executed_semantic_query', plan['semantic_query']), top_k=settings.troubleshooting_top_k,
                            **plan['retrieval_filters'])
    vector = embedder.encode([request.query], query=True)[0]
    with Session(engine) as db:
        assert_compatible(db, embedder, settings)
        semantic = semantic_search(db, request, vector, settings.semantic_top_n)
        unique = {}
        exact_ids = set()
        definition_ids = set()
        ranks = {}
        for query in plan['keyword_queries']:
            rows = keyword_search(db, request.model_copy(update={'query': query}), settings.keyword_top_n)
            for rank, row in enumerate(rows, 1):
                if query in plan.get('technical_keyword_queries', []):
                    exact_ids.add(row.chunk_id)
                    # A code's own table row is more useful than repeated mentions
                    # inside other rows (e.g. status-bit compatibility tables).
                    if re.search(r'^\s*' + re.escape(query) + r'\s*\|', row.chunk_text, re.MULTILINE | re.IGNORECASE):
                        definition_ids.add(row.chunk_id)
                ranks[row.chunk_id] = ranks.get(row.chunk_id, 0) + 1 / (settings.rrf_k + rank)
                previous = unique.get(row.chunk_id)
                if previous is None or (row.keyword_score or 0) > (previous.keyword_score or 0):
                    unique[row.chunk_id] = row
        # Raw ts_rank scores from different queries are not comparable. Fuse ranks;
        # when exact technical hits exist, broad prose must not displace them.
        keyword = sorted((r for r in unique.values() if not exact_ids or r.chunk_id in exact_ids),
                         key=lambda r: (r.chunk_id not in definition_ids, -ranks[r.chunk_id], str(r.chunk_id)))
    return reciprocal_rank_fusion(semantic, keyword, settings.rrf_k, request.top_k)
