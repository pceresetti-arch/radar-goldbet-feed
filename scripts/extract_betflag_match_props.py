import json, pathlib, re, unicodedata
from datetime import datetime, timezone


def norm(v):
    s = unicodedata.normalize('NFD', str(v or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower().replace('°', '')
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())

req = json.loads(pathlib.Path('betflag-match-props-request.json').read_text(encoding='utf-8'))
feed = json.loads(pathlib.Path('feed/betflag-residential-current.json').read_text(encoding='utf-8'))
targets = req.get('matches') or []
rows = feed.get('rows') or []

out_matches = []
for target in targets:
    q = norm(target.get('q'))
    qterms = q.split()
    event_id = target.get('event_id')
    matched = []
    for r in rows:
        if event_id is not None and str(r.get('event_id')) == str(event_id):
            matched.append(r)
            continue
        m = norm(r.get('match'))
        if qterms and all(t in m for t in qterms):
            matched.append(r)
    out_matches.append({
        'q': target.get('q'),
        'event_id': event_id,
        'row_count': len(matched),
        'rows': matched,
    })

out = {
    'schema_version': 'betflag-match-props-v1',
    'requested_at': req.get('requested_at'),
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'source_class': 'BETFLAG_AAMS_DIRECT',
    'source_healthy': bool(feed.get('source_healthy')),
    'feed_generated_at': feed.get('generated_at'),
    'matches': out_matches,
}
pathlib.Path('feed/betflag-match-props-latest.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8'
)
print(json.dumps({'source_healthy': out['source_healthy'], 'matches': [{k:v for k,v in x.items() if k != 'rows'} for x in out_matches]}, ensure_ascii=False))
