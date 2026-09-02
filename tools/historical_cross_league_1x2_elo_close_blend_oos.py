#!/usr/bin/env python3
import csv,json,math,random
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
ROOT=Path(".");OUT=Path("feed/historical/markets/cross-league-1x2-elo-close-blend-oos-v1.json")
OUTCOMES=["H","D","A"]
REPORTS=[
"feed/historical/sweden/structural-oos-v1.json","feed/historical/norway/structural-oos-v1.json",
"feed/historical/denmark/structural-oos-v1.json","feed/historical/netherlands/structural-oos-v1.json",
"feed/historical/portugal/structural-oos-v1.json","feed/historical/germany2/structural-oos-v1.json",
"feed/historical/germany1/structural-oos-v1.json","feed/historical/spain1/structural-oos-v1.json",
"feed/historical/england1/structural-oos-v1.json","feed/historical/scotland1/structural-oos-v1.json",
"feed/historical/austria1/structural-oos-v1.json"]
NAMES={"sweden":"Allsvenskan","norway":"Eliteserien","denmark":"Superliga","netherlands":"Eredivisie",
"portugal":"Primeira Liga","germany2":"2. Bundesliga","germany1":"Bundesliga","spain1":"LaLiga",
"england1":"Premier League","scotland1":"Scottish Premiership","austria1":"Austrian Bundesliga"}
L2=.01;LR=.08;IT=1800
def prep(train,test):
 vals=np.array([float(r["elo_diff"]) for r in train]);mean=float(vals.mean());scale=float(vals.std()) or 1.
 xtr=np.column_stack([np.ones(len(train)),(vals-mean)/scale]);xte=np.column_stack([np.ones(len(test)),np.array([(float(r["elo_diff"])-mean)/scale for r in test])])
 return xtr,np.array([OUTCOMES.index(r["result"]) for r in train]),xte,mean,scale
def train(x,y):
 w=np.zeros((3,x.shape[1]));oh=np.eye(3)[y]
 for _ in range(IT):
  z=x@w.T;z-=z.max(axis=1,keepdims=True);p=np.exp(z);p/=p.sum(axis=1,keepdims=True)
  g=(p-oh).T@x/len(x);pen=L2*w;pen[:,0]=0;w-=LR*(g+pen)
 return w
def predict(x,w):
 z=x@w.T;z-=z.max(axis=1,keepdims=True);p=np.exp(z);return p/p.sum(axis=1,keepdims=True)
def softmax(z):
 m=max(z);e=[math.exp(v-m) for v in z];t=sum(e);return [v/t for v in e]
def market(r):
 inv=[1/float(r["avg_close_home"]),1/float(r["avg_close_draw"]),1/float(r["avg_close_away"])];t=sum(inv);return [v/t for v in inv]
def loss(p,y):return sum((p[k]-(1 if k==y else 0))**2 for k in range(3)),-math.log(max(p[y],1e-15))
def metric(rows,key):
 ls=[loss(r[key],r["y"]) for r in rows];return {"n":len(rows),"brier":sum(v[0] for v in ls)/len(ls),"log_loss":sum(v[1] for v in ls)/len(ls),
 "accuracy":sum(max(range(3),key=lambda k:r[key][k])==r["y"] for r in rows)/len(rows)}
def q(a,z):
 a=sorted(a);p=(len(a)-1)*z;i=int(p);j=min(i+1,len(a)-1);u=p-i;return a[i]*(1-u)+a[j]*u
def boot(rows,n=10000):
 rng=random.Random(120902);N=len(rows);leagues=sorted({r["league"] for r in rows});by={g:[r for r in rows if r["league"]==g] for g in leagues};fb=[];fl=[];hb=[];hl=[]
 for _ in range(n):
  s=[rows[rng.randrange(N)] for __ in range(N)];d=[(loss(r["blend"],r["y"])[0]-loss(r["close"],r["y"])[0],loss(r["blend"],r["y"])[1]-loss(r["close"],r["y"])[1]) for r in s]
  fb.append(sum(v[0] for v in d)/N);fl.append(sum(v[1] for v in d)/N);vb=[];vl=[]
  for __ in leagues:
   g=leagues[rng.randrange(len(leagues))];v=by[g];ss=[v[rng.randrange(len(v))] for ___ in v];dd=[(loss(r["blend"],r["y"])[0]-loss(r["close"],r["y"])[0],loss(r["blend"],r["y"])[1]-loss(r["close"],r["y"])[1]) for r in ss]
   vb.append(sum(x[0] for x in dd)/len(dd));vl.append(sum(x[1] for x in dd)/len(dd))
  hb.append(sum(vb)/len(vb));hl.append(sum(vl)/len(vl))
 return {"paired_fixture":{"draws":n,"brier_delta_blend_minus_close_ci95":[q(fb,.025),q(fb,.975)],"log_loss_delta_blend_minus_close_ci95":[q(fl,.025),q(fl,.975)]},
 "hierarchical_league":{"draws":n,"brier_delta_blend_minus_close_ci95":[q(hb,.025),q(hb,.975)],"log_loss_delta_blend_minus_close_ci95":[q(hl,.025),q(hl,.975)]}}
