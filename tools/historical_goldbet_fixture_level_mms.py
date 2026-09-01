#!/usr/bin/env python3
"""Fixture-level GoldBet movement diagnostic with exact outcomes.

Pre-specified independent-ish units:
- one maximum probability-shortening selection per event for FT 1X2;
- one for FT O/U 2.5 only;
- one for FT BTTS.
Signals are frozen before exact-ID outcomes are attached. Observed-current is
an executable historical snapshot, but not certified CLOSE.
"""
from __future__ import annotations
import hashlib,json,math,random
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"feed/diretta-goldbet-true-open-index.json"
OUTCOMES=ROOT/"feed/historical/open-close/goldbet-exact-outcomes-v1.json"
OUT=ROOT/"feed/historical/open-close/goldbet-fixture-level-mms-v1.json"

def settle(market,sel,line,o):
    hg,ag=o["home_goals"],o["away_goals"]
    if market=="HOME_DRAW_AWAY":
        result="HOME" if hg>ag else "AWAY" if ag>hg else "DRAW"
        return sel==result
    if market=="OVER_UNDER":
        total=hg+ag
        if math.isclose(total,float(line)):return None
        return total>float(line) if sel=="OVER" else total<float(line) if sel=="UNDER" else None
    if market=="BOTH_TEAMS_TO_SCORE":
        yes=hg>0 and ag>0
        if sel in {"YES","GOAL"}:return yes
        if sel in {"NO","NO_GOAL"}:return not yes
    return None

def ci_roi(profits,draws=10000):
    if not profits:return None
    rng=random.Random(20260901+len(profits))
    vals=[]
    n=len(profits)
    for _ in range(draws):
        vals.append(sum(profits[rng.randrange(n)] for __ in range(n))/n)
    vals.sort()
    return [vals[int(.025*draws)],vals[int(.975*draws)-1]]

def max_drawdown(profits):
    equity=peak=0.0;dd=0.0
    for p in profits:
        equity+=p;peak=max(peak,equity);dd=max(dd,peak-equity)
    return dd

def lead_bin(x):
    if x is None:return "UNKNOWN"
    if x<30:return "T_0_30"
    if x<120:return "T_30_120"
    if x<360:return "T_120_360"
    return "T_360_PLUS"

