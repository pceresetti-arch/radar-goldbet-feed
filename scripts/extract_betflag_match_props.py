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
    focus_players = target.get('focus_players') or []
    focus_norm = [(p, norm(p)) for p in focus_players]
    matched = []
    focus_rows = []
    for r in rows:
        belongs = False
        if event_id is not None and str(r.get('event_id')) == str(event_id):
            belongs = True
        else:
            m = norm(r.get('match'))
            if qterms and all(t in m for t in qterms):
                belongs = True
        if not belongs:
            continue
        matched.append(r)
        player_norm = norm(r.get('player'))
        if any(fp and fp in player_norm for _, fp in focus_norm):
            focus_rows.append(r)
    out_matches.append({
        'q': target.get('q'),
        'event_id': event_id,
        'row_count': len(matched),
        'focus_players': focus_players,
        'focus_row_count': len(focus_rows),
        'focus_rows': focus_rows,
        'rows': matched,
    })

out = {
    'schema_version': 'betflag-match-props-v2',
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
print(json.dumps({'source_healthy': out['source_healthy'], 'matches': [{'q':x['q'],'event_id':x['event_id'],'row_count':x['row_count'],'focus_row_count':x['focus_row_count']} for x in out_matches]}, ensure_ascii=False))
