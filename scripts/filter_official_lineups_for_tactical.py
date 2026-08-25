#!/usr/bin/env python3
import json
import pathlib

src = pathlib.Path('feed/lineups-current.json')
out = pathlib.Path('feed/lineups-official-for-tactical.json')
try:
    payload = json.loads(src.read_text(encoding='utf-8'))
except Exception:
    payload = {'matches': []}

matches = []
for m in payload.get('matches') or []:
    line = m.get('lineup') or {}
    official = (
        m.get('status') in ('SOURCE_CONFIRMED', 'CROSS_CONFIRMED')
        and bool(line.get('confirmed'))
        and str(line.get('lineup_type') or '').lower() == 'standard'
        and not bool(line.get('historical_reference'))
    )
    if official:
        matches.append(m)

filtered = {**payload, 'matches': matches, 'official_tactical_gate': True, 'source_match_count': len(payload.get('matches') or []), 'official_match_count': len(matches)}
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'source_match_count': filtered['source_match_count'], 'official_match_count': filtered['official_match_count']}, ensure_ascii=False))
