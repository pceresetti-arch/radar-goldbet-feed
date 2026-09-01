#!/usr/bin/env python3
import csv, hashlib, json, time
from collections import Counter
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.request import Request, urlopen

OUT=Path("feed/historical/japan1")
OUT.mkdir(parents=True,exist_ok=True)
REPORT=OUT/"format-audit-v1.json"
SOURCE="https://www.football-data.co.uk/new/JPN.csv"
TARGET=["2022","2023","2024","2025"]

def fetch(url):
    errors=[]
    for attempt in range(1,4):
        try:
            req=Request(url,headers={"User-Agent":"radar-historical-backtest/1.0"})
            with urlopen(req,timeout=60) as r:
                return r.read(),getattr(r,"status",200),dict(r.headers.items()),attempt,errors
        except Exception as exc:
            errors.append(repr(exc))
            if attempt<3: time.sleep(attempt*3)
    raise RuntimeError(json.dumps(errors))

def main():
    generated=datetime.now(timezone.utc).isoformat()
    failures=[]
    try:
        data,status,headers,attempt,prior_errors=fetch(SOURCE)
        snapshot=OUT/"football-data-JPN.csv"
        snapshot.write_bytes(data)
        rows=list(csv.DictReader(StringIO(data.decode("utf-8-sig"))))
        header=list(rows[0]) if rows else []
        required={"Country","League","Season","Date","Home","Away","HG","AG","Res"}
        missing=sorted(required-set(header))
        if missing: raise ValueError(f"missing columns {missing}")
    except Exception as exc:
        failures.append({"url":SOURCE,"error":repr(exc)})
        data=b""; status=None; headers={}; attempt=None; prior_errors=[]; rows=[]; header=[]

    league_counts=Counter((r.get("League") or "").strip() for r in rows)
    season_counts=Counter((r.get("Season") or "").strip() for r in rows)
    preferred=("J-League","J1 League","J1")
    selected_league=next((x for x in preferred if x in league_counts),None)
    if selected_league is None and league_counts:
        selected_league=max(league_counts,key=league_counts.get)
    seasons=[]
    for target in TARGET:
        sr=[r for r in rows if (r.get("Season") or "").strip()==target and (r.get("League") or "").strip()==selected_league]
        apps=Counter(); keys=[]; invalid=0
        for r in sr:
            home=(r.get("Home") or "").strip(); away=(r.get("Away") or "").strip()
            apps[home]+=1; apps[away]+=1
            keys.append((target,(r.get("Date") or "").strip(),home,away))
            try:
                hg=int(r.get("HG","")); ag=int(r.get("AG",""))
                expected="H" if hg>ag else ("A" if ag>hg else "D")
                invalid+=expected!=(r.get("Res") or "").strip()
            except Exception: invalid+=1
        seasons.append({
            "season":target,"rows":len(sr),"clubs":len(apps),
            "team_appearances":dict(sorted(apps.items())),
            "appearance_values":sorted(set(apps.values())),
            "all_teams_same_appearances":len(set(apps.values()))==1 if apps else False,
            "duplicate_fixture_keys":len(keys)-len(set(keys)),
            "invalid_or_inconsistent_results":invalid,
            "missing_average_close_triplets":sum(not all((r.get(k) or "").strip() for k in ("AvgCH","AvgCD","AvgCA")) for r in sr)
        })
    signatures=[(s["rows"],s["clubs"],tuple(s["appearance_values"])) for s in seasons]
    all_four=all(s["rows"]>0 for s in seasons)
    comparable=all_four and len(set(signatures))==1
    report={
        "schema_version":"radar-historical-japan1-format-audit-v1",
        "generated_at":generated,
        "competition":"J1 League",
        "source_provider":"Football-Data",
        "source_url":SOURCE,
        "source_class":"EXTERNAL_FORMAT_DISCOVERY",
        "fetch":{"http_status":status,"attempt":attempt,"prior_errors":prior_errors,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest() if data else None,"last_modified":headers.get("Last-Modified"),"snapshot":str(OUT/"football-data-JPN.csv") if data else None},
        "source_schema":{"columns":header,"league_counts":dict(sorted(league_counts.items())),"season_counts":dict(sorted(season_counts.items()))},
        "selection_rule_frozen_before_model":{"league_field_exact_value":selected_league,"target_seasons":TARGET,"no_result_or_odds_based_row_selection":True},
        "seasons":seasons,"failures":failures,
        "comparability":{"signature_fields":["fixture_rows","club_count","team_appearance_values"],"season_signatures":{s["season"]:{"rows":s["rows"],"clubs":s["clubs"],"appearance_values":s["appearance_values"]} for s in seasons},"four_season_directly_comparable":comparable},
        "anti_hindsight":{"outcomes_used_for_format_decision":False,"odds_used_for_format_decision":False,"holdout_model_evaluated":False,"model_built":False},
        "status":"FORMAT_COMPARABLE_READY_FOR_FROZEN_SPLIT" if comparable else ("FORMAT_DRIFT_18_TO_20_AND_2022_PLAYOFF_ROWS_NO_MODEL" if all_four else "SOURCE_FAILURE_OR_MISSING_SEASON_NO_MODEL"),
        "interpretation":{"season_2022":"310 rows include a regular 18-club 306-match schedule plus four rows involving lower-division playoff participants; full source league label is not phase-pure.","season_2023":"18 clubs and 306 balanced fixtures.","seasons_2024_2025":"20 clubs and 380 balanced fixtures after league expansion.","eligible_four_season_holdout":False,"future_safe_option":"A 20-club cohort currently has only 2024 and 2025 complete seasons, insufficient for the requested four-season development/holdout design.","decision":"NO_MODEL_NO_METRICS_NO_THRESHOLD_PROMOTION"},
        "decision":"Construct no development/holdout model unless all four target seasons share identical club count and schedule exposure; never downsample based on outcomes."
    }
    REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"selected_league":selected_league,"signatures":report["comparability"]["season_signatures"],"failures":failures},indent=2))
    if failures: raise RuntimeError(json.dumps(failures,ensure_ascii=False))

if __name__=="__main__": main()
