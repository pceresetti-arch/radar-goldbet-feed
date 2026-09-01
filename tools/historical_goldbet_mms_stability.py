#!/usr/bin/env python3
"""Stability/drift audit for fixture-level GoldBet MMS diagnostics."""
from __future__ import annotations
import hashlib,json,random
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"feed/historical/open-close/goldbet-fixture-level-mms-v1.json"
OUT=ROOT/"feed/historical/open-close/goldbet-mms-stability-v1.json"

def roi(rows):
    return sum(x["profit_at_observed_current"] for x in rows)/len(rows) if rows else None

def roi_ci(rows,draws=5000,seed=1):
    if not rows:return None
    vals=[x["profit_at_observed_current"] for x in rows];n=len(vals);rng=random.Random(seed+n)
    sims=sorted(sum(vals[rng.randrange(n)] for __ in range(n))/n for _ in range(draws))
    return [sims[int(.025*draws)],sims[int(.975*draws)-1]]

def diff_ci(a,b,draws=5000,seed=2):
    if len(a)<10 or len(b)<10:return None
    av=[x["profit_at_observed_current"] for x in a];bv=[x["profit_at_observed_current"] for x in b]
    rng=random.Random(seed+len(a)*7+len(b));s=[]
    for _ in range(draws):
        ar=sum(av[rng.randrange(len(av))] for __ in av)/len(av)
        br=sum(bv[rng.randrange(len(bv))] for __ in bv)/len(bv)
        s.append(ar-br)
    s.sort()
    return {"a_minus_b":roi(a)-roi(b),"ci95":[s[int(.025*draws)],s[int(.975*draws)-1]],"draws":draws}

def pack(name,rows):
    return {"segment":name,"n":len(rows),"events":len({x["flashscore_event_id"] for x in rows}),
            "roi":roi(rows),"roi_ci95":roi_ci(rows,seed=sum(ord(c) for c in name))}

def main():
    raw=SRC.read_bytes();data=json.loads(raw);rows=data["candidate_rows"]
    rules=[("PP1",lambda x:x["movement_probability_pp"]>=1),
           ("PP2",lambda x:x["movement_probability_pp"]>=2),
           ("PP3",lambda x:x["movement_probability_pp"]>=3),
           ("DROP020",lambda x:x["absolute_price_drop"]>=.20)]
    audits=[];material=[]
    for market in ["HOME_DRAW_AWAY","OVER_UNDER","BOTH_TEAMS_TO_SCORE"]:
      base=[x for x in rows if x["market"]==market]
      for rn,fn in rules:
        r=sorted([x for x in base if fn(x)],key=lambda x:(x.get("kickoff") or "",x["flashscore_event_id"]))
        near=[x for x in r if x.get("lead_minutes") is not None and x["lead_minutes"]<360]
        far=[x for x in r if x.get("lead_minutes") is not None and x["lead_minutes"]>=360]
        half=len(r)//2;early=r[:half];late=r[half:]
        lead_diff=diff_ci(near,far,seed=11)
        time_diff=diff_ci(early,late,seed=17)
        rec={"market":market,"rule":rn,"total_n":len(r),
             "lead_time":{"a":pack("T_LT_360",near),"b":pack("T_GE_360",far),"difference":lead_diff},
             "chronology":{"a":pack("EARLY_HALF",early),"b":pack("LATE_HALF",late),"difference":time_diff}}
        for axis,obj in [("lead_time",lead_diff),("chronology",time_diff)]:
            if obj and (obj["ci95"][0]>0 or obj["ci95"][1]<0):
                material.append({"market":market,"rule":rn,"axis":axis,**obj})
        audits.append(rec)

    # Country-prefix cells are descriptive and only emitted at n>=30.
    countries=[]
    for market in ["HOME_DRAW_AWAY","OVER_UNDER","BOTH_TEAMS_TO_SCORE"]:
      r=[x for x in rows if x["market"]==market and x["movement_probability_pp"]>=1]
      names={}
      for x in r:
        country=(x.get("tournament") or "UNKNOWN").split(":",1)[0]
        names.setdefault(country,[]).append(x)
      for country,cell in sorted(names.items()):
        if len(cell)>=30:countries.append({"market":market,"rule":"PP1","country":country,**pack(country,cell)})

    report={"schema_version":"radar-goldbet-mms-stability-v1","generated_at":datetime.now(timezone.utc).isoformat(),
      "classification":"PROSPECTIVE_2026_STABILITY_DIAGNOSTIC",
      "methodology":{"source":"fixture-level one-selection-per-event-market candidates",
        "lead_split":"<360 versus >=360 minutes before kickoff","chronology_split":"ordered equal halves within market-rule",
        "minimum_for_difference":10,"bootstrap_draws":5000,
        "material_drift_definition":"95% bootstrap interval for ROI difference excludes zero",
        "observed_current_is_close":False},
      "source":{"path":str(SRC.relative_to(ROOT)),"sha256":hashlib.sha256(raw).hexdigest()},
      "audits":audits,"country_cells_n_ge_30":countries,"material_drift_findings":material,
      "decision":"MATERIAL_DRIFT_FOUND" if material else "NO_MATERIAL_DRIFT_DETECTED_NO_RULE_CHANGE"}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"audits":len(audits),"country_cells":len(countries),"material":len(material)}))

if __name__=="__main__":main()
