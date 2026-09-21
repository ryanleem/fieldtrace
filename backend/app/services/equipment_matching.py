"""Rule scores rank catalog entries; levels indicate identification strength only."""
from difflib import SequenceMatcher
import re

from app.services.equipment_parsing import extract_identifiers


def signal_match(identifier, equipment, source):
    value = identifier['normalized']
    model = equipment['model_name']
    if value == model:
        kind = 'exact model'
        base = 100
    elif value in equipment['aliases']:
        kind = 'catalog alias'
        base = 95
    elif value.startswith(model + '-') and re.fullmatch(equipment['model_number_pattern'], value):
        kind = 'full type-code prefix (series match; full SKU not validated)'
        base = 100
    elif value == equipment['equipment_family']:
        kind = 'family only; subtype not established'
        base = 60
    else:
        # A different explicit subtype cannot be upgraded into a model match.
        similarity = max(SequenceMatcher(None, value, model).ratio(),
                         SequenceMatcher(None, value, equipment['equipment_family']).ratio())
        if similarity < 0.55:
            return None
        return {'source': source, 'identifier': value, 'rule': 'approximate identifier; confirm from nameplate',
                'points': round(similarity * 30), 'normalization_notes': identifier['normalization_notes']}
    penalty = 10 if source == 'user_text' else 0
    if source.startswith('equipment_image'):
        penalty = 25  # OCR on a general equipment image is secondary.
    if identifier['normalization_notes']:
        penalty = max(penalty, 25)
    if identifier.get('low_ocr_quality'):
        penalty = max(penalty, 25)
        kind += '; low OCR recognition quality'
    return {'source': source, 'identifier': value, 'rule': kind, 'points': base - penalty,
            'normalization_notes': identifier['normalization_notes']}


def rank_equipment(entered_text, ocr_results, catalog):
    user_ids = extract_identifiers(entered_text or '')
    observations = [('user_text', value) for value in user_ids]
    for index, result in enumerate(ocr_results):
        source = ('nameplate' if result['role'] == 'nameplate' else 'equipment_image') + f'[{index}]'
        for value in result['parsed']['identifiers']:
            value = dict(value)
            supporting = [line['recognition_score'] for line in result.get('lines', [])
                          if value['raw'].casefold() in line['text'].casefold()]
            value['low_ocr_quality'] = bool(supporting and min(supporting) < 0.8)
            observations.append((source, value))
    candidates = []
    for equipment in catalog:
        signals = [signal_match(value, equipment, source) for source, value in observations]
        signals = [signal for signal in signals if signal is not None]
        if not signals:
            continue
        # Repeated copies of an image must not manufacture stronger evidence.
        points = max(signal['points'] for signal in signals)
        conflicts = []
        for source, value in observations:
            family = value['normalized'][:6]
            if len(family) == 6 and family in {row['equipment_family'] for row in catalog}:
                if family != equipment['equipment_family']:
                    conflicts.append(f"{source} contains {value['raw']} (normalized {value['normalized']}); differs from {equipment['model_name']}")
                elif '-' in value['normalized'] and not (value['normalized'] == equipment['model_name'] or value['normalized'].startswith(equipment['model_name'] + '-')):
                    conflicts.append(f"{source} specifies a different or uncatalogued subtype: {value['normalized']}")
        level = 'HIGH' if points >= 90 else 'MEDIUM' if points >= 45 else 'LOW'
        reliable = [signal for signal in signals if signal['points'] >= 45]
        candidates.append({'candidate_id': equipment['id'], 'candidate_model': equipment['model_name'],
                           'manufacturer': equipment['manufacturer'], 'equipment_family': equipment['equipment_family'],
                           'match_level': level, 'rule_score': points, 'matched_signals': signals,
                           'conflicting_signals': conflicts,
                           'explanation': f"Catalog entry {equipment['model_name']}: " + '; '.join(signal['source'] + ' ' + signal['rule'] for signal in reliable or signals),
                           'source_url': equipment['source_url']})
    candidates.sort(key=lambda row: (-row['rule_score'], row['candidate_id']))
    candidates = candidates[:3]
    mismatch = []
    if candidates:
        mismatch = candidates[0]['conflicting_signals'].copy()
    ocr_families = {value['normalized'][:6] for source, value in observations if source != 'user_text'
                    and value['normalized'][:6] in {row['equipment_family'] for row in catalog}}
    ocr_series = {'-'.join(value['normalized'].split('-')[:2]) for source, value in observations
                  if source != 'user_text' and '-' in value['normalized']}
    if len(ocr_families) > 1 or len(ocr_series) > 1:
        mismatch.append('Uploaded images contain different equipment families or subtypes; select the intended equipment explicitly.')
        for item in candidates:
            if item['match_level'] == 'HIGH':
                item['match_level'] = 'MEDIUM'
    return {'input_identifiers': user_ids, 'ranked_candidates': candidates, 'mismatch_warnings': mismatch,
            'confirmation_status': 'SUGGESTED' if candidates and candidates[0]['rule_score'] >= 45 else 'UNCONFIRMED'}
