#!/usr/bin/env python3
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SOURCE=Path("feed/diretta-goldbet-true-open-index.json")
OUT=Path("feed/historical/open-close/goldbet-true-open-joinability-audit-v2.json")

def dt(value):
    if not value: return None
    try:
        return datetime.fromisoformat(str(value).replace("Z","+00:00"))
    except Exception:
        return None

def percentile(xs,p):
    if not xs: return None
    ys=sorted(xs); pos=(len(ys)-1)*p; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    return ys[lo] if lo==hi else ys[lo]+(ys[hi]-ys[lo])*(pos-lo)

def main():
    raw=SOURCE.read_bytes(); data=json.loads(raw); events=data.get("events",{})
    timing=Counter(); status=Counter(); bookmakers=Counter(); markets=Counter(); selections=Counter()
    rows_total=rows_complete=primary_rows=primary_drops=0
    primary_drop_events=set(); offsets=[]; start_times=[]; attempted_times=[]
    identity_scores=[]; score_fractional=0; score_outside_goal_plausible=0
    missing=Counter(); row_keys=Counter(); event_keys=Counter()
    for event_key,e in events.items():
        event_keys.update(e.keys()); status[str(e.get("status"))]+=1
        bm=e.get("bookmaker") or {}; bookmakers[f"{bm.get('id')}:{bm.get('name')}"]+=1
        st=dt(e.get("start_time")); at=dt(e.get("attempted_at") or e.get("certified_at"))
        if st: start_times.append(st)
        else: missing["start_time"]+=1
        if at: attempted_times.append(at)
        else: missing["observation_timestamp"]+=1
        if st and at:
            delta=(st-at).total_seconds()/60
            offsets.append(delta)
            if delta>0: timing["PRE_KICKOFF_OBSERVED_CURRENT"]+=1
            elif delta==0: timing["AT_KICKOFF"]+=1
            else: timing["POST_KICKOFF_INVALID_FOR_PREMATCH"]+=1
        else: timing["UNPARSEABLE"]+=1
        for key in ("home_score","away_score","match_score"):
            v=e.get(key)
            if isinstance(v,(int,float)):
                identity_scores.append(v)
                if abs(v-round(v))>1e-9: score_fractional+=1
                if v>20 or v<0: score_outside_goal_plausible+=1
        for r in e.get("rows") or []:
            rows_total+=1; row_keys.update(r.keys())
            market=str(r.get("market")); selection=str(r.get("selection"))
            markets[market]+=1; selections[f"{market}:{selection}"]+=1
            op=r.get("true_open"); cur=r.get("diretta_current")
            if isinstance(op,(int,float)) and isinstance(cur,(int,float)):
                rows_complete+=1
                is_primary=(market=="HOME_DRAW_AWAY") or (market in ("OVER_UNDER","TOTAL_GOALS") and selection=="OVER" and r.get("period")=="full_time")
                if is_primary:
                    primary_rows+=1
                    if op-cur>=0.20-1e-12:
                        primary_drops+=1; primary_drop_events.add(event_key)
            else: missing["row_true_open_or_current"]+=1
    pre=sum(v for k,v in timing.items() if k=="PRE_KICKOFF_OBSERVED_CURRENT")
    report={
      "schema_version":"radar-goldbet-true-open-joinability-audit-v2",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "source":{"path":str(SOURCE),"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)},
      "inventory":{
        "events":len(events),"rows":rows_total,"rows_with_true_open_and_current":rows_complete,
        "event_statuses":dict(status),"bookmakers":dict(bookmakers),
        "market_rows":dict(markets),"selection_rows":dict(selections)
      },
      "timestamp_audit":{
        "classification":dict(timing),
        "pre_kickoff_event_share":pre/len(events) if events else None,
        "minutes_before_kickoff":{"p05":percentile(offsets,.05),"p50":percentile(offsets,.5),"p95":percentile(offsets,.95),"min":min(offsets) if offsets else None,"max":max(offsets) if offsets else None},
        "start_time_min":min(start_times).isoformat() if start_times else None,
        "start_time_max":max(start_times).isoformat() if start_times else None,
        "observation_time_min":min(attempted_times).isoformat() if attempted_times else None,
        "observation_time_max":max(attempted_times).isoformat() if attempted_times else None
      },
      "identity_score_semantics":{
        "fields":["home_score","away_score","match_score"],
        "values":len(identity_scores),
        "min":min(identity_scores) if identity_scores else None,
        "max":max(identity_scores) if identity_scores else None,
        "fractional_values":score_fractional,
        "interpretation":"Fixture/team fuzzy-match confidence fields, not final football scores. They are forbidden as outcomes."
      },
      "mms_observed_current_diagnostic":{
        "primary_market_rows_with_prices":primary_rows,
        "absolute_drop_ge_0_20_rows":primary_drops,
        "events_with_at_least_one_primary_drop":len(primary_drop_events),
        "classification":"TRUE_OPEN_TO_SINGLE_OBSERVED_CURRENT_SAME_BOOK_DIAGNOSTIC",
        "not_close_reason":"The index stores one attempted/certified observation per event and does not certify it as the final last-pre-kickoff price.",
        "active_drop_only":True,
        "rebounded_after_drop_measurable":False
      },
      "joinability":{
        "true_open_exact_identity":"AVAILABLE",
        "observed_current_exact_identity":"AVAILABLE",
        "observation_timestamp":"AVAILABLE_AT_EVENT_LEVEL",
        "certified_last_pre_kickoff_close":"NOT_AVAILABLE",
        "final_outcome":"NOT_AVAILABLE_IN_THIS_SOURCE",
        "outcome_join_using_home_score_away_score":"FORBIDDEN_IDENTITY_CONFIDENCE_NOT_GOALS",
        "clv":"NOT_CALCULABLE_WITHOUT_CERTIFIED_CLOSE",
        "roi_brier_log_loss":"NOT_CALCULABLE_WITHOUT_OUTCOME_AND_EX_ANTE_SELECTION"
      },
      "quality":{"missing":dict(missing),"event_keys":sorted(event_keys),"row_keys":sorted(row_keys)},
      "decision":"DO_NOT_RELABEL_DIRETTA_CURRENT_AS_CLOSE; USE_ONLY_PRE_KICKOFF_ROWS_AS_OPEN_TO_OBSERVED_CURRENT_DIAGNOSTIC; ACQUIRE_CERTIFIED_LAST_PRE_KICKOFF_SNAPSHOT_AND_OUTCOME_SEPARATELY"
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"events":len(events),"rows":rows_total,"timing":dict(timing),"primary_drops":primary_drops,"identity_score_range":[report["identity_score_semantics"]["min"],report["identity_score_semantics"]["max"]]},indent=2))

if __name__=="__main__":
    main()
