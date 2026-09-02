#!/usr/bin/env python3
import csv,json,math,random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"feed/historical/markets/b365-ou25-structural-early-blend-oos-v1.json"
CFG=[
 ("Netherlands","feed/historical/netherlands/eredivisie-2022-2026-regular.csv","feed/historical/netherlands","N1"),
 ("Portugal","feed/historical/portugal/primeira-liga-2022-2026-regular.csv","feed/historical/portugal","P1"),
 ("Germany2","feed/historical/germany2/2-bundesliga-2022-2026-regular.csv","feed/historical/germany2","D2"),
 ("Germany1","feed/historical/germany1/bundesliga-2022-2026-regular.csv","feed/historical/germany1","D1"),
 ("Spain1","feed/historical/spain1/laliga-2022-2026-regular.csv","feed/historical/spain1","SP1"),
 ("England1","feed/historical/england1/premier-league-2022-2026-regular.csv","feed/historical/england1","E0"),
 ("Scotland1","feed/historical/scotland1/scottish-premiership-2022-2026-regular.csv","feed/historical/scotland1","SC0")]
SEASONS=["2022-2023","2023-2024","2024-2025","2025-2026"]
PRIOR_MATCHES=12.0;PRIOR_HOME_GOALS=1.45;PRIOR_AWAY_GOALS=1.15
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
def ll(p,y):
 p=min(max(p,1e-12),1-1e-12);return -(y*math.log(p)+(1-y)*math.log(1-p))
def metric(a,key):
 n=len(a);return {"n":n,"brier":sum((x[key]-x["y"])**2 for x in a)/n,
 "log_loss":sum(ll(x[key],x["y"]) for x in a)/n,
 "accuracy":sum((x[key]>=.5)==bool(x["y"]) for x in a)/n}
def q(a,z):
 a=sorted(a);p=(len(a)-1)*z;i=int(p);j=min(i+1,len(a)-1);w=p-i;return a[i]*(1-w)+a[j]*w
def boot(a,n=10000):
 rng=random.Random(209021);N=len(a);leagues=sorted({x["league"] for x in a});by={g:[x for x in a if x["league"]==g] for g in leagues}
 fb=[];fl=[];hb=[];hl=[]
 for _ in range(n):
  s=[a[rng.randrange(N)] for __ in range(N)]
  fb.append(sum((x["p_blend"]-x["y"])**2-(x["p_early"]-x["y"])**2 for x in s)/N)
  fl.append(sum(ll(x["p_blend"],x["y"])-ll(x["p_early"],x["y"]) for x in s)/N)
  vb=[];vl=[]
  for __ in leagues:
   g=leagues[rng.randrange(len(leagues))];v=by[g];ss=[v[rng.randrange(len(v))] for ___ in v]
   vb.append(sum((x["p_blend"]-x["y"])**2-(x["p_early"]-x["y"])**2 for x in ss)/len(ss))
   vl.append(sum(ll(x["p_blend"],x["y"])-ll(x["p_early"],x["y"]) for x in ss)/len(ss))
  hb.append(sum(vb)/len(vb));hl.append(sum(vl)/len(vl))
 return {"paired_fixture":{"draws":n,"brier_delta_blend_minus_early_ci95":[q(fb,.025),q(fb,.975)],"log_loss_delta_blend_minus_early_ci95":[q(fl,.025),q(fl,.975)]},
 "hierarchical_league":{"draws":n,"brier_delta_blend_minus_early_ci95":[q(hb,.025),q(hb,.975)],"log_loss_delta_blend_minus_early_ci95":[q(hl,.025),q(hl,.975)]}}
