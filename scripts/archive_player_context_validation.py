#!/usr/bin/env python3
import json, pathlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict

ROOT=pathlib.Path('feed'); NOW_DT=datetime.now(timezone.utc); NOW=NOW_DT.isoformat(); ROME=ZoneInfo('Europe/Rome')
def load(name,default):
    p=ROOT/name
    try:return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception:return default
def parse_dt(s):
    if not s:return None
    try:return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:
        try:return datetime.strptime(str(s),'%d-%m-%Y %H:%M').replace(tzinfo=ROME).astimezone(timezone.utc)
        except Exception:return None
def kickoff_for(lu,snap=None):
    d=parse_dt((lu or {}).get('start_utc'))
    if d:return d
    d=parse_dt((lu or {}).get('start_time'))
    if d:return d
    if snap:
        d=parse_dt(snap.get('start_utc')) or parse_dt(snap.get('start_time'))
        if d:return d
    return None
def actual_minutes(kickoff,when=NOW_DT):
    return None if not kickoff else round((kickoff-when).total_seconds()/60,3)

ctx=load('player-matchup-context-current.json',{'matches':[]});heat=load('player-heatmap-context-current.json',{'matches':[]})
lineups=load('lineups-current.json',{'matches':[]});props=load('player-props-current.json',{'rows':[]});movement=load('odds-movement-state.json',{'records':{}})
ledger_path=ROOT/'player-context-validation-ledger.json';ledger=load('player-context-validation-ledger.json',{'schema_version':'player-context-oos-v3','entries':{}});entries=ledger.get('entries') or {}
LU={str(m.get('match_market_id')):m for m in lineups.get('matches') or []}
HM={}
for m in heat.get('matches') or []:
    mmid=str(m.get('match_market_id') or ''); hfp=str(m.get('xi_fingerprint') or '')
    for t in m.get('teams') or []:
        tid=str(t.get('team_id') or '')
        for p in t.get('players') or []:HM[(mmid,hfp,tid,str(p.get('player_id') or ''))]=p
PROP_MM=defaultdict(list);PROP_EID=defaultdict(list)
for r in props.get('rows') or []:
    if not isinstance(r,dict):continue
    if r.get('match_market_id') is not None:PROP_MM[str(r.get('match_market_id'))].append(r)
    if r.get('match_event_id') is not None:PROP_EID[str(r.get('match_event_id'))].append(r)
MOV_EID=defaultdict(list)
for r in (movement.get('records') or {}).values():
    if isinstance(r,dict) and r.get('event_id') is not None:MOV_EID[str(r.get('event_id'))].append(r)

def player_snapshot(p,hm):
    keys=('player_id','player','current_position_id','current_usual_position_id','sample_matches','appearances','starts','start_rate','avg_minutes_when_selected','p60_preliminary','p75_preliminary','p90_preliminary','minutes_model_status','historical_start_pos_x','historical_start_pos_y','historical_role_zone','shots','shot_xg','shots_on_target','shot_origin_x','shot_origin_y','dominant_shot_zone','shot_situations','shot_types')
    out={k:p.get(k) for k in keys if k in p}
    if hm:
        for k in ('heatmap_status','heatmap_offered_matches','heatmap_bridge_matches','heatmap_sample_matches','heatmap_location_samples','heatmap_centroid_x','heatmap_centroid_y','heatmap_dispersion','heatmap_dominant_zone','heatmap_final_third_share','heatmap_box_share','heatmap_central_share','heatmap_model_status'):
            if k in hm:out[k]=hm.get(k)
    return out
def prop_snapshot(rows):
    by=defaultdict(list)
    for r in rows:
        pl=str(r.get('player') or '')
        if not pl or len(by[pl])>=30:continue
        by[pl].append({k:r.get(k) for k in ('market','line','selection','odd','requested_market','fetched_at')})
    return dict(by)
def standard_market_snapshot(eid):
    out=[]
    for r in MOV_EID.get(str(eid),[]):
        if r.get('source')!='GOLDBET_DIRECT_STANDARD':continue
        m=str(r.get('market') or '').lower();sel=str(r.get('selection') or '').upper()
        if m=='1x2' or (sel=='OVER' and ('over' in m or 'total' in m)):
            out.append({k:r.get(k) for k in ('market','line','selection','true_open_status','true_open_price','first_seen_price','current_price','checkpoints','last_observed_at')})
    return out[:40]

