#!/usr/bin/env python3
import csv,json,math,random
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
ROOT=Path(".");OUT=Path("feed/historical/markets/b365-1x2-elo-edge-oos-v1.json");O=["H","D","A"]
CFG=[
("Netherlands","feed/historical/netherlands/structural-oos-v1.json","feed/historical/netherlands","N1"),
("Portugal","feed/historical/portugal/structural-oos-v1.json","feed/historical/portugal","P1"),
("Germany2","feed/historical/germany2/structural-oos-v1.json","feed/historical/germany2","D2"),
("Germany1","feed/historical/germany1/structural-oos-v1.json","feed/historical/germany1","D1"),
("Spain1","feed/historical/spain1/structural-oos-v1.json","feed/historical/spain1","SP1"),
("England1","feed/historical/england1/structural-oos-v1.json","feed/historical/england1","E0"),
("Scotland1","feed/historical/scotland1/structural-oos-v1.json","feed/historical/scotland1","SC0")]
SEASONS=["2022-2023","2023-2024","2024-2025","2025-2026"];TH=[.01,.02,.03,.05,.08];L2=.01;LR=.08;IT=1800
def date(s):
 for f in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
  try:return datetime.strptime((s or "").strip(),f).date().isoformat()
  except ValueError:pass
 raise ValueError(s)
def num(x):
 try:
  v=float(x);return v if math.isfinite(v) and v>1 else None
 except:return None
def prep(tr,te):
 v=np.array([float(r["elo_diff"]) for r in tr]);m=float(v.mean());s=float(v.std()) or 1
 return np.column_stack([np.ones(len(tr)),(v-m)/s]),np.array([O.index(r["result"]) for r in tr]),np.column_stack([np.ones(len(te)),np.array([(float(r["elo_diff"])-m)/s for r in te])])
def train(x,y):
 w=np.zeros((3,x.shape[1]));oh=np.eye(3)[y]
 for _ in range(IT):
  z=x@w.T;z-=z.max(axis=1,keepdims=True);p=np.exp(z);p/=p.sum(axis=1,keepdims=True);g=(p-oh).T@x/len(x);pen=L2*w;pen[:,0]=0;w-=LR*(g+pen)
 return w
def pred(x,w):
 z=x@w.T;z-=z.max(axis=1,keepdims=True);p=np.exp(z);return p/p.sum(axis=1,keepdims=True)
def soft(z):
 m=max(z);e=[math.exp(v-m) for v in z];t=sum(e);return [v/t for v in e]
def market(odds):
 inv=[1/x for x in odds];t=sum(inv);return [x/t for x in inv]
def q(a,z):
 a=sorted(a);p=(len(a)-1)*z;i=int(p);j=min(i+1,len(a)-1);u=p-i;return a[i]*(1-u)+a[j]*u
def strategy(rows,t):
 selected=[]
 for r in rows:
  edges=[r["elo"][k]-r["market"][k] for k in range(3)];k=max(range(3),key=lambda i:edges[i])
  if edges[k]>=t:
   ret=r["odds"][k]-1 if r["y"]==k else -1
   selected.append({**r,"side":O[k],"edge":edges[k],"ret":ret})
 if not selected:return {"n":0}
 rets=[r["ret"] for r in selected];rng=random.Random(902120+int(t*1000));boots=[]
 for _ in range(10000):boots.append(sum(rets[rng.randrange(len(rets))] for __ in rets)/len(rets))
 cum=peak=0.;maxdd=0.
 for r in sorted(selected,key=lambda x:(x["date"],x["fixture"])):
  cum+=r["ret"];peak=max(peak,cum);maxdd=max(maxdd,peak-cum)
 by={}
 for r in selected:by.setdefault(r["league"],[]).append(r["ret"])
 return {"n":len(selected),"hit_rate":sum(r["ret"]>0 for r in selected)/len(selected),"mean_edge":sum(r["edge"] for r in selected)/len(selected),
 "mean_odds":sum(r["odds"][O.index(r["side"])] for r in selected)/len(selected),"roi":sum(rets)/len(rets),"roi_ci95":[q(boots,.025),q(boots,.975)],
 "max_drawdown_units":maxdd,"positive_roi_leagues":sum(sum(v)/len(v)>0 for v in by.values()),"league_count":len(by),
 "side_counts":{o:sum(r["side"]==o for r in selected) for o in O}}
