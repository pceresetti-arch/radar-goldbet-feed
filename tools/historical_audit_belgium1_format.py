#!/usr/bin/env python3
import csv, hashlib, json, time
from collections import Counter
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.request import Request, urlopen

OUT=Path("feed/historical/belgium1")
OUT.mkdir(parents=True, exist_ok=True)
REPORT=OUT/"format-audit-v1.json"
SOURCES=[
 ("2022/2023","https://www.football-data.co.uk/mmz4281/2223/B1.csv"),
 ("2023/2024","https://www.football-data.co.uk/mmz4281/2324/B1.csv"),
 ("2024/2025","https://www.football-data.co.uk/mmz4281/2425/B1.csv"),
 ("2025/2026","https://www.football-data.co.uk/mmz4281/2526/B1.csv"),
]

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
    seasons=[]; failures=[]
    for season,url in SOURCES:
        try:
            data,status,headers,attempt,prior_errors=fetch(url)
            rows=list(csv.DictReader(StringIO(data.decode("utf-8-sig"))))
            required={"Date","HomeTeam","AwayTeam","FTHG","FTAG","FTR"}
            missing=sorted(required-set(rows[0].keys() if rows else []))
            if missing: raise ValueError(f"missing columns {missing}")
            path=OUT/f"football-data-B1-{season.replace('/','-')}.csv"
            path.write_bytes(data)
            apps=Counter()
            for row in rows:
                apps[row["HomeTeam"]]+=1; apps[row["AwayTeam"]]+=1
            teams=sorted(apps)
            close_missing=sum(
                not all(row.get(k,"") for k in ("AvgCH","AvgCD","AvgCA"))
                for row in rows
            )
            seasons.append({
                "season":season,"url":url,"http_status":status,"fetch_attempt":attempt,
                "prior_fetch_errors":prior_errors,"rows":len(rows),"clubs":len(teams),
                "team_appearances":dict(sorted(apps.items())),
                "appearance_values":sorted(set(apps.values())),
                "all_teams_same_appearances":len(set(apps.values()))==1,
                "missing_average_close_triplets":close_missing,
                "sha256":hashlib.sha256(data).hexdigest(),
                "last_modified":headers.get("Last-Modified"),"path":str(path)
            })
        except Exception as exc:
            failures.append({"season":season,"url":url,"error":repr(exc)})
    signatures=[(s["rows"],s["clubs"],tuple(s["appearance_values"])) for s in seasons]
    all_four=len(seasons)==4
    comparable=all_four and len(set(signatures))==1
    cohorts={}
    for s,sig in zip(seasons,signatures):
        cohorts.setdefault(str(sig),[]).append(s["season"])
    report={
        "schema_version":"radar-historical-belgium1-format-audit-v1",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "competition":"Belgian Pro League",
        "source_provider":"Football-Data",
        "source_class":"EXTERNAL_FORMAT_DISCOVERY",
        "seasons":seasons,"failures":failures,
        "comparability":{
            "signature_fields":["fixture_rows","club_count","team_appearance_values"],
            "season_signatures":{s["season"]:{"rows":s["rows"],"clubs":s["clubs"],"appearance_values":s["appearance_values"]} for s in seasons},
            "cohorts":cohorts,
            "four_season_directly_comparable":comparable
        },
        "anti_hindsight":{
            "outcomes_used_for_format_decision":False,
            "odds_used_for_format_decision":False,
            "holdout_model_evaluated":False,
            "model_built":False
        },
        "status":"FORMAT_COMPARABLE_READY_FOR_FROZEN_SPLIT" if comparable else ("FOUR_SEASON_FORMAT_DRIFT_NO_MODEL" if all_four else "SOURCE_FAILURE_NO_MODEL"),
        "decision":"Do not construct development/holdout model until a comparable competition-phase rule is frozen without inspecting holdout performance."
    }
    REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if failures: raise RuntimeError(json.dumps(failures,ensure_ascii=False))
    print(json.dumps({"status":report["status"],"signatures":report["comparability"]["season_signatures"]},indent=2))

if __name__=="__main__": main()
