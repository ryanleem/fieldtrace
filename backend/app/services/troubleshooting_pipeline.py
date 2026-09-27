"""Bounded evidence -> candidate -> cited-only verification loop.

Candidates/audits are private by default. No alternative is ever auto-promoted.
All LLM-generated public technical text, including cause labels/rationales,
actions, questions and missing-information text, goes through the verifier.
"""
from collections import defaultdict
import re
from app.schemas.troubleshooting import STAGE_SCHEMAS
from app.services.troubleshooting_provider import TroubleshootingUnavailable
from app.services.troubleshooting_query import construct_query, retrieve


def follow_up_question(context):
    if not context.get('equipment'):
        return 'What exact equipment model is shown on the nameplate? Please confirm it.'
    if not context['inputs'].get('reported_symptoms'):
        return 'What symptom or fault code are you observing?'
    if not context['inputs'].get('measurements'):
        if any('overheat' in s.lower() for s in context['inputs'].get('reported_symptoms', [])):
            return 'What temperature was already measured, at which location, and under what operating conditions?'
        return 'What values have you already measured, including units and measurement location?'
    return 'What exact fault code or additional observation can you provide, and under what operating conditions?'


def insufficient(context, status='insufficient_evidence'):
    return {'status': status, 'primary_cause': None, 'alternative_causes': [],
            'technical_claims': [], 'recommended_actions': [], 'confidence': 'LOW',
            'next_question': follow_up_question(context), 'missing_information': [],
            'sources': [], 'conflicts': [],
            'message': 'The available evidence is insufficient to support a suspected cause.'}


def confidence(*, primary_supported, strong_evidence, strong_retrieval, conflict,
               equipment_confirmed, low_visual_confidence, missing_count, partial):
    """Ordinal policy, not a probability or statistical calibration.

    Unsupported primary / weak evidence -> LOW. Otherwise HIGH only when both
    retrieval channels contribute, equipment is confirmed, no conflicts or missing
    information, no weakened claims, and no low-confidence visual observations.
    Every other supported case -> MEDIUM, satisfying all explicit confidence caps.
    """
    if not primary_supported or not strong_evidence:
        return 'LOW'
    if (strong_retrieval and equipment_confirmed and not conflict and not low_visual_confidence
            and missing_count == 0 and not partial):
        return 'HIGH'
    return 'MEDIUM'


