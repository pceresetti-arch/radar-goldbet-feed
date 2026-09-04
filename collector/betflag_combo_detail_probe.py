import json, pathlib, re, unicodedata
from collections import Counter
from datetime import datetime, timezone
from betflag_session_transport import BetFlagTransport

BASE='https://sportservice.betflag.it/api/sport/pregame'
AGG=1334500001
FEED=pathlib.Path('feed')
OUT=FEED/'betflag-combo-detail-availability.json'


def norm(v):
    s=unicodedata.normalize('NFD',str(v or ''))
    s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower().replace('°','')
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)


def marketish(name):
    n=norm(name)
    return bool(re.search(r'marcat|marc |assist|giocator|player|combo|doppietta|tripletta|tiri|parate|segna',n))


def extract_market_names(body):
    names=[]
    for x in walk(body):
        if not isinstance(x,dict): continue
        for k in ('mn','sn','tbN'):
            v=x.get(k)
            if isinstance(v,str) and marketish(v): names.append(v.strip())
    return sorted(set(names))


def overview_fixtures(std):
    out={}
    for x in walk(std):
        if not isinstance(x,dict): continue
        en=str(x.get('en') or '')
        if x.get('mi') is None or not en or en.startswith('('): continue
        key=norm(en)
        cur=out.setdefault(key,{'match':en,'nodes':[]})
        cur['nodes'].append({k:x.get(k) for k in ('ei','mi','ti','tai','ed','en')})
    return out


def relevant_sections(std):
    ids={0,1,2,3,4,5,6,7,8,9,10,2484}
    tab_names={}
    for node in walk(std):
        tabs=node.get('lmtW') if isinstance(node,dict) else None
        if not isinstance(tabs,list): continue
        for tab in tabs:
            if not isinstance(tab,dict): continue
            tid=tab.get('tbI'); tname=str(tab.get('tbN') or '')
            if tid is None: continue
            if re.search(r'giocator|player|marcator|combo|speciali',norm(tname)):
                try:
                    tid=int(tid); ids.add(tid); tab_names[str(tid)]=tname
                except: pass
    return sorted(ids),tab_names


def load_player_matches():
    p=FEED/'betflag-residential-current.json'
    if not p.exists(): return [], 'missing_file'
    try:
        # PowerShell 5.x Out-File -Encoding utf8 may prepend a BOM. utf-8-sig
        # accepts both BOM and normal UTF-8, avoiding silent candidate loss.
        data=json.loads(p.read_text(encoding='utf-8-sig'))
    except Exception as e:
        return [], f'parse_error:{e!r}'
    counts=Counter()
    starts={}
    for r in data.get('rows') or []:
        m=r.get('match')
        if not m: continue
        counts[m]+=1
        if r.get('match_start'): starts[m]=r.get('match_start')
    rows=[{'match':m,'player_rows':c,'match_start':starts.get(m)} for m,c in counts.items()]
    rows.sort(key=lambda x:(-(x['player_rows']),x.get('match_start') or '',x['match']))
    return rows, None


def best_fixture_node(nodes):
    ranked=sorted(nodes,key=lambda x:sum(x.get(k) is not None for k in ('tai','ti','mi','ei')),reverse=True)
    return ranked[0] if ranked else None


def main():
    now=datetime.now(timezone.utc).isoformat()
    client=BetFlagTransport(timeout=20)
    out={'schema_version':'betflag-combo-detail-availability-v2','generated_at':now,'source_class':'BETFLAG_AAMS_DIRECT','source_healthy':False,'candidate_rule':'probe only fixtures that already expose BetFlag player rows; combo availability is fixture-specific, not assumed league-wide','fixtures':[]}
    try:
        st,std=client.get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0')
        out['overview_status']=st
        if st!=200: raise RuntimeError(f'overview HTTP {st}')
        fixtures=overview_fixtures(std)
        sections,tab_names=relevant_sections(std)
        out['sections_probed']=sections
        out['section_names']=tab_names
        candidates,load_error=load_player_matches()
        out['player_feed_load_error']=load_error
        out['candidate_count_total']=len(candidates)
        candidates=candidates[:20]
        out['candidate_count']=len(candidates)
        for cand in candidates:
            f=fixtures.get(norm(cand['match']))
            row={**cand,'resolved':bool(f),'detail_attempts':[],'combo_or_player_detail_available':False,'market_names':[]}
            if not f:
                out['fixtures'].append(row); continue
            node=best_fixture_node(f['nodes'])
            row['ids']=node
            if not node or any(node.get(k) is None for k in ('ti','mi','ei')):
                row['resolution_error']='missing detail identifiers'; out['fixtures'].append(row); continue
            tai=node.get('tai') or 0
            found=set(); positive_at=None
            for idx,sec in enumerate(sections):
                url=f"{BASE}/getDetailsEventAams/{tai}/{node['ti']}/{node['mi']}/{node['ei']}/{sec}/0?channelId=0"
                try:
                    status,body=client.get(url)
                    names=extract_market_names(body) if status==200 else []
                    for n in names: found.add(n)
                    hit=bool(names)
                    row['detail_attempts'].append({'section':sec,'section_name':tab_names.get(str(sec)),'status':status,'market_name_count':len(names),'market_names':names[:40]})
                    if hit and positive_at is None: positive_at=idx
                    if positive_at is not None and idx-positive_at>=4: break
                except Exception as e:
                    row['detail_attempts'].append({'section':sec,'section_name':tab_names.get(str(sec)),'status':None,'error':repr(e)})
            row['market_names']=sorted(found)
            row['combo_or_player_detail_available']=bool(found)
            row['positive_sections']=[a['section'] for a in row['detail_attempts'] if a.get('market_name_count',0)>0]
            out['fixtures'].append(row)
        out['resolved_fixture_count']=sum(1 for x in out['fixtures'] if x.get('resolved'))
        out['fixtures_with_detail_player_markets']=sum(1 for x in out['fixtures'] if x['combo_or_player_detail_available'])
        out['source_healthy']=True
    except Exception as e:
        out['error']=repr(e)
    finally:
        out['transport']=client.diagnostics(); client.close()
    FEED.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'source_healthy':out.get('source_healthy'),'candidate_count_total':out.get('candidate_count_total'),'candidate_count':out.get('candidate_count'),'resolved_fixture_count':out.get('resolved_fixture_count'),'fixtures_with_detail_player_markets':out.get('fixtures_with_detail_player_markets'),'player_feed_load_error':out.get('player_feed_load_error'),'sections_probed':len(out.get('sections_probed') or []),'transport':out.get('transport')},ensure_ascii=False))

if __name__=='__main__': main()
