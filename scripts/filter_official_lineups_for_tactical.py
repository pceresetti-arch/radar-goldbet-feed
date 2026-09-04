#!/usr/bin/env python3
import json
import pathlib

src = pathlib.Path('feed/lineups-current.json')
out = pathlib.Path('feed/lineups-official-for-tactical.json')

PRIMARY_SOURCE_MARKERS = {
    'OFFICIAL_CLUB', 'CLUB_OFFICIAL', 'OFFICIAL_LEAGUE', 'LEAGUE_OFFICIAL',
    'OFFICIAL_FEDERATION', 'FEDERATION_OFFICIAL'
}

try:
    payload = json.loads(src.read_text(encoding='utf-8'))
except Exception:
    payload = {'matches': []}


def upper(value):
    return str(value or '').strip().upper()


def source_names(match):
    """Collect explicit provider/source names without inventing cross-check evidence."""
    values = []
    for key in ('crosscheck_sources', 'sources', 'provider_sources', 'lineup_sources'):
        raw = match.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    name = item.get('name') or item.get('source') or item.get('provider')
                else:
                    name = item
                if name:
                    values.append(str(name).strip().lower())
    meta = match.get('source_meta') if isinstance(match.get('source_meta'), dict) else {}
    raw = meta.get('crosscheck_sources') or meta.get('sources')
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = item.get('name') or item.get('source') or item.get('provider')
            else:
                name = item
            if name:
                values.append(str(name).strip().lower())
    return sorted(set(v for v in values if v))


def source_confidence(match):
    """A provider label alone never certifies an official XI.

    CROSS_CONFIRMED is accepted only when the record carries evidence of at least
    two independent named sources. Primary official metadata can certify directly.
    """
    status = upper(match.get('status') or match.get('confirmation_status'))
    source_class = upper(match.get('source_class') or match.get('source_type'))
    source_meta = match.get('source_meta') if isinstance(match.get('source_meta'), dict) else {}
    explicit_primary = (
        source_class in PRIMARY_SOURCE_MARKERS
        or bool(match.get('official_primary_source'))
        or upper(source_meta.get('class')) in PRIMARY_SOURCE_MARKERS
        or bool(source_meta.get('official_primary_source'))
    )
    if status == 'SOURCE_CONFIRMED' and explicit_primary:
        return 'CERTIFIED_PRIMARY'
    if status == 'CROSS_CONFIRMED':
        return 'CERTIFIED_CROSSCHECK' if len(source_names(match)) >= 2 else 'PROVIDER_ONLY'
    if status == 'SOURCE_CONFIRMED':
        return 'PROVIDER_ONLY'
    if status in {'PREDICTED', 'PROBABLE'}:
        return 'PREDICTED'
    return 'MISSING'


matches = []
rejected_provider_only = 0
rejected_crosscheck_without_evidence = 0
for m in payload.get('matches') or []:
    line = m.get('lineup') or {}
    confidence = source_confidence(m)
    certified = confidence in ('CERTIFIED_PRIMARY', 'CERTIFIED_CROSSCHECK')
    standard_11v11 = (
        bool(line.get('confirmed'))
        and str(line.get('lineup_type') or '').lower() == 'standard'
        and not bool(line.get('historical_reference'))
    )
    if certified and standard_11v11:
        enriched = dict(m)
        enriched['xi_source_confidence'] = confidence
        enriched['xi_crosscheck_sources'] = source_names(m)
        matches.append(enriched)
    elif confidence == 'PROVIDER_ONLY' and standard_11v11:
        rejected_provider_only += 1
        if upper(m.get('status') or m.get('confirmation_status')) == 'CROSS_CONFIRMED':
            rejected_crosscheck_without_evidence += 1

filtered = {
    **payload,
    'matches': matches,
    'official_tactical_gate': True,
    'official_definition': 'CERTIFIED_PRIMARY or CERTIFIED_CROSSCHECK + confirmed standard 11v11; CROSS_CONFIRMED requires >=2 explicit independent source names; single-provider evidence is not official',
    'source_match_count': len(payload.get('matches') or []),
    'official_match_count': len(matches),
    'provider_only_rejected_count': rejected_provider_only,
    'crosscheck_without_evidence_rejected_count': rejected_crosscheck_without_evidence,
}
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'source_match_count': filtered['source_match_count'],
    'official_match_count': filtered['official_match_count'],
    'provider_only_rejected_count': filtered['provider_only_rejected_count'],
    'crosscheck_without_evidence_rejected_count': filtered['crosscheck_without_evidence_rejected_count'],
}, ensure_ascii=False))
