"""Conservative candidates for duplicate visible observations, not physical tracking."""
import re
from collections import Counter
from uuid import UUID, uuid5

ORDINAL = {'low': 0, 'medium': 1, 'high': 2}


def location_key(value):
    words = re.findall(r'[a-z0-9]+', value.lower())
    # Tiny explicit alias list preserves left/right, upper/lower and component IDs.
    return ' '.join('enclosure' if word == 'housing' else word for word in words if word not in {'the', 'a', 'an'})


def aggregate(findings, session_id):
    groups = {}
    counts = Counter((f.get('equipment_id'), f['issue_type'], location_key(f['location']), str(f['image_id'])) for f in findings)
    ambiguous = {key[:3] for key, count in counts.items() if count > 1}
    for finding in findings:
        location = location_key(finding['location'])
        key = (finding.get('equipment_id'), finding['issue_type'], location)
        # Vague locations and multiple defects in the same image cannot be equated.
        if key in ambiguous or location in {'unknown', 'unspecified', 'equipment', 'surface', 'image', 'not visible'} or not location:
            key += (str(finding['id']),)
        bucket = groups.setdefault(key, [])
        match = next((group for group in bucket if str(finding['image_id']) not in {str(f['image_id']) for f in group}), None)
        if match is None:
            bucket.append([finding])
        else:
            match.append(finding)
    result = []
    for buckets in groups.values():
        for group in buckets:
            first = group[0]
            image_ids = sorted({str(item['image_id']) for item in group})
            ids = sorted(str(item['id']) for item in group)
            result.append(dict(
                id=uuid5(UUID(str(session_id)), '|'.join(ids)), session_id=session_id,
                equipment_id=first.get('equipment_id'), issue_type=first['issue_type'], location=first['location'],
                description=first['description'] + (f' Observed in {len(image_ids)} uploaded images; grouped by issue and location.' if len(image_ids) > 1 else ''),
                severity=max((f['severity'] for f in group), key=ORDINAL.get),
                # Repeated views do not increase confidence; keep the weakest support.
                visual_confidence=min((f['visual_confidence'] for f in group), key=ORDINAL.get),
                supporting_image_ids=image_ids, supporting_finding_ids=ids))
    return result