dev=[];hold=[];coverage={}
for league,rp,folder,code in CFG:
 rep=json.loads(Path(rp).read_text());raw={}
 for season in SEASONS:
  with open(Path(folder)/f"football-data-{code}-{season}.csv",encoding="utf-8-sig",newline="") as f:
   for r in csv.DictReader(f):
    try:k=(date(r.get("Date")),r.get("HomeTeam","").strip(),r.get("AwayTeam","").strip())
    except ValueError:continue
    raw[k]=r
 with Path(rep["feature_dataset"]).open(encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
 d=[r for r in rows if r["split"]=="DEVELOPMENT"];seasons=sorted({r["season"] for r in d});miss_dev=miss_hold=0
 for pos in (1,2):
  tr=[r for r in d if r["season"] in seasons[:pos]];te=[r for r in d if r["season"]==seasons[pos]];x,y,xt=prep(tr,te);pp=pred(xt,train(x,y))
  for r,p in zip(te,pp):
   rr=raw.get((r["source_date"],r["home_team"].strip(),r["away_team"].strip()));od=[num(rr.get(c)) for c in ("B365H","B365D","B365A")] if rr else [None]*3
   if None in od:miss_dev+=1;continue
   dev.append({"league":league,"date":r["source_date"],"fixture":r["fixture_key"],"y":O.index(r["result"]),"elo":[float(v) for v in p],"market":market(od),"odds":od})
 model=rep["ablation_same_holdout"]["ELO_ONLY"];fn=model["features"];means=model["standardization"]["means"];scales=model["standardization"]["scales"];weights=[model["weights_by_outcome"][o] for o in O]
 hrs=[r for r in rows if r["split"]=="HOLDOUT"]
 for r in hrs:
  rr=raw.get((r["source_date"],r["home_team"].strip(),r["away_team"].strip()));od=[num(rr.get(c)) for c in ("B365H","B365D","B365A")] if rr else [None]*3
  if None in od:miss_hold+=1;continue
  xx=[1.]+[(float(r[n])-means[n])/scales[n] for n in fn];pe=soft([sum(a*b for a,b in zip(w,xx)) for w in weights])
  hold.append({"league":league,"date":r["source_date"],"fixture":r["fixture_key"],"y":O.index(r["result"]),"elo":pe,"market":market(od),"odds":od})
 coverage[league]={"rolling_development_expected":2*len(hrs),"rolling_development_scored":2*len(hrs)-miss_dev,"holdout_expected":len(hrs),"holdout_scored":len(hrs)-miss_hold,"missing_development_prices":miss_dev,"missing_holdout_prices":miss_hold}
development={f"{int(t*100)}pp":strategy(dev,t) for t in TH};holdout={f"{int(t*100)}pp":strategy(hold,t) for t in TH};gates={}
for t in TH:
 k=f"{int(t*100)}pp";a,b=development[k],holdout[k];gates[k]={"passes":a["n"]>=200 and b["n"]>=200 and a["roi"]>0 and b["roi_ci95"][0]>0 and b["positive_roi_leagues"]>=5,
 "rule":"n>=200 both partitions, positive rolling-development ROI, holdout ROI CI95 above zero, positive ROI in >=5/7 leagues"}
report={"schema_version":"radar-historical-b365-1x2-elo-edge-oos-v1","generated_at":datetime.now(timezone.utc).isoformat(),"status":"COMPLETE_ROLLING_DEVELOPMENT_AND_FROZEN_HOLDOUT",
"market":"FULL_TIME_1X2","bookmaker":"Bet365",
"design":{"rolling_development_rows":len(dev),"holdout_rows":len(hold),"thresholds_pp":[1,2,3,5,8],"one_selection_per_fixture":True,
"selection":"Outcome with maximum ELO_ONLY probability minus de-vigged Bet365 provider-early probability, if edge meets threshold",
"development_predictions":"Out-of-fold from two rolling-origin folds per league","holdout_predictions":"Persisted model fitted on all three development seasons",
"provider_early_timestamp_certified":False,"true_open":False,"goldbet":False,"outcomes_evaluation_only":True},
"coverage":coverage,"development":development,"holdout":holdout,"promotion_gates":gates,
"verdict":"No threshold may be operationally promoted unless it passes the frozen gate; Bet365 provider-early prices are not certified TRUE OPEN and cannot be relabelled GoldBet."}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({"design":report["design"],"development":development,"holdout":holdout,"promotion_gates":gates},indent=2))
