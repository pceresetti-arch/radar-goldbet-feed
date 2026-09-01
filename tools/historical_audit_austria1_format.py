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

def parse_date(value):
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
        try: return datetime.strptime((value or "").strip(),fmt).date()
        except ValueError: pass
    raise ValueError(f"unparsed date {value!r}")

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
        sr.sort(key=lambda r:(parse_date(r.get("Date")), (r.get("Time") or ""), (r.get("Home") or ""), (r.get("Away") or "")))
        core=sr[:192]
        core_apps=Counter()
        for r in core:
            core_apps[(r.get("Home") or "").strip()]+=1; core_apps[(r.get("Away") or "").strip()]+=1
        extras=sr[192:]
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
            "chronological_core_192":{"rows":len(core),"clubs":len(core_apps),"appearance_values":sorted(set(core_apps.values())),"balanced_12_clubs_32_each":len(core)==192 and len(core_apps)==12 and set(core_apps.values())=={32}},
            "subsequent_extras":[{"date":r.get("Date"),"time":r.get("Time"),"home":r.get("Home"),"away":r.get("Away")} for r in extras],
        })
    signatures=[(s["rows"],s["clubs"],tuple(s["appearance_values"])) for s in seasons]
    all_four=all(s["rows"]>0 for s in seasons)
    comparable=all_four and len(set(signatures))==1
    core_comparable=all_four and all(s["chronological_core_192"]["balanced_12_clubs_32_each"] for s in seasons)
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
            "four_season_directly_comparable":comparable,
            "chronological_core_192_comparable":core_comparable,
            "core_rule":"Retain the earliest 192 fixtures only when they form 12 clubs with exactly 32 appearances each; exclude only chronologically subsequent fixtures."
        },
        "anti_hindsight":{
            "outcomes_used_for_format_decision":False,
            "odds_used_for_format_decision":False,
            "holdout_model_evaluated":False,
            "model_built":False
        },
        "status":"FULL_FORMAT_COMPARABLE_READY_FOR_FROZEN_SPLIT" if comparable else ("CORE_192_COMPARABLE_READY_FOR_FROZEN_SPLIT" if core_comparable else ("FOUR_SEASON_FORMAT_DRIFT_NO_MODEL" if all_four else "SOURCE_FAILURE_OR_MISSING_SEASON_NO_MODEL")),
        "decision":"A structural model is eligible only if the frozen chronological core rule yields 192 fixtures, 12 clubs and 32 appearances per club in every season; subsequent playoff fixtures remain excluded."
    }
    REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"selected_league":selected_league,"signatures":report["comparability"]["season_signatures"],"failures":failures},indent=2))
    if failures: raise RuntimeError(json.dumps(failures,ensure_ascii=False))

if __name__=="__main__": main()
