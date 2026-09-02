#!/usr/bin/env python3
import csv, json, math, random
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"feed/historical/markets/cross-league-ou25-close-oos-v1.json"
LEAGUES=[
 ("Netherlands","feed/historical/netherlands/eredivisie-2022-2026-regular.csv","feed/historical/netherlands/football-data-N1-2025-2026.csv"),
 ("Portugal","feed/historical/portugal/primeira-liga-2022-2026-regular.csv","feed/historical/portugal/football-data-P1-2025-2026.csv"),
 ("Germany2","feed/historical/germany2/2-bundesliga-2022-2026-regular.csv","feed/historical/germany2/football-data-D2-2025-2026.csv"),
 ("Germany1","feed/historical/germany1/bundesliga-2022-2026-regular.csv","feed/historical/germany1/football-data-D1-2025-2026.csv"),
 ("Spain1","feed/historical/spain1/laliga-2022-2026-regular.csv","feed/historical/spain1/football-data-SP1-2025-2026.csv"),
 ("England1","feed/historical/england1/premier-league-2022-2026-regular.csv","feed/historical/england1/football-data-E0-2025-2026.csv"),
 ("Scotland1","feed/historical/scotland1/scottish-premiership-2022-2026-regular.csv","feed/historical/scotland1/football-data-SC0-2025-2026.csv"),
]