# Repair older ledger versions: a stale upstream minutes_to_start must never make a post-kickoff snapshot valid.
repaired=invalidated=0
for key,e in list(entries.items()):
    if not isinstance(e,dict):continue
    first=e.get('first_pre_kickoff_snapshot') or {}; latest=e.get('latest_pre_kickoff_snapshot') or {}; mmid=str(first.get('match_market_id') or latest.get('match_market_id') or '')
    ko=kickoff_for(LU.get(mmid),first or latest)
    if not ko:continue
    def valid_snap(s):
        c=parse_dt((s or {}).get('captured_at'));return bool(c and c<ko)
    if first and valid_snap(first):
        # Normalize the first snapshot's true distance to kickoff without altering its feature values.
        c=parse_dt(first.get('captured_at'));first['actual_minutes_to_start']=round((ko-c).total_seconds()/60,3);first['start_utc']=ko.isoformat()
    elif first:
        e['validation_status']='INVALID_FIRST_SNAPSHOT_AFTER_KICKOFF';invalidated+=1
    if latest and not valid_snap(latest):
        if first and valid_snap(first):
            e['latest_pre_kickoff_snapshot']=json.loads(json.dumps(first));e['repair_note']='Latest snapshot captured after real kickoff was discarded; reset to valid first pre-kickoff snapshot.';repaired+=1
        else:
            e['validation_status']='NO_VALID_PRE_KICKOFF_SNAPSHOT';invalidated+=1
    elif latest:
        c=parse_dt(latest.get('captured_at'));latest['actual_minutes_to_start']=round((ko-c).total_seconds()/60,3);latest['start_utc']=ko.isoformat()

captured=updated=0
for m in ctx.get('matches') or []:
    mmid=str(m.get('match_market_id') or '');eid=str(m.get('match_event_id') or '');lu=LU.get(mmid) or {};line=lu.get('lineup') or {}
    if lu.get('status') not in ('SOURCE_CONFIRMED','CROSS_CONFIRMED') or line.get('lineup_type')!='standard' or not line.get('confirmed'):continue
    fp=str(m.get('xi_fingerprint') or '')
    if not fp or fp!=str(line.get('xi_fingerprint') or ''):continue
    ko=kickoff_for(lu,m)
    mt=actual_minutes(ko)
    if mt is None or mt<=0 or mt>90:continue
    key=f'{eid}|{fp}';teams=[]
    for t in m.get('teams') or []:
        tid=str(t.get('team_id') or '');cm=t.get('opponent_concession_map') or {};ps=[]
        for p in t.get('players') or []:ps.append(player_snapshot(p,HM.get((mmid,fp,tid,str(p.get('player_id') or '')))))
        teams.append({'team_id':t.get('team_id'),'team':t.get('team'),'recent_match_features_available':t.get('recent_match_features_available'),'players':ps,'opponent_concession_map':{'sample_matches':cm.get('sample_matches'),'zones':(cm.get('zones') or [])[:8],'situations':(cm.get('situations') or [])[:8]}})
    rows=PROP_MM.get(mmid) or PROP_EID.get(eid) or []
    snap={'captured_at':NOW,'actual_minutes_to_start':mt,'source_minutes_to_start':m.get('minutes_to_start'),'start_utc':ko.isoformat(),'match_market_id':mmid,'match_event_id':m.get('match_event_id'),'match':m.get('match'),'league':m.get('league'),'start_time':m.get('start_time'),'xi_fingerprint':fp,'feature_source_generated_at':ctx.get('generated_at'),'heatmap_source_generated_at':heat.get('generated_at'),'feature_policy':'Prospective raw-feature snapshot only. Eligibility is based on real kickoff timestamp computed at capture; stale upstream countdown cannot authorize a post-kickoff snapshot. Minutes and heatmap features remain uncalibrated context until OOS validation.','teams':teams,'player_props':prop_snapshot(rows),'player_props_source':'shared AAMS GoldBet-aligned; player prices not independently GoldBet-certified','standard_goldbet_markets':standard_market_snapshot(eid)}
    if key not in entries:
        entries[key]={'key':key,'created_at':NOW,'first_pre_kickoff_snapshot':snap,'latest_pre_kickoff_snapshot':snap,'outcome_status':'PENDING','validation_status':'VALID_PRE_KICKOFF'};captured+=1
    else:
        e=entries[key];prev=e.get('latest_pre_kickoff_snapshot') or {}
        prev_mt=prev.get('actual_minutes_to_start')
        try:prev_mt=float(prev_mt)
        except Exception:prev_mt=9999
        if 0<mt<=prev_mt:e['latest_pre_kickoff_snapshot']=snap;e['validation_status']='VALID_PRE_KICKOFF';updated+=1
if len(entries)>5000:entries=dict(sorted(entries.items(),key=lambda kv:str(kv[1].get('created_at') or ''),reverse=True)[:5000])
ledger={'schema_version':'player-context-oos-v3','updated_at':NOW,'method':'Immutable first + latest valid PRE-KICKOFF snapshot per exact XI fingerprint. Eligibility uses real kickoff timestamp, never cached countdown. Includes real heatmap density when available; outcomes joined only later.','entry_count':len(entries),'captured_this_run':captured,'updated_this_run':updated,'repaired_post_kickoff_latest_this_run':repaired,'invalidated_entries_this_run':invalidated,'entries':entries}
ROOT.mkdir(exist_ok=True);ledger_path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:ledger[k] for k in ('schema_version','entry_count','captured_this_run','updated_this_run','repaired_post_kickoff_latest_this_run','invalidated_entries_this_run')},ensure_ascii=False,indent=2))
