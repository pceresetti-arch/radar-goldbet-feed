#!/usr/bin/env python3
import csv,json,math,random
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"feed/historical/markets/b365-1x2-early-close-movement-oos-v1.json"
CFG=[
 ("Netherlands","feed/historical/netherlands/eredivisie-2022-2026-regular.csv","feed/historical/netherlands","N1"),
 ("Portugal","feed/historical/portugal/primeira-liga-2022-2026-regular.csv","feed/historical/portugal","P1"),
 ("Germany2","feed/historical/germany2/2-bundesliga-2022-2026-regular.csv","feed/historical/germany2","D2"),
 ("Germany1","feed/historical/germany1/bundesliga-2022-2026-regular.csv","feed/historical/germany1","D1"),
 ("Spain1","feed/historical/spain1/laliga-2022-2026-regular.csv","feed/historical/spain1","SP1"),
 ("England1","feed/historical/england1/premier-league-2022-2026-regular.csv","feed/historical/england1","E0"),
 ("Scotland1","feed/historical/scotland1/scottish-premiership-2022-2026-regular.csv","feed/historical/scotland1","SC0")]
SEASONS=["2022-2023","2023-2024","2024-2025","2025-2026"]
BINS=[("0_to_1pp",0,.01),("1_to_2pp",.01,.02),("2_to_3pp",.02,.03),("ge_3pp",.03,99)]
SIDES=["H","D","A"]
def read(p):
 with open(ROOT/p,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def date(s):
 for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
  try:return datetime.strptime((s or "").strip(),fmt).date().isoformat()
  except ValueError:pass
 raise ValueError(s)
def num(x):
 try:
  v=float(x);return v if math.isfinite(v) and v>1 else None
 except:return None
def probs(a):
 inv=[1/x for x in a];z=sum(inv);return [x/z for x in inv]
def ll(p,y):
 return -math.log(max(p[y],1e-12))
def br(p,y):
 return sum((p[i]-(1 if i==y else 0))**2 for i in range(3))
def metric(items,key):
 n=len(items);return {"n":n,"brier":sum(br(x[key],x["y"]) for x in items)/n,"log_loss":sum(ll(x[key],x["y"]) for x in items)/n,
 "accuracy":sum(max(range(3),key=lambda i:x[key][i])==x["y"] for x in items)/n}
def q(a,z):
 a=sorted(a);p=(len(a)-1)*z;i=int(p);j=min(i+1,len(a)-1);w=p-i;return a[i]*(1-w)+a[j]*w
def paired(items,n=10000):
 rng=random.Random(120902);N=len(items);b=[];l=[]
 for _ in range(n):
  s=[items[rng.randrange(N)] for __ in range(N)]
  b.append(sum(br(x["p_close"],x["y"])-br(x["p_early"],x["y"]) for x in s)/N)
  l.append(sum(ll(x["p_close"],x["y"])-ll(x["p_early"],x["y"]) for x in s)/N)
 return {"draws":n,"brier_delta_close_minus_early_ci95":[q(b,.025),q(b,.975)],"log_loss_delta_close_minus_early_ci95":[q(l,.025),q(l,.975)]}
def strategy(items):
 if not items:return {"n":0}
 rets=[];clv=[];wins=0;by={};counts={s:0 for s in SIDES}
 for x in items:
  side=x["pick"];price=x["early_prices"][side];close=x["close_prices"][side];win=x["y"]==side
  ret=price-1 if win else -1
  rets.append(ret);clv.append(price/close-1);wins+=win;counts[SIDES[side]]+=1;by.setdefault(x["league"],[]).append(ret)
 rng=random.Random(10203);boot=[]
 for _ in range(10000):boot.append(sum(rets[rng.randrange(len(rets))] for __ in rets)/len(rets))
 return {"n":len(items),"selection_counts":counts,"hit_rate":wins/len(items),"roi":sum(rets)/len(rets),
 "mean_decimal_odds_clv":sum(clv)/len(clv),"roi_ci95":[q(boot,.025),q(boot,.975)],
 "positive_roi_leagues":sum(sum(v)/len(v)>0 for v in by.values()),"league_count":len(by)}
def binned(items):
 return {name:strategy([x for x in items if lo<=x["strength"]<hi]) for name,lo,hi in BINS}
allrows=[];coverage={};fail=[]
for league,norm,folder,code in CFG:
 accepted={(r["source_date"],r["home_team"].strip(),r["away_team"].strip()):r for r in read(norm)}
 raw={}
 for season in SEASONS:
  for r in read(f"{folder}/football-data-{code}-{season}.csv"):
   try:k=(date(r.get("Date")),r.get("HomeTeam","").strip(),r.get("AwayTeam","").strip())
   except ValueError:continue
   raw[k]=r
 joined=[];mi=mp=0
 for k,nr in accepted.items():
  r=raw.get(k)
  if not r:mi+=1;continue
  ep=[num(r.get(c)) for c in ("B365H","B365D","B365A")];cp=[num(r.get(c)) for c in ("B365CH","B365CD","B365CA")]
  if None in ep+cp:mp+=1;continue
  pe,pc=probs(ep),probs(cp);ds=[pc[i]-pe[i] for i in range(3)];pick=max(range(3),key=lambda i:ds[i])
  joined.append({"league":league,"split":nr["split"],"y":SIDES.index(nr["result"]),"p_early":pe,"p_close":pc,
   "pick":pick,"strength":ds[pick],"early_prices":ep,"close_prices":cp})
 allrows+=joined;coverage[league]={"accepted_rows":len(accepted),"joined_rows":len(joined),"missing_identity_rows":mi,"missing_price_rows":mp}
 if mi or mp:fail.append({"league":league,**coverage[league]})
dev=[x for x in allrows if x["split"]=="DEVELOPMENT"];hold=[x for x in allrows if x["split"]=="HOLDOUT"]
me,mc=metric(hold,"p_early"),metric(hold,"p_close");bd,bh=binned(dev),binned(hold)
gate={}
for name,_,_ in BINS:
 a,b=bd[name],bh[name];gate[name]={"eligible":a["n"]>=200 and b["n"]>=200,
 "passes":a["n"]>=200 and b["n"]>=200 and a["roi"]>0 and b["roi_ci95"][0]>0 and b["positive_roi_leagues"]>=5,
 "reason":"Requires n>=200 in both partitions, positive development ROI, holdout ROI CI95 above zero and positive ROI in at least 5 leagues."}
report={"schema_version":"radar-historical-b365-1x2-early-close-movement-oos-v1","generated_at":datetime.utcnow().isoformat()+"Z",
 "status":"COMPLETE_SAME_BOOK_EARLY_TO_CLOSE_DIAGNOSTIC","market":"FULL_TIME_1X2","bookmaker":"Bet365",
 "price_semantics":{"early":"Football-Data B365H/B365D/B365A provider early price without certified timestamp",
 "close":"Football-Data B365CH/B365CD/B365CA","same_bookmaker":True,"true_open_certified":False,"goldbet":False},
 "anti_hindsight":{"movement_bins_prefixed":["0-1pp","1-2pp","2-3pp",">=3pp"],"development_and_holdout_separate":True,
 "outcomes_evaluation_only":True,"no_missing_price_reconstruction":True},
 "coverage":{"development_rows":len(dev),"holdout_rows":len(hold),"total_rows":len(allrows),"by_league":coverage},
 "holdout_probability_quality":{"early":me,"close":mc,"delta_close_minus_early":{"brier":mc["brier"]-me["brier"],"log_loss":mc["log_loss"]-me["log_loss"]},"paired_bootstrap":paired(hold)},
 "movement_direction_strategy":{"definition":"Bet at the early price on the 1X2 outcome with the largest de-vigged probability increase by close.",
 "development":bd,"holdout":bh,"promotion_gate":gate},"source_failures":fail,
 "verdict":"Bet365 same-book diagnostic only. No result is GoldBet TRUE OPEN and no operational rule is promoted without passing the frozen gate."}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"coverage":report["coverage"],"quality":report["holdout_probability_quality"],"gate":gate},indent=2))