def rows(path):
    with open(ROOT/path,encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def iso_date(s):
    s=(s or "").strip()
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
        try:return datetime.strptime(s,fmt).date().isoformat()
        except ValueError:pass
    raise ValueError("unparsed date "+s)

def fnum(x):
    try:
        v=float(x)
        return v if math.isfinite(v) and v>1 else None
    except:return None

def brier(p,y): return (p-y)**2
def logloss(p,y):
    p=min(max(p,1e-12),1-1e-12)
    return -(y*math.log(p)+(1-y)*math.log(1-p))

def metrics(items,key):
    n=len(items)
    return {"n":n,"brier":sum(brier(x[key],x["y"]) for x in items)/n,
            "log_loss":sum(logloss(x[key],x["y"]) for x in items)/n,
            "accuracy":sum((x[key]>=.5)==bool(x["y"]) for x in items)/n}

def quantile(a,q):
    a=sorted(a); pos=(len(a)-1)*q; lo=int(pos); hi=min(lo+1,len(a)-1); w=pos-lo
    return a[lo]*(1-w)+a[hi]*w

def bootstrap(items,n=10000,seed=20260902):
    rng=random.Random(seed); N=len(items); leagues=sorted({x["league"] for x in items})
    fixture_b=[]; fixture_l=[]; league_b=[]; league_l=[]
    by={g:[x for x in items if x["league"]==g] for g in leagues}
    for _ in range(n):
        sample=[items[rng.randrange(N)] for __ in range(N)]
        fixture_b.append(sum(brier(x["p_close"],x["y"])-brier(x["p_base"],x["y"]) for x in sample)/N)
        fixture_l.append(sum(logloss(x["p_close"],x["y"])-logloss(x["p_base"],x["y"]) for x in sample)/N)
        chosen=[leagues[rng.randrange(len(leagues))] for __ in leagues]
        vals_b=[]; vals_l=[]
        for g in chosen:
            s=by[g]; ss=[s[rng.randrange(len(s))] for __ in s]
            vals_b.append(sum(brier(x["p_close"],x["y"])-brier(x["p_base"],x["y"]) for x in ss)/len(ss))
            vals_l.append(sum(logloss(x["p_close"],x["y"])-logloss(x["p_base"],x["y"]) for x in ss)/len(ss))
        league_b.append(sum(vals_b)/len(vals_b)); league_l.append(sum(vals_l)/len(vals_l))
    return {
      "paired_fixture_bootstrap":{"draws":n,"brier_delta_close_minus_baseline_ci95":[quantile(fixture_b,.025),quantile(fixture_b,.975)],"log_loss_delta_close_minus_baseline_ci95":[quantile(fixture_l,.025),quantile(fixture_l,.975)]},
      "hierarchical_league_bootstrap":{"draws":n,"brier_delta_close_minus_baseline_ci95":[quantile(league_b,.025),quantile(league_b,.975)],"log_loss_delta_close_minus_baseline_ci95":[quantile(league_l,.025),quantile(league_l,.975)]}
    }

all_items=[]; league_reports={}; failures=[]
for league,norm_path,raw_path in LEAGUES:
    norm=rows(norm_path)
    dev=[r for r in norm if r["split"]=="DEVELOPMENT"]
    hold=[r for r in norm if r["split"]=="HOLDOUT"]
    p_base=sum((int(r["home_goals"])+int(r["away_goals"]))>=3 for r in dev)/len(dev)
    raw=rows(raw_path)
    idx={}
    dup=0
    for r in raw:
        try:k=(iso_date(r.get("Date")),r.get("HomeTeam","").strip(),r.get("AwayTeam","").strip())
        except ValueError:continue
        if k in idx:dup+=1
        idx[k]=r
    items=[]; missing_identity=[]; missing_price=[]
    for r in hold:
        k=(r["source_date"],r["home_team"].strip(),r["away_team"].strip())
        q=idx.get(k)
        if not q:
            missing_identity.append("|".join(k)); continue
        over=fnum(q.get("AvgC>2.5")); under=fnum(q.get("AvgC<2.5"))
        if over is None or under is None:
            missing_price.append("|".join(k)); continue
        io,iu=1/over,1/under
        p=io/(io+iu)
        y=int(int(r["home_goals"])+int(r["away_goals"])>=3)
        items.append({"league":league,"fixture_key":r["fixture_key"],"y":y,"p_base":p_base,"p_close":p,
                      "close_over":over,"close_under":under})
    all_items.extend(items)
    mb=metrics(items,"p_base") if items else None
    mc=metrics(items,"p_close") if items else None
    league_reports[league]={
      "development_rows":len(dev),"holdout_rows":len(hold),"joined_scored_rows":len(items),
      "development_over_rate_frozen":p_base,"duplicate_raw_keys":dup,
      "missing_identity_rows":len(missing_identity),"missing_close_pair_rows":len(missing_price),
      "baseline":mb,"external_average_close":mc,
      "delta_close_minus_baseline":{"brier":mc["brier"]-mb["brier"],"log_loss":mc["log_loss"]-mb["log_loss"]} if items else None
    }
    if missing_identity or missing_price or dup:
        failures.append({"league":league,"duplicate_raw_keys":dup,"missing_identity_rows":missing_identity[:20],"missing_close_pair_rows":missing_price[:20]})

pooled_base=metrics(all_items,"p_base")
pooled_close=metrics(all_items,"p_close")
boot=bootstrap(all_items)
report={
 "schema_version":"radar-historical-cross-league-ou25-close-oos-v1",
 "generated_at":datetime.utcnow().isoformat()+"Z",
 "status":"COMPLETE_EXTERNAL_CLOSE_BENCHMARK_ONLY",
 "market":"FULL_TIME_OVER_UNDER_2_5",
 "design":{
   "leagues":len(LEAGUES),
   "development_probability":"Per-league Over 2.5 rate frozen from the three development seasons only.",
   "holdout":"Latest season already frozen by each accepted structural block.",
   "market_probability":"De-vigged AvgC>2.5 / AvgC<2.5 from the external Football-Data average closing market.",
   "outcome_boundary":"Final goals used only for evaluation after probability construction.",
   "same_bookmaker_primary_signal":False,
   "goldbet_status":"NOT_GOLDBET",
   "roi_clv_mms_allowed":False
 },
 "coverage":{"potential_holdout_rows":sum(x["holdout_rows"] for x in league_reports.values()),
             "scored_rows":len(all_items),"unscored_rows":sum(x["holdout_rows"]-x["joined_scored_rows"] for x in league_reports.values())},
 "pooled":{
   "development_rate_baseline":pooled_base,
   "external_average_close":pooled_close,
   "delta_close_minus_baseline":{"brier":pooled_close["brier"]-pooled_base["brier"],"log_loss":pooled_close["log_loss"]-pooled_base["log_loss"]}
 },
 "uncertainty":boot,
 "by_league":league_reports,
 "source_failures":failures,
 "verdict":"External average closing O/U 2.5 probabilities are a benchmark only. Promote no GoldBet rule, threshold, MMS, CLV or ROI inference.",
 "excluded_leagues":{
   "Sweden":"Persisted consolidated source has no O/U price columns.",
   "Norway":"Persisted consolidated source has no O/U price columns.",
   "Denmark":"Persisted consolidated source has no O/U price columns.",
   "Austria":"Persisted consolidated source has no O/U price columns."
 }
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"status":report["status"],"coverage":report["coverage"],"pooled":report["pooled"],"uncertainty":report["uncertainty"]},indent=2))