items=[];coverage={}
for league,norm,folder,code in CFG:
 rows=read(norm);rows.sort(key=lambda r:(r["source_date"],r.get("source_time",""),r["fixture_key"]))
 raw={}
 for season in SEASONS:
  for r in read(f"{folder}/football-data-{code}-{season}.csv"):
   try:k=(date(r.get("Date")),r.get("HomeTeam","").strip(),r.get("AwayTeam","").strip())
   except ValueError:continue
   raw[k]=r
 total_n=0;hg=ag=0.0;th=defaultdict(lambda:[0,0.0,0.0]);ta=defaultdict(lambda:[0,0.0,0.0])
 joined=[];missing_identity=missing_price=0
 grouped={d:[r for r in rows if r["source_date"]==d] for d in sorted({r["source_date"] for r in rows})}
 for d,batch in grouped.items():
  preds=[];mh=(hg+PRIOR_MATCHES*PRIOR_HOME_GOALS)/(total_n+PRIOR_MATCHES);ma=(ag+PRIOR_MATCHES*PRIOR_AWAY_GOALS)/(total_n+PRIOR_MATCHES)
  for r in batch:
   h,a=r["home_team"],r["away_team"];hn,hgf,hga=th[h];an,agf,aga=ta[a]
   hat=((hgf+PRIOR_MATCHES*mh)/(hn+PRIOR_MATCHES))/mh;hdef=((hga+PRIOR_MATCHES*ma)/(hn+PRIOR_MATCHES))/ma
   aat=((agf+PRIOR_MATCHES*ma)/(an+PRIOR_MATCHES))/ma;adef=((aga+PRIOR_MATCHES*mh)/(an+PRIOR_MATCHES))/mh
   lh=min(max(mh*hat*adef,.15),4.0);la=min(max(ma*aat*hdef,.15),4.0);lt=lh+la
   ps=1-math.exp(-lt)*(1+lt+lt*lt/2)
   k=(r["source_date"],h.strip(),a.strip());rr=raw.get(k)
   if rr is None:missing_identity+=1
   else:
    qo,qu=num(rr.get("B365>2.5")),num(rr.get("B365<2.5"))
    if qo is None or qu is None:missing_price+=1
    else:
     pc=(1/qo)/((1/qo)+(1/qu));y=int(int(r["home_goals"])+int(r["away_goals"])>=3)
     joined.append({"league":league,"split":r["split"],"fixture_key":r["fixture_key"],"p_struct":ps,"p_early":pc,"y":y})
   preds.append((r,h,a))
  for r,h,a in preds:
   gh,ga=int(r["home_goals"]),int(r["away_goals"]);total_n+=1;hg+=gh;ag+=ga
   th[h][0]+=1;th[h][1]+=gh;th[h][2]+=ga;ta[a][0]+=1;ta[a][1]+=ga;ta[a][2]+=gh
 items+=joined;coverage[league]={"accepted_rows":len(rows),"joined_rows":len(joined),"missing_identity_rows":missing_identity,"missing_price_rows":missing_price}
dev=[x for x in items if x["split"]=="DEVELOPMENT"];hold=[x for x in items if x["split"]=="HOLDOUT"]
grid=[]
for i in range(21):
 w=i/20
 for x in dev:x["p_candidate"]=w*x["p_early"]+(1-w)*x["p_struct"]
 m=metric(dev,"p_candidate");grid.append({"early_weight":w,**m})
chosen=min(grid,key=lambda x:(x["log_loss"],x["brier"],-x["early_weight"]))
w=chosen["early_weight"]
for x in items:x["p_blend"]=w*x["p_early"]+(1-w)*x["p_struct"]
mc=metric(hold,"p_early");ms=metric(hold,"p_struct");mb=metric(hold,"p_blend")
by={}
for g in sorted({x["league"] for x in hold}):
 v=[x for x in hold if x["league"]==g];a=metric(v,"p_early");b=metric(v,"p_blend")
 by[g]={"n":len(v),"close":a,"blend":b,"delta_blend_minus_early":{"brier":b["brier"]-a["brier"],"log_loss":b["log_loss"]-a["log_loss"]}}
report={"schema_version":"radar-historical-b365-ou25-structural-early-blend-oos-v1","generated_at":datetime.utcnow().isoformat()+"Z",
 "status":"COMPLETE_DEVELOPMENT_SELECTED_FROZEN_OOS","market":"FULL_TIME_OVER_UNDER_2_5",
 "design":{"development_rows":len(dev),"holdout_rows":len(hold),"blend_formula":"w*b365_provider_early + (1-w)*structural_poisson",
 "weight_grid":[i/20 for i in range(21)],"selection_metric":"development log-loss; Brier then larger close weight as deterministic tie breakers",
 "selected_early_weight":w,"selected_structural_weight":1-w,"holdout_used_for_weight_selection":False,
 "structural_features":"Strictly prior-date home/away goals for and against with fixed shrinkage and date-batch updates",
 "market_probability":"De-vigged Bet365 provider-early O/U 2.5 pair; timestamp uncertified, not TRUE OPEN or GoldBet","operational_rule_allowed":False},
 "coverage":{"leagues":len(CFG),"development_rows":len(dev),"holdout_rows":len(hold),"by_league":coverage},
 "development_selection":{"selected":chosen,"grid":grid},
 "holdout":{"b365_provider_early":mc,"structural_poisson":ms,"frozen_blend":mb,
 "delta_blend_minus_early":{"brier":mb["brier"]-mc["brier"],"log_loss":mb["log_loss"]-mc["log_loss"]}},
 "uncertainty":boot(hold),"by_league":by,
 "verdict":"A structural increment may be promoted only if development selection gives it positive weight and frozen holdout improves robustly. Bet365 provider-early is not certified TRUE OPEN or GoldBet."}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"coverage":report["coverage"],"development_selection":report["development_selection"]["selected"],"holdout":report["holdout"],"uncertainty":report["uncertainty"]},indent=2))
