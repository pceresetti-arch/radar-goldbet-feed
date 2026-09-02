#!/usr/bin/env python3
import csv,json,math,random
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"feed/historical/markets/b365-ou25-early-close-movement-oos-v1.json"
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
def prob(a,b):
 ia,ib=1/a,1/b;return ia/(ia+ib)
def ll(p,y):
 p=min(max(p,1e-12),1-1e-12);return -(y*math.log(p)+(1-y)*math.log(1-p))
def metric(items,key):
 n=len(items)
 return {"n":n,"brier":sum((x[key]-x["y"])**2 for x in items)/n,"log_loss":sum(ll(x[key],x["y"]) for x in items)/n}
def q(a,z):
 a=sorted(a);p=(len(a)-1)*z;i=int(p);j=min(i+1,len(a)-1);w=p-i;return a[i]*(1-w)+a[j]*w
def paired(items,n=10000,seed=260902):
 rng=random.Random(seed);N=len(items);bd=[];ld=[]
 for _ in range(n):
  s=[items[rng.randrange(N)] for __ in range(N)]
  bd.append(sum((x["p_close"]-x["y"])**2-(x["p_early"]-x["y"])**2 for x in s)/N)
  ld.append(sum(ll(x["p_close"],x["y"])-ll(x["p_early"],x["y"]) for x in s)/N)
 return {"draws":n,"brier_delta_close_minus_early_ci95":[q(bd,.025),q(bd,.975)],"log_loss_delta_close_minus_early_ci95":[q(ld,.025),q(ld,.975)]}
def strategy(items):
 if not items:return {"n":0}
 rets=[];clv=[];wins=0
 byleague={}
 for x in items:
  over=x["delta"]>0
  price=x["early_over"] if over else x["early_under"]
  close=x["close_over"] if over else x["close_under"]
  win=(x["y"]==1) if over else (x["y"]==0)
  ret=price-1 if win else -1
  rets.append(ret);clv.append(price/close-1);wins+=win
  byleague.setdefault(x["league"],[]).append(ret)
 rng=random.Random(90210);boot=[]
 for _ in range(10000):
  boot.append(sum(rets[rng.randrange(len(rets))] for __ in rets)/len(rets))
 return {"n":len(items),"hit_rate":wins/len(items),"roi":sum(rets)/len(rets),"mean_decimal_odds_clv":sum(clv)/len(clv),
         "roi_ci95":[q(boot,.025),q(boot,.975)],"positive_roi_leagues":sum(sum(v)/len(v)>0 for v in byleague.values()),
         "league_count":len(byleague)}
def binned(items):
 return {name:strategy([x for x in items if lo<=abs(x["delta"])<hi]) for name,lo,hi in BINS}

allrows=[];coverage={};fail=[]
for league,norm,folder,code in CFG:
 nrows=read(norm);accepted={(r["source_date"],r["home_team"].strip(),r["away_team"].strip()):r for r in nrows}
 raw={}
 for season in SEASONS:
  p=f"{folder}/football-data-{code}-{season}.csv"
  for r in read(p):
   try:k=(date(r.get("Date")),r.get("HomeTeam","").strip(),r.get("AwayTeam","").strip())
   except ValueError:continue
   raw[k]=r
 joined=[];missing_identity=missing_price=0
 for k,nr in accepted.items():
  r=raw.get(k)
  if not r:missing_identity+=1;continue
  eo,eu,co,cu=[num(r.get(c)) for c in ("B365>2.5","B365<2.5","B365C>2.5","B365C<2.5")]
  if None in (eo,eu,co,cu):missing_price+=1;continue
  pe,pc=prob(eo,eu),prob(co,cu)
  joined.append({"league":league,"split":nr["split"],"y":int(int(nr["home_goals"])+int(nr["away_goals"])>=3),
   "p_early":pe,"p_close":pc,"delta":pc-pe,"early_over":eo,"early_under":eu,"close_over":co,"close_under":cu})
 allrows+=joined
 coverage[league]={"accepted_rows":len(nrows),"joined_rows":len(joined),"missing_identity_rows":missing_identity,"missing_price_rows":missing_price}
 if missing_identity or missing_price:fail.append({"league":league,**coverage[league]})
dev=[x for x in allrows if x["split"]=="DEVELOPMENT"];hold=[x for x in allrows if x["split"]=="HOLDOUT"]
me,mc=metric(hold,"p_early"),metric(hold,"p_close")
bins_dev=binned(dev);bins_hold=binned(hold)
promotion={}
for name,_,_ in BINS:
 a,b=bins_dev[name],bins_hold[name]
 promotion[name]={"eligible":a["n"]>=200 and b["n"]>=200,
  "passes":a["n"]>=200 and b["n"]>=200 and a["roi"]>0 and b["roi_ci95"][0]>0 and b["positive_roi_leagues"]>=5,
  "reason":"Requires n>=200 in both partitions, positive development ROI, holdout ROI CI95 above zero and positive ROI in at least 5 leagues."}
report={
 "schema_version":"radar-historical-b365-ou25-early-close-movement-oos-v1","generated_at":datetime.utcnow().isoformat()+"Z",
 "status":"COMPLETE_SAME_BOOK_EARLY_TO_CLOSE_DIAGNOSTIC",
 "market":"FULL_TIME_OVER_UNDER_2_5","bookmaker":"Bet365",
 "price_semantics":{"early":"Football-Data B365>2.5/B365<2.5; provider early price without a certified timestamp","close":"Football-Data B365C>2.5/B365C<2.5",
  "true_open_certified":False,"same_bookmaker":True,"goldbet":False},
 "anti_hindsight":{"movement_bins_prefixed":["0-1pp","1-2pp","2-3pp",">=3pp"],"development_and_holdout_separate":True,
  "outcomes_evaluation_only":True,"no_missing_price_reconstruction":True},
 "coverage":{"development_rows":len(dev),"holdout_rows":len(hold),"total_rows":len(allrows),"by_league":coverage},
 "holdout_probability_quality":{"early":me,"close":mc,"delta_close_minus_early":{"brier":mc["brier"]-me["brier"],"log_loss":mc["log_loss"]-me["log_loss"]},"paired_bootstrap":paired(hold)},
 "movement_direction_strategy":{"definition":"Choose Over at the early price when de-vigged Over probability rises by close; choose Under when it falls.","development":bins_dev,"holdout":bins_hold,
  "promotion_gate":promotion},
 "source_failures":fail,
 "verdict":"This is a Bet365 same-book early-to-close diagnostic. No result may be relabelled GoldBet TRUE OPEN, and no operational GoldBet rule is promoted."
}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"status":report["status"],"coverage":report["coverage"],"quality":report["holdout_probability_quality"],"promotion":promotion},indent=2))
