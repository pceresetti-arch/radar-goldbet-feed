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


def source_confidence(match):
    """A single live provider is useful evidence, but it is not a primary official source."""
    status = upper(match.get('status') or match.get('confirmation_status'))
    source_class = upper(match.get('source_class') or match.get('source_type'))
    source_meta = match.get('source_meta') if isinstance(match.get('source_meta'), dict) else {}
    explicit_primary = (
        source_class in PRIMARY_SOURCE_MARKERS
        or bool(match.get('official_primary_source'))
        or upper(source_meta.get('class')) in PRIMARY_SOURCE_MARKERS
        or bool(source_meta.get('official_primary_source'))
    )
    if status == 'CROSS_CONFIRMED':
        return 'CERTIFIED_CROSSCHECK'
    if status == 'SOURCE_CONFIRMED' and explicit_primary:
        return 'CERTIFIED_PRIMARY'
    if status == 'SOURCE_CONFIRMED':
        return 'PROVIDER_ONLY'
    if status in {'PREDICTED', 'PROBABLE'}:
        return 'PREDICTED'
    return 'MISSING'


matches = []
rejected_provider_only = 0
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
        matches.append(enriched)
    elif confidence == 'PROVIDER_ONLY' and standard_11v11:
        rejected_provider_only += 1

filtered = {
    **payload,
    'matches': matches,
    'official_tactical_gate': True,
    'official_definition': 'CERTIFIED_PRIMARY or CERTIFIED_CROSSCHECK + confirmed standard 11v11; single-provider SOURCE_CONFIRMED is not official',
    'source_match_count': len(payload.get('matches') or []),
    'official_match_count': len(matches),
    'provider_only_rejected_count': rejected_provider_only,
}
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'source_match_count': filtered['source_match_count'],
    'official_match_count': filtered['official_match_count'],
    'provider_only_rejected_count': filtered['provider_only_rejected_count'],
}, ensure_ascii=False))
