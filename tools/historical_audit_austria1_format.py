#!/usr/bin/env python3
import csv, hashlib, json, time
from collections import Counter
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.request import Request, urlopen

OUT=Path("feed/historical/austria1")
OUT.mkdir(parents=True,exist_ok=True)
REPORT=OUT/"format-audit-v1.json"
SOURCE="https://www.football-data.co.uk/new/AUT.csv"
TARGET=["2022/2023","2023/2024","2024/2025","2025/2026"]

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

def norm_season(value):
    s=(value or "").strip().replace("-","/").replace("_","/")
    if len(s)==4 and s.isdigit():
        y=int(s)
        return f"{y}/{y+1}"
    if len(s)==7 and s[4]=="/" and s[:4].isdigit() and s[5:].isdigit():
        return f"{s[:4]}/{s[5:]}"
    if len(s)==9 and s[4]=="/" and s[:4].isdigit() and s[5:].isdigit():
        return s
    return s

def main():
    generated=datetime.now(timezone.utc).isoformat()
    failures=[]
    try:
        data,status,headers,attempt,prior_errors=fetch(SOURCE)
        snapshot=OUT/"football-data-AUT.csv"
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
    season_counts=Counter(norm_season(r.get("Season")) for r in rows)
    league_values=sorted(league_counts)
    exact=[x for x in league_values if x.lower() in ("bundesliga","austrian bundesliga")]
    contains=[x for x in league_values if "bundesliga" in x.lower()]
    selected_league=(exact or contains or [None])[0]
    seasons=[]
    for target in TARGET:
        sr=[r for r in rows if norm_season(r.get("Season"))==target and (r.get("League") or "").strip()==selected_league]
        apps=Counter()
        keys=[]
        invalid_results=0
        for r in sr:
            home=(r.get("Home") or "").strip(); away=(r.get("Away") or "").strip()
            apps[home]+=1; apps[away]+=1
            keys.append((target,(r.get("Date") or "").strip(),home,away))
            try:
                hg=int(r.get("HG","")); ag=int(r.get("AG",""))
                expected="H" if hg>ag else ("A" if ag>hg else "D")
                invalid_results+=expected!=(r.get("Res") or "").strip()
            except Exception:
                invalid_results+=1
        close_cols=("AvgCH","AvgCD","AvgCA")
        close_missing=sum(not all((r.get(k) or "").strip() for k in close_cols) for r in sr)
        seasons.append({
            "season":target,"rows":len(sr),"clubs":len(apps),
            "team_appearances":dict(sorted(apps.items())),
            "appearance_values":sorted(set(apps.values())),
            "all_teams_same_appearances":len(set(apps.values()))==1 if apps else False,
            "duplicate_fixture_keys":len(keys)-len(set(keys)),
            "invalid_or_inconsistent_results":invalid_results,
            "missing_average_close_triplets":close_missing,
        })
    signatures=[(s["rows"],s["clubs"],tuple(s["appearance_values"])) for s in seasons]
    all_four=all(s["rows"]>0 for s in seasons)
    comparable=all_four and len(set(signatures))==1
    report={
        "schema_version":"radar-historical-austria1-format-audit-v1",
        "generated_at":generated,
        "competition":"Austrian Bundesliga",
        "source_provider":"Football-Data",
        "source_url":SOURCE,
        "source_class":"EXTERNAL_FORMAT_DISCOVERY",
        "fetch":{
            "http_status":status,"attempt":attempt,"prior_errors":prior_errors,
            "bytes":len(data),"sha256":hashlib.sha256(data).hexdigest() if data else None,
            "last_modified":headers.get("Last-Modified"),"snapshot":str(OUT/"football-data-AUT.csv") if data else None
        },
        "source_schema":{"columns":header,"league_counts":dict(sorted(league_counts.items())),"season_counts":dict(sorted(season_counts.items()))},
        "selection_rule_frozen_before_model":{
            "league_field_exact_value":selected_league,
            "target_seasons":TARGET,
            "no_result_or_odds_based_row_selection":True
        },
        "seasons":seasons,
        "failures":failures,
        "comparability":{
            "signature_fields":["fixture_rows","club_count","team_appearance_values"],
            "season_signatures":{s["season"]:{"rows":s["rows"],"clubs":s["clubs"],"appearance_values":s["appearance_values"]} for s in seasons},
            "four_season_directly_comparable":comparable
        },
        "anti_hindsight":{
            "outcomes_used_for_format_decision":False,
            "odds_used_for_format_decision":False,
            "holdout_model_evaluated":False,
            "model_built":False
        },
        "status":"FORMAT_COMPARABLE_READY_FOR_FROZEN_SPLIT" if comparable else ("FOUR_SEASON_FORMAT_DRIFT_NO_MODEL" if all_four else "SOURCE_FAILURE_OR_MISSING_SEASON_NO_MODEL"),
        "decision":"Construct no development/holdout model unless four target seasons share the same phase-exposure signature; inspect format only."
    }
    REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"selected_league":selected_league,"signatures":report["comparability"]["season_signatures"],"failures":failures},indent=2))
    if failures: raise RuntimeError(json.dumps(failures,ensure_ascii=False))

if __name__=="__main__": main()
