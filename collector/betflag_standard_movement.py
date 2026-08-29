import json,pathlib,hashlib
from datetime import datetime,timezone
F=pathlib.Path('feed'); CUR=F/'betflag-standard-current.json'; STATE=F/'betflag-standard-movement.json'; IDX=F/'betflag-movement-index.json'
def key(r):
 raw='|'.join(str(r.get(k) or '') for k in ('match_market_id','event_id','family','market','line','selection','selection_id','market_id'))
 return hashlib.sha1(raw.encode()).hexdigest()[:24]
def main():
 feed=json.loads(CUR.read_text(encoding='utf-8'))
 if not feed.get('source_healthy'): raise SystemExit('Standard BetFlag source unhealthy; preserving movement state')
 try: state=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'schema_version':'betflag-standard-movement-v1','quotes':{}}
 except Exception: raise SystemExit('Movement state unreadable; refusing overwrite')
 if not isinstance(state,dict): state={}
 state['schema_version']='betflag-standard-movement-v1'
 # Backward-compatible migration: an older diagnostic file may exist at this path.
 # Preserve metadata but always initialise the quote store required by this tracker.
 if not isinstance(state.get('quotes'),dict): state['quotes']={}
 prior=state.get('last_success_at'); now=feed.get('generated_at') or datetime.now(timezone.utc).isoformat(); changed=0; new=0
 for r in feed.get('rows') or []:
  odd=r.get('odd')
  if not isinstance(odd,(int,float)): continue
  k=key(r); q=state['quotes'].get(k)
  if q is None:
   q={'quote_id':k,'identity':{x:r.get(x) for x in ('event_id','match_market_id','match','match_start','family','market','line','selection','selection_id','market_id','odds_id')},'first_seen_at':now,'first_seen_odd':odd,'captured_open_at':now if prior else None,'captured_open_odd':odd if prior else None,'open_status':'OPEN_CAPTURED_AT_FIRST_BETFLAG_AVAILABILITY' if prior else 'FIRST_OBSERVED_ONLY','true_open_odd':None,'current_at':now,'current_odd':odd,'changes':[]}; state['quotes'][k]=q; new+=1
  else:
   q.setdefault('changes',[])
   if float(q.get('current_odd',odd))!=float(odd):
    q['changes'].append({'at':now,'from':q.get('current_odd'),'to':odd,'delta':round(float(odd)-float(q.get('current_odd')),4)}); changed+=1
  q['current_odd']=odd; q['current_at']=now; q['last_seen_at']=now
 state.update({'generated_at':now,'last_success_at':now,'source_healthy':True,'policy':'TRUE OPEN only when source-certified; captured_open is immutable first BetFlag availability after a prior healthy scan.'})
 STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
 items=[]
 for q in state['quotes'].values():
  i=q.get('identity',{}); fam=i.get('family')
  if fam not in ('1X2','OVER_UNDER','GOAL_NO_GOAL','TEAM_TOTAL','HANDICAP','DOUBLE_CHANCE'): continue
  base=q.get('true_open_odd') if q.get('true_open_odd') is not None else q.get('captured_open_odd')
  current=q.get('current_odd')
  items.append({'quote_id':q['quote_id'],'match':i.get('match'),'match_start':i.get('match_start'),'family':fam,'market':i.get('market'),'line':i.get('line'),'selection':i.get('selection'),'true_open':q.get('true_open_odd'),'captured_open':q.get('captured_open_odd'),'open_status':q.get('open_status'),'current':current,'current_at':q.get('current_at'),'delta_from_available_open':None if base is None or current is None else round(float(current)-float(base),4),'changes':q.get('changes',[])[-20:]})
 items.sort(key=lambda x:(0 if x['family']=='1X2' else 1 if x['family']=='OVER_UNDER' else 2,str(x.get('match')),str(x.get('market')),str(x.get('line')),str(x.get('selection'))))
 IDX.write_text(json.dumps({'schema_version':'betflag-movement-index-v1','generated_at':now,'priority':['1X2','OVER_UNDER'],'rows':items},ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'movement_rows':len(state['quotes']),'index_rows':len(items),'new':new,'changed':changed},ensure_ascii=False))
if __name__=='__main__': main()
