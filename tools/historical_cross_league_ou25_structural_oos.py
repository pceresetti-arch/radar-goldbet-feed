#!/usr/bin/env python3
import csv,json,math,random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"feed/historical/markets/cross-league-ou25-structural-oos-v1.json"
FILES=[
 ("Sweden","feed/historical/sweden/allsvenskan-2022-2025-regular.csv"),
 ("Norway","feed/historical/norway/eliteserien-2022-2025-regular.csv"),
 ("Denmark","feed/historical/denmark/superliga-2022-2026-regular.csv"),
 ("Netherlands","feed/historical/netherlands/eredivisie-2022-2026-regular.csv"),
 ("Portugal","feed/historical/portugal/primeira-liga-2022-2026-regular.csv"),
 ("Germany2","feed/historical/germany2/2-bundesliga-2022-2026-regular.csv"),
 ("Germany1","feed/historical/germany1/bundesliga-2022-2026-regular.csv"),
 ("Spain1","feed/historical/spain1/laliga-2022-2026-regular.csv"),
 ("England1","feed/historical/england1/premier-league-2022-2026-regular.csv"),
 ("Scotland1","feed/historical/scotland1/scottish-premiership-2022-2026-regular.csv"),
 ("Austria1","feed/historical/austria1/austrian-bundesliga-2022-2026-regular.csv")]
