#!/usr/bin/env python3
"""Calibration audit for GoldBet TRUE OPEN using exact-ID outcomes.

This is a prospective 2026 diagnostic, not a multi-season OOS model test.
Observed-current prices remain labelled as such and are never called CLOSE.
"""
from __future__ import annotations
import hashlib,json,math,random
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"feed/diretta-goldbet-true-open-index.json"
OUTCOMES=ROOT/"feed/historical/open-close/goldbet-exact-outcomes-v1.json"
OUT=ROOT/"feed/historical/open-close/goldbet-true-open-calibration-v1.json"

def logloss(p,y):
    p=min(max(p,1e-12),1-1e-12)
    return -(y*math.log(p)+(1-y)*math.log(1-p))

def settle(period,market,sel,line,o):
    if period=="first_half":
        p=next((x for x in o["periods"] if x["period"]=="1st Half"),None)
        if not p:return None
        hg,ag=p["home"],p["away"]
    elif period=="full_time":
        hg,ag=o["home_goals"],o["away_goals"]
    else:return None
    if market=="HOME_DRAW_AWAY":
        res="HOME" if hg>ag else "AWAY" if ag>hg else "DRAW"
        return sel==res
    if market=="OVER_UNDER":
        total=hg+ag
        try: line=float(line)
        except (TypeError,ValueError):return None
        if math.isclose(total,line):return None
        return (total>line) if sel=="OVER" else (total<line) if sel=="UNDER" else None
    if market=="BOTH_TEAMS_TO_SCORE":
        yes=hg>0 and ag>0
        if sel in {"YES","GOAL"}:return yes
        if sel in {"NO","NO_GOAL"}:return not yes
    return None

def mean(xs):return sum(xs)/len(xs) if xs else None

def bootstrap_diff(rows,draws=5000):
    # cluster by exact event id; positive means observed-current loss is worse.
    by=defaultdict(list)
    for r in rows:by[r["flashscore_event_id"]].append(r)
    ids=sorted(by)
    if len(ids)<2:return None
    rng=random.Random(20260901)
    vals=[]
    for _ in range(draws):
        sample=[rng.choice(ids) for __ in ids]
        op=[];cur=[]
        for eid in sample:
            for r in by[eid]:
                op.append(r["open_loss"]);cur.append(r["current_loss"])
        vals.append(mean(cur)-mean(op))
    vals.sort()
    return {"observed_current_minus_true_open_mean":mean([r["current_loss"]-r["open_loss"] for r in rows]),
            "cluster_bootstrap_ci95":[vals[int(.025*draws)],vals[int(.975*draws)-1]],
            "draws":draws,"cluster":"flashscore_event_id"}

