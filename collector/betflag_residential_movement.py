import json, pathlib, hashlib, calendar
from datetime import datetime, timezone, timedelta

FEED=pathlib.Path('feed')
CURRENT=FEED/'betflag-residential-current.json'
STATE=FEED/'betflag-residential-movement.json'


def last_sunday(year,month):
 last_day=calendar.monthrange(year,month)[1]
 d=datetime(year,month,last_day)
 return last_day-((d.weekday()+1)%7)


def rome_tz_for_local(naive):
 # EU daylight-saving rule: last Sunday of March 02:00 local to
 # last Sunday of October 03:00 local. Avoids a tzdata dependency on Windows runners.
 y=naive.year
 dst_start=datetime(y,3,last_sunday(y,3),2,0)
 dst_end=datetime(y,10,last_sunday(y,10),3,0)
 return timezone(timedelta(hours=2 if dst_start<=naive<dst_end else 1))


def localize_rome(naive):
 return naive.replace(tzinfo=rome_tz_for_local(naive))


def iso_dt(v):
 if not v: return None
 if isinstance(v,(int,float)):
  n=float(v)
  if n>10_000_000_000: n/=1000.0
  try: return datetime.fromtimestamp(n,tz=timezone.utc)
  except Exception: return None
 s=str(v).strip()
 try:
  d=datetime.fromisoformat(s.replace('Z','+00:00'))
  return localize_rome(d) if d.tzinfo is None else d
 except Exception: pass
 for fmt in ('%d-%m-%Y %H:%M','%d/%m/%Y %H:%M','%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M'):
  try: return localize_rome(datetime.strptime(s,fmt))
  except Exception: pass
 return None


def qid(row):
 identity=[
  row.get('match_market_id'),row.get('event_id'),row.get('player'),row.get('market'),
  row.get('line'),row.get('selection'),row.get('selection_id'),row.get('market_id')
 ]
 raw='|'.join('' if v is None else str(v) for v in identity)
 return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:24]


def load_state():
 if not STATE.exists():
  return {
   'schema_version':'betflag-residential-movement-v2',
   'source_class':'BETFLAG_AAMS_DIRECT',
   'true_open_policy':'TRUE OPEN is immutable and certified only by explicit BetFlag source evidence. If a quote first appears after an earlier healthy scan, its first-availability price is frozen separately as CAPTURED OPEN.',
   'quotes':{}
  }
 try:
  data=json.loads(STATE.read_text(encoding='utf-8'))
  data['schema_version']='betflag-residential-movement-v2'
  data.setdefault('quotes',{})
  return data
 except Exception:
  raise SystemExit('Existing movement state is unreadable; refusing to overwrite it.')


def checkpoint(ms,label,target,at,odd,start):
 if not start: return
 mins=(start-at).total_seconds()/60.0
 if mins < 0: return
 distance=abs(mins-target)
 # Polling is normally every 5 minutes. Keep the closest observation inside a broad
 # window so schedule jitter cannot erase T-40/T-30 evidence.
 if distance>8: return
 old=ms.setdefault('checkpoints',{}).get(label)
 if old is None or distance < float(old.get('distance_minutes',999)):
  ms['checkpoints'][label]={
   'at':at.isoformat(),'odd':odd,'minutes_to_kickoff':round(mins,2),
   'distance_minutes':round(distance,2),'source':'BETFLAG_AAMS_DIRECT_RESIDENTIAL'
  }


def status_summary(ms):
 if ms.get('true_open_odd') is not None:
  return 'TRUE_OPEN_CERTIFIED_FULL_MOVEMENT'
 if ms.get('captured_open_odd') is not None:
  return 'OPEN_CAPTURED_AT_FIRST_BETFLAG_AVAILABILITY'
 return 'TRUE OPEN BETFLAG NON CERTIFICATA — MOVIMENTO INCOMPLETO'


