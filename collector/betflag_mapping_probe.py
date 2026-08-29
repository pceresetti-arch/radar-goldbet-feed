import json, pathlib, re, unicodedata
from datetime import datetime, timezone
from betflag_session_transport import BetFlagTransport

BASE='https://sportservice.betflag.it/api/sport/pregame'
AGG=1334500001


def norm(v):
    s=unicodedata.normalize('NFD',str(v or ''))
    s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower()
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values():
            yield from walk(v)
    elif isinstance(x,list):
        for v in x:
            yield from walk(v)


def scalar_map(d):
    return {str(k):v for k,v in d.items() if v is None or isinstance(v,(str,int,float,bool))}


def main():
    out={
        'schema_version':'betflag-fixture-identity-probe-v1',
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'source_class':'BETFLAG_AAMS_DIRECT',
        'source_healthy':False,
        'standard_samples':[],
        'player_samples':[],
    }
    selected_matches=('elversberg','leverkusen','galatasaray','goztepe','lokomotiv','batrakov')
    selected_players=('patrik schick','abdulkerim bardakci','aleksey batrakov','victor osimhen')
    client=BetFlagTransport(timeout=30)
    try:
        ss,std=client.get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0')
        ps,players=client.get(f'{BASE}/getOverviewEventsAams/0/-1/0/{AGG}/2484/22884/0?channelId=0')
        out['standard_status']=ss; out['player_status']=ps
        standard=[]
        for x in walk(std):
            en=str(x.get('en') or '')
            sn=norm(x.get('sn'))
            if x.get('mi') is None or not en or en.startswith('(') or sn.startswith('giocatori'):
                continue
            n=norm(en)
            if any(t in n for t in selected_matches):
                standard.append({'scalars':scalar_map(x)})
            if len(standard)>=50: break
        out['standard_samples']=standard
        player=[]
        for x in walk(players):
            en=str(x.get('en') or '')
            if not en.startswith('('): continue
            n=norm(en)
            if any(p in n for p in selected_players):
                player.append({'scalars':scalar_map(x)})
        out['player_samples']=player[:100]
        out['source_healthy']=ss==200 and ps==200 and bool(out['player_samples'])
    except Exception as e:
        out['error']=repr(e)
    finally:
        out['transport']=client.diagnostics(); client.close()
    p=pathlib.Path('feed'); p.mkdir(exist_ok=True)
    (p/'betflag-mapping-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'source_healthy':out['source_healthy'],'standard_samples':len(out['standard_samples']),'player_samples':len(out['player_samples']),'transport':out.get('transport')},ensure_ascii=False))

if __name__=='__main__': main()
