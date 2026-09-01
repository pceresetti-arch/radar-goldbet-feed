#!/usr/bin/env python3
"""Resolve final outcomes for the GoldBet TRUE OPEN index by exact Flashscore ID.

Outcomes are intentionally stored in a separate post-match table. No market
feature is constructed here and fuzzy identity confidence fields are ignored.
"""
from __future__ import annotations
import hashlib, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"feed/diretta-goldbet-true-open-index.json"
OUT=ROOT/"feed/historical/open-close/goldbet-exact-outcomes-v1.json"
HEADERS={"User-Agent":"Mozilla/5.0","x-fsign":"SW9D1eZo","referer":"https://www.flashscore.com/"}

def parse(raw:bytes):
    text=raw.decode("utf-8","replace")
    periods=[]
    for section in text.split("~"):
        fields={}
        for part in section.split("¬"):
            if "÷" in part:
                k,v=part.split("÷",1); fields[k]=v
        if fields.get("AC") in {"1st Half","2nd Half"}:
            try:
                periods.append({"period":fields["AC"],"home":int(fields["IG"]),"away":int(fields["IH"])})
            except (KeyError,ValueError):
                pass
    by={p["period"]:p for p in periods}
    if set(by)!={"1st Half","2nd Half"}:
        return None,periods
    return {"home_goals":by["1st Half"]["home"]+by["2nd Half"]["home"],
            "away_goals":by["1st Half"]["away"]+by["2nd Half"]["away"],
            "periods":[by["1st Half"],by["2nd Half"]]},periods

def one(item):
    source_key,e=item
    eid=e.get("flashscore_event_id")
    base={"source_event_key":source_key,"flashscore_event_id":eid,"event":e.get("event"),
          "tournament":e.get("flashscore_tournament"),"kickoff":e.get("start_time") or e.get("kickoff")}
    if not eid:
        return {**base,"status":"MISSING_FLASHSCORE_EVENT_ID"}
    url=f"https://www.flashscore.com/x/feed/df_sui_1_{eid}"
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,timeout=25) as r:
                raw=r.read()
            result,periods=parse(raw)
            if result:
                return {**base,"status":"FINAL_TWO_REGULAR_HALVES_PARSED","endpoint":url,
                        "raw_sha256":hashlib.sha256(raw).hexdigest(),**result}
            return {**base,"status":"NOT_FINAL_OR_UNPARSEABLE","endpoint":url,
                    "raw_sha256":hashlib.sha256(raw).hexdigest(),"parsed_periods":periods}
        except Exception as ex:
            last=f"{type(ex).__name__}:{ex}"
            time.sleep(0.6*(attempt+1))
    return {**base,"status":"SOURCE_FAILURE","endpoint":url,"error":last}

def main():
    raw=INDEX.read_bytes(); data=json.loads(raw)
    events=data.get("events") or {}
    ordered=sorted(events.items())
    results=[]
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs={pool.submit(one,x):x[0] for x in ordered}
        for fut in as_completed(futs):
            results.append(fut.result())
    results.sort(key=lambda x:(x.get("flashscore_event_id") or "",x.get("source_event_key") or ""))
    counts={}
    for x in results: counts[x["status"]]=counts.get(x["status"],0)+1
    duplicate_ids={}
    for x in results:
        eid=x.get("flashscore_event_id")
        if eid: duplicate_ids[eid]=duplicate_ids.get(eid,0)+1
    report={
      "schema_version":"radar-goldbet-exact-outcomes-v1",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "methodology":{
        "identity_join":"EXACT_FLASHSCORE_EVENT_ID_ONLY",
        "endpoint":"df_sui_1_{flashscore_event_id}",
        "final_gate":"both 1st Half and 2nd Half score sections must parse as integers",
        "outcome_role":"POST_MATCH_LABEL_ONLY",
        "pre_match_features_in_this_file":False,
        "forbidden_fields":["home_score","away_score","match_score"],
        "note":"Those forbidden index fields are fuzzy fixture-match confidence, not goals."
      },
      "source_index":{"path":str(INDEX.relative_to(ROOT)),"sha256":hashlib.sha256(raw).hexdigest(),
                      "declared_certified_events":data.get("certified_total"),"event_records":len(events)},
      "coverage":{"records":len(results),"unique_flashscore_ids":len(duplicate_ids),
                  "duplicate_flashscore_ids":sum(1 for n in duplicate_ids.values() if n>1),
                  "status_counts":counts},
      "outcomes":results
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["coverage"],ensure_ascii=False))

if __name__=="__main__": main()