class Pipeline:
    def __init__(self, provider, embedder, settings, retriever):
        self.provider, self.embedder, self.settings = provider, embedder, settings
        self.retriever = retriever
        self.audit = {'attempts': [], 'calls': []}

    def call(self, stage, payload):
        if len(self.audit['calls']) >= self.settings.troubleshooting_max_llm_calls:
            raise TroubleshootingUnavailable('Troubleshooting call budget exhausted')
        record = {'stage': stage, 'input': payload}
        self.audit['calls'].append(record)
        try:
            response = self.provider.complete(stage, payload)
            record['response'] = response
            return STAGE_SCHEMAS[stage].model_validate(response['output'])
        except Exception:
            # Never leak provider details/secrets or invent a replacement answer.
            record['error'] = 'Provider output unavailable or invalid'
            raise TroubleshootingUnavailable('Troubleshooting provider output unavailable or invalid') from None

    def verify(self, text, ids, evidence, log, key):
        ids = list(dict.fromkeys(ids))
        if not ids or any(cid not in evidence for cid in ids):
            log.append({'key': key, 'text': text, 'status': 'UNSUPPORTED', 'reason': 'Missing or unknown citation'})
            return None, False
        # This payload intentionally contains ONLY the statement and its own citations.
        cited = [evidence[cid] for cid in ids]
        def record(result, statement, record_key):
            row = {'key': record_key, 'text': statement, 'citation_chunk_ids': ids, **result.model_dump()}
            # A live verifier accepted a causal photo inference while explicitly
            # admitting it was not in its sources. Fail closed on that contradiction.
            if result.status == 'SUPPORTED' and re.search(
                    r'\bnot (?:explicitly (?:stated|supported|documented)|directly supported|mentioned in (?:the )?(?:cited|supplied))\b',
                    result.explanation, re.I):
                row.update(status='UNSUPPORTED', provider_status='SUPPORTED',
                           guard_reason='Verifier explanation admits an evidence gap')
            log.append(row)
            return row['status']
        result = self.call('verify', {'claim': text, 'evidence': cited})
        status = record(result, text, key)
        if status == 'SUPPORTED':
            return text, False
        if status == 'PARTIAL' and result.revised_text:
            # Never trust the verifier's rewrite without checking the rewrite itself.
            checked = self.call('verify', {'claim': result.revised_text, 'evidence': cited})
            if record(checked, result.revised_text, key + ':revision') == 'SUPPORTED':
                return result.revised_text, True
        return None, False

    def execute(self, context):
        if context.get('manual_coverage') is False:
            result = insufficient(context)
            result['message'] = ('Equipment confirmed, but no indexed manual matches this equipment. '
                                 'Troubleshooting is unavailable until an applicable manual is added.')
            result['next_question'] = 'Can you provide an applicable manual or confirm that the selected equipment is correct?'
            result['missing_information'] = ['An indexed manual matching the confirmed equipment.']
            self.audit['coverage'] = 'No indexed manual matches the confirmed equipment filters'
            return result
        refinement = None
        reviewed_evidence = {}
        for attempt in range(2):
            plan = construct_query(context, self.embedder, refinement)
            rows = self.retriever(plan)
            evidence = {str(row.chunk_id): row.model_dump(mode='json') for row in rows}
            audit = {'query': plan, 'evidence': list(evidence.values()), 'verifications': []}
            self.audit['attempts'].append(audit)
            if not evidence:
                answer = insufficient(context)
                answer['sources'] = self.sources(reviewed_evidence, reviewed_evidence)
                return answer
            review = self.call('review', {'context': context, 'evidence': list(evidence.values())})
            if len(review.chunks) != len(evidence) or {r.chunk_id for r in review.chunks} != set(evidence):
                raise TroubleshootingUnavailable('Evidence review did not cover retrieved chunks')
            audit['review'] = review.model_dump()
            usable = {r.chunk_id: evidence[r.chunk_id] for r in review.chunks if r.relevance != 'NOT_RELEVANT'}
            relevant = [r for r in review.chunks if r.relevance == 'RELEVANT']
            # Documentary context for review, not a verified causal claim. Keep
            # only explicitly relevant passages, including from a prior retry.
            for rating in review.chunks:
                reviewed_evidence.pop(rating.chunk_id, None)
                if rating.relevance == 'RELEVANT':
                    reviewed_evidence[rating.chunk_id] = evidence[rating.chunk_id]
            # Weak evidence cannot support a candidate. Do not let a subsequent
            # optional conflict call turn this valid follow-up path into failure.
            if review.strength == 'WEAK' or not relevant:
                audit['conflicts'] = []
                answer = insufficient(context)
                answer['sources'] = self.sources(reviewed_evidence, reviewed_evidence)
                return answer
            groups = defaultdict(list)
            for r in review.chunks:
                if r.chunk_id in usable:
                    groups[r.issue.strip().casefold()].append(r.chunk_id)
            conflicts = []
            for ids in groups.values():
                # Existing RRF rank order, not arbitrary order chosen by the LLM.
                ids.sort(key=lambda cid: evidence[cid]['rank'])
                if len(ids) < 2: continue
                ids = ids[:3]
                relation = self.call('conflict', {'evidence': [evidence[cid] for cid in ids]})
                if set(relation.chunk_ids) != set(ids) or len(relation.chunk_ids) != len(ids):
                    raise TroubleshootingUnavailable('Invalid conflict citation IDs')
                conflicts.append(relation.model_dump())
            audit['conflicts'] = conflicts
            unresolved = any(r['relationship'] in {'CONFLICTING', 'DIFFERENT_APPLICABILITY'} for r in conflicts)
            candidate = self.call('candidate', {'context': context, 'evidence': list(usable.values()),
                'conflicts': conflicts, 'review': review.model_dump(), 'retry': bool(attempt)})
            audit['candidate'] = candidate.model_dump()
            result = self.filter_candidate(candidate, usable, audit['verifications'], unresolved, context)
            if result is None:
                audit['primary_supported'] = False
                label = candidate.primary_cause.label if candidate.primary_cause else 'reported symptom'
                refinement = 'Find applicable documentation supporting or excluding this hypothesis: ' + label[:300]
                continue  # one refined retrieval; never promote an alternative
            audit['primary_supported'] = True
            primary_ids = result['primary_cause']['citation_chunk_ids']
            relevant_ids = {r.chunk_id for r in relevant}
            strong_retrieval = all(cid in relevant_ids for cid in primary_ids) and any(
                evidence[cid]['semantic_rank'] is not None and evidence[cid]['keyword_rank'] is not None
                for cid in primary_ids)
            result['confidence'] = confidence(primary_supported=True, strong_evidence=True,
                strong_retrieval=strong_retrieval, conflict=unresolved,
                equipment_confirmed=bool(context.get('equipment')),
                low_visual_confidence=any(f.get('visual_confidence') == 'low' for f in context.get('visual_findings', [])),
                missing_count=len(candidate.missing_information) + len(review.missing_information),
                partial=result.pop('_partial'))
            result['conflicts'] = self.public_conflicts(conflicts, evidence)
            ids = [cid for item in result['technical_claims'] + result['recommended_actions'] for cid in item['citation_chunk_ids']]
            ids += result['primary_cause']['citation_chunk_ids']
            ids += [cid for cause in result['alternative_causes'] for cid in cause['citation_chunk_ids']]
            ids += [cid for item in result.get('question_sources', []) for cid in [item]]
            ids += [cid for r in conflicts for cid in r['chunk_ids']]
            result['sources'] = self.sources(evidence, ids)
            return result
        answer = insufficient(context)
        answer['conflicts'] = self.public_conflicts(conflicts, evidence)
        source_evidence = {**reviewed_evidence, **evidence}
        answer['sources'] = self.sources(source_evidence, list(reviewed_evidence) +
                                        [cid for r in conflicts for cid in r['chunk_ids']])
        return answer

    def filter_candidate(self, candidate, evidence, log, unresolved, context):
        primary = candidate.primary_cause
        original = {c.claim_id: c for c in candidate.technical_claims}
        if not primary or len(original) != len(candidate.technical_claims): return None
        verified, partial = {}, False
        for claim in candidate.technical_claims:
            text, weakened = self.verify(claim.text, claim.citation_chunk_ids, evidence, log, claim.claim_id)
            partial |= weakened
            if text:
                verified[claim.claim_id] = dict(claim.model_dump(), text=text)

        def cause(c, key):
            nonlocal partial
            if not c.claim_ids or any(cid not in verified for cid in c.claim_ids): return None
            if any(c.label.casefold() == r.casefold() for r in context['inputs'].get('ruled_out_causes', [])): return None
            ids = list(dict.fromkeys(cid for claim_id in c.claim_ids for cid in verified[claim_id]['citation_chunk_ids']))
            # Label and rationale are each claims too; a cited technical_claim does
            # not license an unsupported diagnosis title or embellished rationale.
            label, weak_label = self.verify(c.label, ids, evidence, log, key + ':label')
            rationale, weak_reason = self.verify(c.rationale, ids, evidence, log, key + ':rationale')
            partial |= weak_label or weak_reason
            if not label or not rationale: return None
            return dict(label=label, rationale=rationale, claim_ids=c.claim_ids, citation_chunk_ids=ids)

        primary = cause(primary, 'primary')
        if primary is None: return None
        alternatives = [v for i, c in enumerate(candidate.alternative_causes) if (v := cause(c, f'alternative:{i}'))]
        actions = []
        if not unresolved and context.get('equipment'):
            for i, action in enumerate(candidate.recommended_actions):
                if action.action in context['inputs'].get('checks_completed', []): continue
                text, weakened = self.verify(action.action, action.citation_chunk_ids, evidence, log, f'action:{i}')
                partial |= weakened
                if text: actions.append(dict(action= text, citation_chunk_ids=action.citation_chunk_ids))
        question = follow_up_question(context)
        question_ids = []
        if candidate.next_question:
            # A question also cannot smuggle an unsupported action/assertion.
            # Bind it explicitly to the primary's evidence in the candidate audit.
            question_ids = primary['citation_chunk_ids']
            text, weakened = self.verify(candidate.next_question, question_ids, evidence, log, 'question')
            partial |= weakened
            if text and text.rstrip().endswith('?'): question = text
            else: question_ids = []
        missing = []
        for i, item in enumerate(candidate.missing_information[:3]):
            text, weakened = self.verify('Information needed: ' + item, primary['citation_chunk_ids'],
                                         evidence, log, f'missing:{i}')
            partial |= weakened
            # A supported rewrite may still change an information request into
            # maintenance advice. Do not publish it under the wrong field role.
            if text and text.startswith('Information needed: '): missing.append(text)
        if unresolved:
            question = 'Which exact equipment model, manual revision, and operating conditions apply to this inspection?'
            question_ids = []
        return {'status': 'suspected_cause', 'primary_cause': primary, 'alternative_causes': alternatives,
            'technical_claims': list(verified.values()), 'recommended_actions': actions,
            'next_question': question, 'question_sources': question_ids, 'missing_information': missing,
            'message': 'Suspected cause based on the cited documentation; not a confirmed diagnosis.', '_partial': partial}

    @staticmethod
    def sources(evidence, ids):
        keys = ('chunk_id', 'document_id', 'document_title', 'page_number', 'printed_page_label',
                'section_title', 'source_url', 'citation_url', 'document_number', 'revision')
        return [{k: evidence[cid].get(k) for k in keys} for cid in dict.fromkeys(ids) if cid in evidence]

    @staticmethod
    def public_conflicts(conflicts, evidence):
        # Free-form conflict explanations stay private; public labels/IDs preserve
        # conflicts without adding unverified technical prose to the answer.
        return [{'relationship': r['relationship'], 'citation_chunk_ids': r['chunk_ids']}
                for r in conflicts]
