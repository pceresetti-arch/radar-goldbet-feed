#!/usr/bin/env python3
"""Audit and quarantine post-kickoff observations in GoldBet multi-snapshot state."""
from __future__ import annotations
import hashlib,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"feed/goldbet-diretta-movement-state.json"
OUT=ROOT/"feed/historical/open-close/goldbet-snapshot-hygiene-v1.json"

def expected(market):
    if market=="HOME_DRAW_AWAY": return {"HOME","DRAW","AWAY"}
    if market=="BOTH_TEAMS_TO_SCORE": return {"YES","NO"}
    if market=="OVER_UNDER": return {"OVER","UNDER"}
    return set()

def quality(lead):
    if lead is None:return "MISSING"
    if 20<=lead<=40:return "GOOD_T30"
    if 10<=lead<=50:return "ACCEPTABLE_T30"
    if 0<=lead<=120:return "FALLBACK_PRE_KICKOFF"
    return "STALE_PRE_KICKOFF"

def main():
    raw=SRC.read_bytes(); src=json.loads(raw)
    rows=list(src.get("records",{}).values())
    clean=[]; post=[]; groups=defaultdict(list)
    for x in rows:
        snaps=sorted(x.get("snapshots",[]),key=lambda z:z.get("captured_at",""))
        pre=[z for z in snaps if isinstance(z.get("minutes_to_start"),(int,float)) and z["minutes_to_start"]>=0]
        bad=[z for z in snaps if isinstance(z.get("minutes_to_start"),(int,float)) and z["minutes_to_start"]<0]
        target=min(pre,key=lambda z:abs(z["minutes_to_start"]-30)) if pre else None
        last=min(pre,key=lambda z:z["minutes_to_start"]) if pre else None
        rec={"key":x.get("key"),"flashscore_event_id":x.get("flashscore_event_id"),"event":x.get("event"),
          "tournament":x.get("tournament"),"start_time":x.get("start_time"),"market":x.get("market"),
          "line":x.get("line"),"selection":x.get("selection"),"true_open_price":x.get("true_open_price"),
          "pre_kickoff_snapshots":len(pre),"post_kickoff_snapshots_excluded":len(bad),
          "t30_candidate":target,"t30_quality":quality(target.get("minutes_to_start") if target else None),
          "last_persisted_pre_kickoff":last,"last_persisted_is_certified_close":False}
        clean.append(rec)
        if bad: post.append({"key":x.get("key"),"flashscore_event_id":x.get("flashscore_event_id"),
          "market":x.get("market"),"selection":x.get("selection"),"count":len(bad),
          "min_minutes_to_start":min(z["minutes_to_start"] for z in bad)})
        groups[(x.get("flashscore_event_id"),x.get("market"),str(x.get("line")))].append(rec)

    group_audit=[]
    for (eid,mkt,line),rr in groups.items():
        exp=expected(mkt); sels={x["selection"] for x in rr}
        quals={x["t30_quality"] for x in rr}
        complete=(not exp) or exp.issubset(sels)
        group_audit.append({"flashscore_event_id":eid,"event":rr[0]["event"],"tournament":rr[0]["tournament"],
          "market":mkt,"line":None if line=="None" else line,"selections":sorted(sels),
          "expected_selections":sorted(exp),"selection_complete":complete,
          "all_good_t30":complete and all(x["t30_quality"]=="GOOD_T30" for x in rr),
          "all_acceptable_t30":complete and all(x["t30_quality"] in {"GOOD_T30","ACCEPTABLE_T30"} for x in rr),
          "all_pre_kickoff_available":complete and all(x["pre_kickoff_snapshots"]>0 for x in rr)})
    event_ids={x["flashscore_event_id"] for x in clean}
    post_event_ids={x["flashscore_event_id"] for x in post}
    report={"schema_version":"radar-goldbet-snapshot-hygiene-v1","generated_at":datetime.now(timezone.utc).isoformat(),
      "classification":"PRE_KICKOFF_SANITIZATION_AND_T30_COVERAGE_AUDIT",
      "source":{"path":str(SRC.relative_to(ROOT)),"sha256":hashlib.sha256(raw).hexdigest(),
        "bookmaker":src.get("bookmaker"),"same_bookmaker":src.get("same_bookmaker")},
      "policy":{"post_kickoff_features_forbidden":True,"negative_minutes_to_start_quarantined":True,
        "t30_good_window_minutes":[20,40],"t30_acceptable_window_minutes":[10,50],
        "last_persisted_pre_kickoff_is_close":False},
      "coverage":{"records":len(clean),"events":len(event_ids),"market_groups":len(group_audit),
        "records_with_post_kickoff_snapshots":len(post),"events_with_post_kickoff_snapshots":len(post_event_ids),
        "post_kickoff_snapshots_excluded":sum(x["count"] for x in post),
        "records_good_t30":sum(x["t30_quality"]=="GOOD_T30" for x in clean),
        "records_acceptable_t30":sum(x["t30_quality"] in {"GOOD_T30","ACCEPTABLE_T30"} for x in clean),
        "groups_selection_complete":sum(x["selection_complete"] for x in group_audit),
        "groups_all_good_t30":sum(x["all_good_t30"] for x in group_audit),
        "groups_all_acceptable_t30":sum(x["all_acceptable_t30"] for x in group_audit),
        "groups_all_pre_kickoff_available":sum(x["all_pre_kickoff_available"] for x in group_audit)},
      "sanitized_records":clean,"group_audit":group_audit,"quarantined_post_kickoff_records":post,
      "decision":"POST_KICKOFF_STATE_CONTAMINATION_QUARANTINED_T30_SAMPLE_DIAGNOSTIC_ONLY"}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["coverage"]))

if __name__=="__main__":main()
