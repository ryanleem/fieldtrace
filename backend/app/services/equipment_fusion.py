"""Catalog-constrained identity granularity. Appearance cannot confirm a subtype."""
import re
from app.services.equipment_matching import rank_equipment
from app.services.equipment_parsing import extract_identifiers


def fuse_identity(entered, ocr, catalog, visual=None):
    ranking = rank_equipment(entered, ocr, catalog)
    candidates = ranking['ranked_candidates']
    by_id = {row['id']: row for row in catalog}
    # Rank supported nameplate signals before optional typed identity; no symptoms.
    def priority(row):
        signals = row['matched_signals']
        plate = [s for s in signals if s['source'].startswith('nameplate')]
        return (0 if any(s['points']>=90 for s in plate) else
                1 if any(s['points']>=45 for s in plate) else
                2 if any(s['source']=='user_text' and s['points']>=45 for s in signals) else 3,
                -row['rule_score'])
    candidates.sort(key=priority)
    observations = (visual or {}).get('images', [])
    families = {}
    for observation in observations:
        if not observation['observed_features'] and not observation['observed_text'].strip():
            continue
        proposed = observation['candidate_family']
        for row in catalog:
            if observation['candidate_manufacturer'] and observation['candidate_manufacturer'].casefold()!=row['manufacturer'].casefold():
                continue
            visible_ids = extract_identifiers(observation['observed_text'])
            if proposed==row['equipment_family'] or observation['candidate_model']==row['model_name'] or any(v['normalized']==row['equipment_family'] or v['normalized'].startswith(row['model_name']) for v in visible_ids):
                families.setdefault(row['equipment_family'], {})[observation['image_index']] = observation
    top = candidates[0] if candidates else None
    reliable = top and any(s['points']>=45 for s in top['matched_signals'])
    partial_families = set()
    for observation in ocr:
        for value in observation['parsed']['identifiers']:
            fragment=value['normalized']
            if len(fragment)>=5:
                partial_families.update(row['equipment_family'] for row in catalog if row['equipment_family'].startswith(fragment))
    if len(partial_families)==1 and not (top and any(s['source'].startswith('nameplate') and s['points']>=45 for s in top['matched_signals'])):
        family=next(iter(partial_families))
        matches=[r for r in candidates if r['equipment_family']==family]
        if matches:
            top=matches[0]
            reliable=any(s['points']>=45 for s in top['matched_signals'])
    family = top['equipment_family'] if top and (reliable or len(partial_families)==1) else (next(iter(families)) if len(families)==1 else None)
    warnings = list(ranking['mismatch_warnings'])
    if family:
        entered_families={r['equipment_family'] for r in catalog for value in extract_identifiers(entered or '') if value['normalized'].startswith(r['equipment_family'])}
        if entered_families and family not in entered_families:
            warnings.append('Equipment evidence conflicts: readable photo text and entered model text indicate different families.')
    if len(families)>1:
        warnings.append('Photo evidence suggests different equipment families. Provide a clear nameplate for the intended equipment.')
    if family and any(f!=family for f in families):
        warnings.append('Visual family cues differ from the readable/entered identity. Review the nameplate before confirming.')
    result = dict(specificity='insufficient', label='Unable to identify confidently from the available photos.',
                  confidence='LOW', why='No supported identity has enough readable or distinctive evidence.',
                  to_confirm='Upload a clear nameplate or front-panel photo.', exact_type_confirmed=False)
    for item in candidates:
        item['confirmable'] = any(s['points']>=45 and s['rule'] in ('exact model','catalog alias','full type-code prefix (series match; full SKU not validated)') for s in item['matched_signals'])
    if family:
        rows=[r for r in catalog if r['equipment_family']==family]
        manufacturer=rows[0]['manufacturer']
        signals=top['matched_signals'] if top and top['equipment_family']==family else []
        exact=next((s for s in signals if s['source'].startswith('nameplate') and s['points']>=90 and s['rule'].startswith('full type-code')),None)
        model_supported=bool(top and top['equipment_family']==family and top.get('confirmable'))
        views=families.get(family,{})
        consistent=sum(o['confidence'] in ('HIGH','MEDIUM') for o in views.values())>=2
        confidence = top['match_level'] if reliable and top and top['equipment_family']==family else ('MEDIUM' if consistent or len(partial_families)==1 else 'LOW')
        if warnings and not exact: confidence='MEDIUM' if confidence=='HIGH' else confidence
        if exact:
            result.update(specificity='exact_type',label=f"{manufacturer} {exact['identifier']}",confidence=confidence,
                          why='Readable nameplate text matches a supported catalog series.', exact_type_confirmed=True,
                          to_confirm='Confirm the equipment below. The full type code is observed text; its complete SKU is not catalog-validated.')
        elif model_supported:
            result.update(specificity='supported_model',label=f"{manufacturer} {top['candidate_model']}",confidence=confidence,
                          why='Readable model text matches the supported catalog. Exact full type code is not confirmed.',
                          to_confirm='Review the nameplate and confirm the catalog model below.')
        else:
            result.update(specificity='model_family',label=f'Likely {manufacturer} {family} family',confidence=confidence,
                          why='Partial readable text and catalog matching narrow the family.' if partial_families or reliable else 'Visible enclosure and control-layout cues suggest this family; appearance is provisional.',
                          to_confirm='Upload a clear model label or nameplate to establish the subtype. Exact type code is not confirmed.')
        if not top or top['equipment_family']!=family:
            # Family evidence is a summary only, not fabricated exact-model candidates.
            ranking['ranked_candidates']=[]
        if top and top['equipment_family']==family and candidates[0]!=top:
            candidates.remove(top);candidates.insert(0,top)
        if top:
            warnings.extend(w for w in top['conflicting_signals'] if w not in warnings)
    elif any(r['manufacturer'].casefold() in o['raw_text'].casefold() for r in catalog for o in ocr) or any(o.get('candidate_manufacturer') and o['candidate_manufacturer'].casefold() in o['observed_text'].casefold() for o in observations):
        brands={r['manufacturer'] for r in catalog}
        seen=[brand for brand in brands if any(brand.casefold() in o['observed_text'].casefold() for o in observations) or any(brand.casefold() in o['raw_text'].casefold() for o in ocr)]
        if len(seen)==1:
            result.update(specificity='manufacturer',label=f'{seen[0]} equipment; family unconfirmed',why='Branding is readable, but model-family evidence is insufficient.')
    ranking['mismatch_warnings']=warnings
    ranking['identification_evidence']={'summary':result,'visual':visual or {},'selected_image_hashes':[o['sha256'] for o in ocr if 'sha256' in o]}
    return ranking