PRIOR_MATCHES=12.0
PRIOR_HOME_GOALS=1.45
PRIOR_AWAY_GOALS=1.15
def read(p):
 with open(ROOT/p,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def ll(p,y):
 p=min(max(p,1e-12),1-1e-12);return -(y*math.log(p)+(1-y)*math.log(1-p))
def metric(a,key):
 n=len(a);return {"n":n,"brier":sum((x[key]-x["y"])**2 for x in a)/n,"log_loss":sum(ll(x[key],x["y"]) for x in a)/n,
 "accuracy":sum((x[key]>=.5)==bool(x["y"]) for x in a)/n}
def q(a,z):
 a=sorted(a);p=(len(a)-1)*z;i=int(p);j=min(i+1,len(a)-1);w=p-i;return a[i]*(1-w)+a[j]*w
def boot(a,n=10000):
 rng=random.Random(20902);N=len(a);leagues=sorted({x["league"] for x in a});by={g:[x for x in a if x["league"]==g] for g in leagues}
 fb=[];fl=[];hb=[];hl=[]
 for _ in range(n):
  s=[a[rng.randrange(N)] for __ in range(N)]
  fb.append(sum((x["p_model"]-x["y"])**2-(x["p_base"]-x["y"])**2 for x in s)/N)
  fl.append(sum(ll(x["p_model"],x["y"])-ll(x["p_base"],x["y"]) for x in s)/N)
  vb=[];vl=[]
  for __ in leagues:
   g=leagues[rng.randrange(len(leagues))];v=by[g];ss=[v[rng.randrange(len(v))] for ___ in v]
   vb.append(sum((x["p_model"]-x["y"])**2-(x["p_base"]-x["y"])**2 for x in ss)/len(ss))
   vl.append(sum(ll(x["p_model"],x["y"])-ll(x["p_base"],x["y"]) for x in ss)/len(ss))
  hb.append(sum(vb)/len(vb));hl.append(sum(vl)/len(vl))
 return {"paired_fixture":{"draws":n,"brier_delta_model_minus_baseline_ci95":[q(fb,.025),q(fb,.975)],"log_loss_delta_model_minus_baseline_ci95":[q(fl,.025),q(fl,.975)]},
 "hierarchical_league":{"draws":n,"brier_delta_model_minus_baseline_ci95":[q(hb,.025),q(hb,.975)],"log_loss_delta_model_minus_baseline_ci95":[q(hl,.025),q(hl,.975)]}}
all_hold=[];reports={}
for league,path in FILES:
 rows=read(path);rows.sort(key=lambda r:(r["source_date"],r.get("source_time",""),r["fixture_key"]))
 dev=[r for r in rows if r["split"]=="DEVELOPMENT"]
 base=sum(int(r["home_goals"])+int(r["away_goals"])>2 for r in dev)/len(dev)
 total_n=0;hg=ag=0.0
 th=defaultdict(lambda:[0,0.0,0.0]);ta=defaultdict(lambda:[0,0.0,0.0])
 hold=[]
 dates=sorted({r["source_date"] for r in rows})
 grouped={d:[r for r in rows if r["source_date"]==d] for d in dates}
 for d in dates:
  preds=[]
  mh=(hg+PRIOR_MATCHES*PRIOR_HOME_GOALS)/(total_n+PRIOR_MATCHES)
  ma=(ag+PRIOR_MATCHES*PRIOR_AWAY_GOALS)/(total_n+PRIOR_MATCHES)
  for r in grouped[d]:
   h,a=r["home_team"],r["away_team"];hn,hgf,hga=th[h];an,agf,aga=ta[a]
   hat=((hgf+PRIOR_MATCHES*mh)/(hn+PRIOR_MATCHES))/mh
   hdef=((hga+PRIOR_MATCHES*ma)/(hn+PRIOR_MATCHES))/ma
   aat=((agf+PRIOR_MATCHES*ma)/(an+PRIOR_MATCHES))/ma
   adef=((aga+PRIOR_MATCHES*mh)/(an+PRIOR_MATCHES))/mh
   lh=min(max(mh*hat*adef,.15),4.0);la=min(max(ma*aat*hdef,.15),4.0)
   lt=lh+la;p=1-math.exp(-lt)*(1+lt+lt*lt/2);y=int(int(r["home_goals"])+int(r["away_goals"])>2)
   preds.append((r,h,a,lh,la,p,y))
   if r["split"]=="HOLDOUT":
    hold.append({"league":league,"fixture_key":r["fixture_key"],"p_base":base,"p_model":p,"y":y,"lambda_home":lh,"lambda_away":la})
  for r,h,a,lh,la,p,y in preds:
   gh,ga=int(r["home_goals"]),int(r["away_goals"]);total_n+=1;hg+=gh;ag+=ga
   th[h][0]+=1;th[h][1]+=gh;th[h][2]+=ga;ta[a][0]+=1;ta[a][1]+=ga;ta[a][2]+=gh
 all_hold+=hold;mb=metric(hold,"p_base");mm=metric(hold,"p_model")
 reports[league]={"development_rows":len(dev),"holdout_rows":len(hold),"development_over25_rate_frozen":base,
 "baseline":mb,"structural_poisson":mm,"delta_model_minus_baseline":{"brier":mm["brier"]-mb["brier"],"log_loss":mm["log_loss"]-mb["log_loss"]}}
mb=metric(all_hold,"p_base");mm=metric(all_hold,"p_model")
report={"schema_version":"radar-historical-cross-league-ou25-structural-oos-v1","generated_at":datetime.utcnow().isoformat()+"Z",
 "status":"COMPLETE_FROZEN_STRUCTURAL_OOS","market":"OVER_2_5_GOALS",
 "design":{"features":"Strictly prior-date home/away goals for and against with league and team shrinkage",
 "prior_matches":PRIOR_MATCHES,"prior_home_goals":PRIOR_HOME_GOALS,"prior_away_goals":PRIOR_AWAY_GOALS,
 "date_batch_update":True,"holdout_parameter_tuning":False,"outcomes_joined_after_probability_freeze":True,
 "price_data_available":False,"roi_clv_mms_allowed":False},
 "coverage":{"leagues":len(FILES),"holdout_rows":len(all_hold),"missing_rows":0},
 "pooled":{"baseline":mb,"structural_poisson":mm,"delta_model_minus_baseline":{"brier":mm["brier"]-mb["brier"],"log_loss":mm["log_loss"]-mb["log_loss"]}},
 "uncertainty":boot(all_hold),"by_league":reports,
 "verdict":"Structural O/U 2.5 probability test only. This is not a same-book price-movement test; no operational fair-price, value, CLV, ROI or MMS conclusion is permitted."}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"coverage":report["coverage"],"pooled":report["pooled"],"uncertainty":report["uncertainty"]},indent=2))
