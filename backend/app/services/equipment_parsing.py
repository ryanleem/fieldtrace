"""Deterministic extraction; preserve observations separately from normalization."""
import re

DASHES = str.maketrans({c: "-" for c in "‐‑‒–—−"})
FAMILIES = {"ACS880", "ACS580", "ACH580"}
# The prefix limits O/0 repair to identifier contexts, never arbitrary serials/ratings.
IDENTIFIER = re.compile(r"\bAC[SH]\s*[0-9O]{2,3}(?:\s*[-‐‑‒–—−]\s*[A-Z0-9]+)*(?:\+[A-Z0-9]+)*\b", re.I)


def normalize_identifier(raw):
    normalized = re.sub(r"\s+", "", raw.upper().translate(DASHES))
    repairs = []
    family = normalized.split("-", 1)[0]
    if re.fullmatch(r"AC[SH][0-9O]{3}", family):
        corrected = family[:3] + family[3:].replace("O", "0")
        if corrected in FAMILIES and corrected != family:
            normalized = corrected + normalized[len(family):]
            repairs.append("O->0 in a recognized catalog family numeric segment")
    if re.match(r"^(ACS880|ACS580|ACH580)-O1(?:-|$)", normalized):
        normalized = normalized.replace("-O1", "-01", 1)
        repairs.append("O->0 in catalog subtype 01")
    return {"raw": raw, "normalized": normalized, "normalization_notes": repairs}


def extract_identifiers(text):
    observations = [normalize_identifier(match.group()) for match in IDENTIFIER.finditer(text)]
    # Explicit catalog aliases, such as ACS88001, are retained without correction.
    for match in re.finditer(r"\b(?:ACS88001|ACS58001|ACH58001)\b", text, re.I):
        observations.append(normalize_identifier(match.group()))
    unique = {}
    for item in observations:
        unique[(item['raw'], item['normalized'])] = item
    return list(unique.values())


def parse_fields(text):
    identifiers = extract_identifiers(text)
    full = [value for value in identifiers if '-' in value['normalized']]
    values = full or identifiers
    unique = {value['normalized'] for value in values}
    model = values[0] if len(unique) == 1 else None
    fields = {name: None for name in ('manufacturer', 'equipment_family', 'model_number', 'type_code',
                                     'serial_number', 'voltage', 'current', 'power', 'frequency', 'fault_display_code')}
    raw_values = {}
    if re.search(r"\bABB\b", text, re.I):
        fields['manufacturer'] = 'ABB'
        raw_values['manufacturer'] = re.search(r"\bABB\b", text, re.I).group()
    if model:
        fields['model_number'] = model['normalized']
        raw_values['model_number'] = model['raw']
        family = model['normalized'][:6]
        if family in FAMILIES:
            fields['equipment_family'] = family
            raw_values['equipment_family'] = model['raw']
        # A full type code is an observed designation, not a verified SKU/rating.
        if model['normalized'].count('-') >= 3:
            fields['type_code'] = model['normalized']
            raw_values['type_code'] = model['raw']
    quantity = r"\d+(?:[.,]\d+)?(?:\s*[-/]\s*\d+(?:[.,]\d+)?)?\s*"
    for name, unit in [('voltage', r'V(?:AC|DC)?'), ('current', 'A'), ('power', r'kW|W|HP'), ('frequency', 'Hz')]:
        matches = list(re.finditer(r'(?<![\w.-])(' + quantity + r'(?:' + unit + r'))\b', text, re.I))
        found = list(dict.fromkeys(match.group(1) for match in matches))
        if len(found) == 1:
            fields[name] = found[0]
            raw_values[name] = found[0]
    for name, pattern in [
        ('serial_number', r'(?im)\b(?:SERIAL(?:\s*(?:NUMBER|NO\.?))?|S/N|SN)\s*[:=#]?\s*([A-Z0-9][A-Z0-9./-]{2,})'),
        ('fault_display_code', r'(?im)\b(?:FAULT|ERROR|DISPLAY)(?:\s*CODE)?\s*[:=#]?\s*([A-Z0-9]{4,8})\b'),
    ]:
        match = re.search(pattern, text)
        if match and any(char.isdigit() for char in match.group(1)):
            fields[name] = match.group(1)
            raw_values[name] = match.group(1)
    return {'fields': fields, 'raw_values': raw_values, 'identifiers': identifiers}