def main():
    iraw=INDEX.read_bytes();oraw=OUTCOMES.read_bytes()
    idx=json.loads(iraw);ores=json.loads(oraw)
    outs={x["flashscore_event_id"]:x for x in ores["outcomes"] if x["status"]=="FINAL_TWO_REGULAR_HALVES_PARSED"}
    candidates=[]
    for source_key,e in sorted((idx.get("events") or {}).items()):
        eid=e.get("flashscore_event_id")
        if eid not in outs:continue
        groups=defaultdict(list)
        for r in e.get("rows") or []:
            if r.get("period")!="full_time" or not r.get("true_open") or not r.get("diretta_current"):continue
            market=r.get("market");line=r.get("line")
            if market=="OVER_UNDER" and float(line or -99)!=2.5:continue
            if market not in {"HOME_DRAW_AWAY","OVER_UNDER","BOTH_TEAMS_TO_SCORE"}:continue
            groups[(market,str(line))].append(r)
        try:
            start=datetime.fromisoformat((e.get("start_time") or "").replace("Z","+00:00"))
            obs=datetime.fromisoformat((e.get("attempted_at") or e.get("certified_at") or "").replace("Z","+00:00"))
            lead=(start-obs).total_seconds()/60
            kickoff=start.isoformat()
        except Exception:
            lead=None;kickoff=e.get("start_time")
        for (market,line),rows in groups.items():
            required={"HOME","DRAW","AWAY"} if market=="HOME_DRAW_AWAY" else {"OVER","UNDER"} if market=="OVER_UNDER" else None
            sels={r.get("selection"):r for r in rows}
            if market=="BOTH_TEAMS_TO_SCORE":
                if {"YES","NO"}<=set(sels):required={"YES","NO"}
                elif {"GOAL","NO_GOAL"}<=set(sels):required={"GOAL","NO_GOAL"}
            if not required or not required<=set(sels):continue
            osum=sum(1/float(sels[x]["true_open"]) for x in required)
            csum=sum(1/float(sels[x]["diretta_current"]) for x in required)
            choices=[]
            for sel in required:
                r=sels[sel];op=(1/float(r["true_open"]))/osum;cp=(1/float(r["diretta_current"]))/csum
                choices.append((cp-op,sel,r,op,cp))
            delta,sel,r,op,cp=max(choices,key=lambda x:(x[0],x[1]))
            y=settle(market,sel,None if line=="None" else float(line),outs[eid])
            if y is None:continue
            candidates.append({"flashscore_event_id":eid,"event":e.get("event"),"tournament":e.get("flashscore_tournament"),
              "kickoff":kickoff,"observed_at":e.get("attempted_at") or e.get("certified_at"),
              "lead_minutes":lead,"lead_bin":lead_bin(lead),"market":market,
              "line":None if line=="None" else float(line),"selection":sel,
              "true_open_price":float(r["true_open"]),"observed_current_price":float(r["diretta_current"]),
              "open_devig_probability":op,"current_devig_probability":cp,
              "movement_probability_pp":(cp-op)*100,
              "absolute_price_drop":float(r["true_open"])-float(r["diretta_current"]),
              "won":bool(y),"profit_at_observed_current":float(r["diretta_current"])-1 if y else -1})

    diagnostics=[]
    rules=[("DEVIG_PP_1",lambda x:x["movement_probability_pp"]>=1),
           ("DEVIG_PP_2",lambda x:x["movement_probability_pp"]>=2),
           ("DEVIG_PP_3",lambda x:x["movement_probability_pp"]>=3),
           ("ABS_PRICE_DROP_0_20",lambda x:x["absolute_price_drop"]>=.20)]
    markets=["HOME_DRAW_AWAY","OVER_UNDER","BOTH_TEAMS_TO_SCORE"]
    for market in markets:
      mr=[x for x in candidates if x["market"]==market]
      for name,fn in rules:
        rs=sorted([x for x in mr if fn(x)],key=lambda x:(x.get("kickoff") or "",x["flashscore_event_id"]))
        profits=[x["profit_at_observed_current"] for x in rs]
        diagnostics.append({"market":market,"rule":name,"signals":len(rs),
          "fixtures":len({x["flashscore_event_id"] for x in rs}),
          "wins":sum(x["won"] for x in rs),"hit_rate":sum(x["won"] for x in rs)/len(rs) if rs else None,
          "flat_stake_roi_at_observed_current":sum(profits)/len(profits) if profits else None,
          "roi_bootstrap_ci95":ci_roi(profits),"max_drawdown_units":max_drawdown(profits) if profits else None,
          "lead_time_counts":dict(sorted((b,sum(x["lead_bin"]==b for x in rs)) for b in {x["lead_bin"] for x in rs})),
          "decision":"NO_PROMOTION_UNLESS_CI_LOWER_BOUND_ABOVE_ZERO_AND_REPLICATION_EXISTS"})

    report={"schema_version":"radar-goldbet-fixture-level-mms-v1","generated_at":datetime.now(timezone.utc).isoformat(),
      "classification":"PROSPECTIVE_2026_SAME_BOOK_OBSERVED_CURRENT_DIAGNOSTIC",
      "methodology":{"bookmaker":"GoldBet","same_bookmaker":True,"identity_join":"EXACT_FLASHSCORE_EVENT_ID",
        "signal_unit":"one maximum de-vig probability-shortening selection per fixture and market",
        "markets":{"HOME_DRAW_AWAY":"full_time","OVER_UNDER":"full_time line 2.5 only",
                   "BOTH_TEAMS_TO_SCORE":"full_time"},
        "thresholds_frozen":["1pp","2pp","3pp","absolute price drop 0.20"],
        "execution_price":"observed_current","observed_current_is_close":False,
        "outcomes_attached_after_signal_freeze":True,"post_kickoff_prices_used":False,
        "replication_requirement":"independent temporal block required even if a confidence interval excludes zero"},
      "sources":{"index":{"path":str(INDEX.relative_to(ROOT)),"sha256":hashlib.sha256(iraw).hexdigest()},
                 "outcomes":{"path":str(OUTCOMES.relative_to(ROOT)),"sha256":hashlib.sha256(oraw).hexdigest()}},
      "coverage":{"exact_outcome_events":len(outs),"candidate_fixture_market_rows":len(candidates),
                  "events":len({x["flashscore_event_id"] for x in candidates}),
                  "by_market":{m:sum(x["market"]==m for x in candidates) for m in markets}},
      "diagnostics":diagnostics,"candidate_rows":candidates,
      "decision":"NO_RULE_PROMOTED_PENDING_RESULTS_AND_INDEPENDENT_REPLICATION"}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["coverage"],ensure_ascii=False))

if __name__=="__main__":main()