def main():
    iraw=INDEX.read_bytes();oraw=OUTCOMES.read_bytes()
    idx=json.loads(iraw);ores=json.loads(oraw)
    outcomes={x["flashscore_event_id"]:x for x in ores["outcomes"] if x["status"]=="FINAL_TWO_REGULAR_HALVES_PARSED"}
    groups=defaultdict(list)
    event_meta={}
    for source_key,e in (idx.get("events") or {}).items():
        eid=e.get("flashscore_event_id")
        if eid not in outcomes:continue
        event_meta[eid]=e
        for r in e.get("rows") or []:
            if r.get("true_open") and r.get("diretta_current"):
                groups[(eid,r.get("market"),r.get("period"),str(r.get("line")))].append(r)

    score_rows=[]
    invalid=[]
    for (eid,market,period,line),rows in groups.items():
        sels={r.get("selection"):r for r in rows}
        required={"HOME","DRAW","AWAY"} if market=="HOME_DRAW_AWAY" else {"OVER","UNDER"} if market=="OVER_UNDER" else None
        if market=="BOTH_TEAMS_TO_SCORE":
            if {"YES","NO"}<=set(sels):required={"YES","NO"}
            elif {"GOAL","NO_GOAL"}<=set(sels):required={"GOAL","NO_GOAL"}
        if not required or not required<=set(sels):
            invalid.append({"flashscore_event_id":eid,"market":market,"period":period,"line":line,
                            "reason":"incomplete_or_unsupported_selection_set","selections":sorted(str(x) for x in sels)})
            continue
        open_sum=sum(1/float(sels[s]["true_open"]) for s in required)
        cur_sum=sum(1/float(sels[s]["diretta_current"]) for s in required)
        e=event_meta[eid]
        lead=None
        try:
            start=datetime.fromisoformat((e.get("start_time") or "").replace("Z","+00:00"))
            obs=datetime.fromisoformat((e.get("attempted_at") or e.get("certified_at") or "").replace("Z","+00:00"))
            lead=(start-obs).total_seconds()/60
        except Exception:pass
        for sel in sorted(required):
            r=sels[sel]; y=settle(period,market,sel,None if line=="None" else line,outcomes[eid])
            if y is None:continue
            op=(1/float(r["true_open"]))/open_sum;cp=(1/float(r["diretta_current"]))/cur_sum
            score_rows.append({"flashscore_event_id":eid,"market":market,"period":period,
              "line":None if line=="None" else float(line),"selection":sel,"outcome":int(y),
              "true_open_price":float(r["true_open"]),"observed_current_price":float(r["diretta_current"]),
              "true_open_probability":op,"observed_current_probability":cp,
              "lead_minutes":lead,"open_brier":(op-int(y))**2,"current_brier":(cp-int(y))**2,
              "open_logloss":logloss(op,int(y)),"current_logloss":logloss(cp,int(y))})

    segments=[]
    for key,rs in sorted(defaultdict(list,{}).items()):pass
    buckets=defaultdict(list)
    for r in score_rows:
        buckets[(r["market"],r["period"])].append(r)
    buckets[("ALL","SUPPORTED")]=score_rows
    for (market,period),rs in sorted(buckets.items()):
        events=len({r["flashscore_event_id"] for r in rs})
        segments.append({"market":market,"period":period,"selection_rows":len(rs),"events":events,
          "true_open":{"brier_selection_mean":mean([r["open_brier"] for r in rs]),
                       "log_loss_selection_mean":mean([r["open_logloss"] for r in rs])},
          "observed_current":{"brier_selection_mean":mean([r["current_brier"] for r in rs]),
                       "log_loss_selection_mean":mean([r["current_logloss"] for r in rs])},
          "paired_brier":bootstrap_diff([{**r,"open_loss":r["open_brier"],"current_loss":r["current_brier"]} for r in rs]),
          "paired_logloss":bootstrap_diff([{**r,"open_loss":r["open_logloss"],"current_loss":r["current_logloss"]} for r in rs])})

    lead_bins=[]
    defs=[("T_0_30",0,30),("T_30_120",30,120),("T_120_360",120,360),("T_360_PLUS",360,float("inf"))]
    for name,lo,hi in defs:
        rs=[r for r in score_rows if r["lead_minutes"] is not None and lo<=r["lead_minutes"]<hi]
        lead_bins.append({"bin":name,"selection_rows":len(rs),"events":len({r["flashscore_event_id"] for r in rs}),
          "open_brier":mean([r["open_brier"] for r in rs]),"current_brier":mean([r["current_brier"] for r in rs]),
          "open_logloss":mean([r["open_logloss"] for r in rs]),"current_logloss":mean([r["current_logloss"] for r in rs])})

    report={"schema_version":"radar-goldbet-true-open-calibration-v1","generated_at":datetime.now(timezone.utc).isoformat(),
      "classification":"PROSPECTIVE_2026_EXACT_OUTCOME_DIAGNOSTIC_NOT_MULTI_SEASON_OOS",
      "methodology":{"identity_join":"EXACT_FLASHSCORE_EVENT_ID","same_bookmaker":True,"bookmaker":"GoldBet",
        "outcomes_attached_after_price_feature_freeze":True,"post_kickoff_prices_used":False,
        "observed_current_is_close":False,"roi_calculated":False,
        "metric_note":"Selection-level binary Brier/log-loss; correlated selections are clustered by fixture for paired intervals."},
      "sources":{"index":{"path":str(INDEX.relative_to(ROOT)),"sha256":hashlib.sha256(iraw).hexdigest()},
                 "outcomes":{"path":str(OUTCOMES.relative_to(ROOT)),"sha256":hashlib.sha256(oraw).hexdigest()}},
      "coverage":{"exact_outcome_events":len(outcomes),"complete_price_groups":len({(r["flashscore_event_id"],r["market"],r["period"],str(r["line"])) for r in score_rows}),
                  "scored_selection_rows":len(score_rows),"invalid_groups":len(invalid)},
      "segments":segments,"lead_time_segments":lead_bins,"invalid_groups":invalid,
      "decision":"CALIBRATION_DIAGNOSTIC_ONLY_NO_RULE_OR_THRESHOLD_PROMOTED"}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["coverage"],ensure_ascii=False))

if __name__=="__main__":main()