def main():
 if not CURRENT.exists(): raise SystemExit('Missing residential current feed')
 feed=json.loads(CURRENT.read_text(encoding='utf-8'))
 if not feed.get('source_healthy'): raise SystemExit('Residential BetFlag source is not healthy; movement state preserved')
 fetched=iso_dt(feed.get('generated_at')) or datetime.now(timezone.utc)
 if fetched.tzinfo is None: fetched=fetched.replace(tzinfo=timezone.utc)
 state=load_state()
 # If a previous healthy scan exists, a quote absent from the persisted state and present
 # now has genuinely appeared after our monitoring started. Freeze that first captured
 # BetFlag availability price forever; do not confuse it with source-certified TRUE OPEN.
 prior_success=state.get('last_success_at') if state.get('source_healthy') else None
 seen=0; changed=0; certified=0; new_quotes=0; captured_new_opens=0

 for row in feed.get('rows') or []:
  odd=row.get('odd')
  if not isinstance(odd,(int,float)): continue
  key=qid(row); seen+=1
  ms=state['quotes'].get(key)
  if ms is None:
   captured=bool(prior_success)
   ms={
    'quote_id':key,
    'identity':{
     'event_id':row.get('event_id'),'match_market_id':row.get('match_market_id'),
     'match':row.get('match'),'match_start':row.get('match_start'),'player':row.get('player'),
     'market':row.get('market'),'line':row.get('line'),'selection':row.get('selection'),
     'selection_id':row.get('selection_id'),'market_id':row.get('market_id'),'odds_id':row.get('odds_id')
    },
    'first_seen_at':fetched.isoformat(),'first_seen_odd':odd,
    'captured_open_odd':odd if captured else None,
    'captured_open_at':fetched.isoformat() if captured else None,
    'captured_open_basis':'ABSENT_FROM_PREVIOUS_HEALTHY_RESIDENTIAL_SCAN' if captured else None,
    'previous_healthy_scan_at':prior_success if captured else None,
    'open_status':'OPEN_CAPTURED_AT_FIRST_BETFLAG_AVAILABILITY' if captured else 'FIRST_OBSERVED_ONLY',
    'true_open_odd':None,'true_open_at':None,'true_open_source_field':None,
    'current_odd':odd,'current_at':fetched.isoformat(),
    'change_count':0,'changes':[],
    'checkpoints':{},'last_seen_at':fetched.isoformat()
   }
   state['quotes'][key]=ms; new_quotes+=1
   if captured: captured_new_opens+=1
  else:
   # Backward-compatible defaults for records created before v2.
   ms.setdefault('captured_open_odd',None)
   ms.setdefault('captured_open_at',None)
   ms.setdefault('captured_open_basis',None)
   ms.setdefault('previous_healthy_scan_at',None)
   for k,v in {'match':row.get('match'),'match_start':row.get('match_start'),'odds_id':row.get('odds_id')}.items():
    if v not in (None,''): ms.setdefault('identity',{})[k]=v

  # A real opening quote is fixed forever once BetFlag explicitly certifies it.
  source_open=row.get('betflag_opening_odd')
  source_field=row.get('betflag_opening_odd_field')
  if isinstance(source_open,(int,float)) and source_open>1:
   if ms.get('true_open_odd') is None:
    ms['true_open_odd']=source_open
    ms['true_open_at']=row.get('betflag_source_open_at') or None
    ms['true_open_source_field']=source_field
    ms['open_status']='TRUE_OPEN_BETFLAG_SOURCE_CERTIFIED'
   elif float(ms.get('true_open_odd')) != float(source_open):
    ms.setdefault('opening_conflicts',[]).append({
     'at':fetched.isoformat(),'existing':ms.get('true_open_odd'),'source_value':source_open,'source_field':source_field
    })
   certified+=1

  prev=ms.get('current_odd')
  if prev is not None and float(prev)!=float(odd):
   ms.setdefault('changes',[]).append({
    'at':fetched.isoformat(),'from':prev,'to':odd,'delta':round(float(odd)-float(prev),4),
    'source':'BETFLAG_AAMS_DIRECT_RESIDENTIAL'
   })
   ms['change_count']=int(ms.get('change_count') or 0)+1
   changed+=1
  ms['current_odd']=odd
  ms['current_at']=fetched.isoformat()
  ms['last_seen_at']=fetched.isoformat()
  ms['movement_status']=status_summary(ms)

  start=iso_dt(ms.get('identity',{}).get('match_start'))
  if start:
   checkpoint(ms,'T-40',40,fetched,odd,start)
   checkpoint(ms,'T-30',30,fetched,odd,start)

 state.update({
  'generated_at':fetched.isoformat(),'last_success_at':fetched.isoformat(),
  'source_healthy':True,'rows_seen':seen,
  'true_open_certified_rows':certified,
  'captured_new_opens_this_scan':captured_new_opens,
  'true_open_definition':'REAL_BETFLAG_OPENING_PRICE_ONLY — IMMUTABLE',
  'captured_open_definition':'FIRST BETFLAG PRICE SEEN FOR A QUOTE THAT WAS ABSENT FROM THE PREVIOUS HEALTHY RESIDENTIAL SCAN — IMMUTABLE, NOT SOURCE-CERTIFIED TRUE OPEN',
  'first_seen_definition':'FIRST PRICE CAPTURED BY RESIDENTIAL RADAR; NEVER A SUBSTITUTE FOR TRUE OPEN WHEN MONITORING STARTED AFTER THE MARKET WAS ALREADY AVAILABLE'
 })
 FEED.mkdir(exist_ok=True)
 STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({
  'rows_seen':seen,'new_quotes':new_quotes,'captured_new_opens':captured_new_opens,
  'price_changes':changed,'true_open_certified_rows':certified,
  'generated_at':fetched.isoformat()
 },ensure_ascii=False))

if __name__=='__main__': main()