dev_oof=[];hold=[];folds=[]
for rp in REPORTS:
 rep=json.loads(Path(rp).read_text());key=Path(rp).parts[-2];league=NAMES[key]
 with Path(rep["feature_dataset"]).open(encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
 dev=[r for r in rows if r["split"]=="DEVELOPMENT"];seasons=sorted({r["season"] for r in dev})
 for pos in (1,2):
  tr=[r for r in dev if r["season"] in seasons[:pos]];te=[r for r in dev if r["season"]==seasons[pos]]
  x,y,xt,mean,scale=prep(tr,te);w=train(x,y);pp=predict(xt,w)
  for r,p in zip(te,pp):dev_oof.append({"league":league,"fold":seasons[pos],"y":OUTCOMES.index(r["result"]),"elo":[float(v) for v in p],"close":market(r)})
  folds.append({"league":league,"train_seasons":seasons[:pos],"validation_season":seasons[pos],"train_n":len(tr),"validation_n":len(te)})
 model=rep["ablation_same_holdout"]["ELO_ONLY"];fn=model["features"];means=model["standardization"]["means"];scales=model["standardization"]["scales"];weights=[model["weights_by_outcome"][o] for o in OUTCOMES]
 hrs=[r for r in rows if r["split"]=="HOLDOUT"]
 for r in hrs:
  x=[1.]+[((float(r[n])-means[n])/scales[n]) for n in fn];pe=softmax([sum(a*b for a,b in zip(w,x)) for w in weights])
  hold.append({"league":league,"y":OUTCOMES.index(r["result"]),"elo":pe,"close":market(r)})
grid=[]
for i in range(21):
 cw=i/20
 for r in dev_oof:r["candidate"]=[cw*r["close"][k]+(1-cw)*r["elo"][k] for k in range(3)]
 grid.append({"close_weight":cw,**metric(dev_oof,"candidate")})
chosen=min(grid,key=lambda x:(x["log_loss"],x["brier"],-x["close_weight"]));cw=chosen["close_weight"]
for r in hold:r["blend"]=[cw*r["close"][k]+(1-cw)*r["elo"][k] for k in range(3)]
mc=metric(hold,"close");me=metric(hold,"elo");mb=metric(hold,"blend");by={}
for g in sorted({r["league"] for r in hold}):
 v=[r for r in hold if r["league"]==g];a=metric(v,"close");b=metric(v,"blend");by[g]={"n":len(v),"close":a,"blend":b,"delta_blend_minus_close":{"brier":b["brier"]-a["brier"],"log_loss":b["log_loss"]-a["log_loss"]}}
report={"schema_version":"radar-historical-cross-league-1x2-elo-close-blend-oos-v1","generated_at":datetime.now(timezone.utc).isoformat(),"status":"COMPLETE_ROLLING_DEVELOPMENT_SELECTED_FROZEN_OOS","market":"FULL_TIME_1X2",
"design":{"development_validation_rows":len(dev_oof),"rolling_origin_folds":len(folds),"holdout_rows":len(hold),"blend_formula":"w*external_average_close + (1-w)*ELO_ONLY",
"weight_grid":[i/20 for i in range(21)],"selection_metric":"rolling-development log-loss; Brier then larger close weight tie breakers","selected_close_weight":cw,"selected_elo_weight":1-cw,
"final_holdout_used_for_weight_selection":False,"external_price_semantics":"de-vigged external average close; not GoldBet","operational_rule_allowed":False},
"development_selection":{"selected":chosen,"grid":grid,"folds":folds},"holdout":{"external_average_close":mc,"elo_only":me,"frozen_blend":mb,
"delta_blend_minus_close":{"brier":mb["brier"]-mc["brier"],"log_loss":mb["log_loss"]-mc["log_loss"]}},
"uncertainty":boot(hold),"by_league":by,
"verdict":"Promote an Elo increment only if rolling-development selection gives it positive weight and the frozen holdout improves robustly. External average close remains a non-GoldBet benchmark."}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({"design":report["design"],"development_selected":chosen,"holdout":report["holdout"],"uncertainty":report["uncertainty"]},indent=2))
