#!/usr/bin/env python3
"""Error decomposition for the material 1X2 PP1 lead-time drift."""
from __future__ import annotations
import hashlib,json,random
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"feed/historical/open-close/goldbet-fixture-level-mms-v1.json"
OUT=ROOT/"feed/historical/open-close/goldbet-1x2-drift-decomposition-v1.json"

def price_bin(x):
    if x<1.75:return "P_LT_1_75"
    if x<2.5:return "P_1_75_2_50"
    if x<4:return "P_2_50_4_00"
    return "P_GE_4_00"

def mean(xs):return sum(xs)/len(xs) if xs else None

def summary(rows):
    return {"n":len(rows),"roi":mean([x["profit_at_observed_current"] for x in rows]),
      "hit_rate":mean([1 if x["won"] else 0 for x in rows]),
      "mean_price":mean([x["observed_current_price"] for x in rows]),
      "mean_current_probability":mean([x["current_devig_probability"] for x in rows]),
      "calibration_error_actual_minus_probability":mean([(1 if x["won"] else 0)-x["current_devig_probability"] for x in rows]),
      "mean_movement_pp":mean([x["movement_probability_pp"] for x in rows])}

def main():
    raw=SRC.read_bytes();data=json.loads(raw)
    rows=[x for x in data["candidate_rows"] if x["market"]=="HOME_DRAW_AWAY" and x["movement_probability_pp"]>=1 and x.get("lead_minutes") is not None]
    for x in rows:
        x["lead_group"]="NEAR_LT_360" if x["lead_minutes"]<360 else "FAR_GE_360"
        x["price_bin"]=price_bin(x["observed_current_price"])
    near=[x for x in rows if x["lead_group"]=="NEAR_LT_360"];far=[x for x in rows if x["lead_group"]=="FAR_GE_360"]

    composition=[]
    for side in ["HOME","DRAW","AWAY"]:
      for pb in ["P_LT_1_75","P_1_75_2_50","P_2_50_4_00","P_GE_4_00"]:
        a=[x for x in near if x["selection"]==side and x["price_bin"]==pb]
        b=[x for x in far if x["selection"]==side and x["price_bin"]==pb]
        if a or b:composition.append({"selection":side,"price_bin":pb,"near":summary(a),"far":summary(b)})

    # Fixed common-composition standardization over cells with >=5 in both groups.
    eligible=[c for c in composition if c["near"]["n"]>=5 and c["far"]["n"]>=5]
    total=sum(c["near"]["n"]+c["far"]["n"] for c in eligible)
    adjusted=sum(((c["near"]["roi"]-c["far"]["roi"])*(c["near"]["n"]+c["far"]["n"])/total) for c in eligible) if total else None

    by=defaultdict(lambda:{"near":[],"far":[]})
    for x in rows:
        by[(x["selection"],x["price_bin"])]["near" if x["lead_group"].startswith("NEAR") else "far"].append(x["profit_at_observed_current"])
    weights={k:(len(v["near"])+len(v["far"]))/total for k,v in by.items() if len(v["near"])>=5 and len(v["far"])>=5} if total else {}
    rng=random.Random(20260901);sims=[]
    for _ in range(10000):
        d=0
        for k,w in weights.items():
            a=by[k]["near"];b=by[k]["far"]
            am=sum(a[rng.randrange(len(a))] for __ in a)/len(a)
            bm=sum(b[rng.randrange(len(b))] for __ in b)/len(b)
            d+=w*(am-bm)
        sims.append(d)
    sims.sort()
    adj_ci=[sims[250],sims[9749]] if sims else None

    # Side-only and price-only tables expose mix.
    side_table=[{"selection":s,"near":summary([x for x in near if x["selection"]==s]),
                 "far":summary([x for x in far if x["selection"]==s])} for s in ["HOME","DRAW","AWAY"]]
    price_table=[{"price_bin":p,"near":summary([x for x in near if x["price_bin"]==p]),
                  "far":summary([x for x in far if x["price_bin"]==p])} for p in ["P_LT_1_75","P_1_75_2_50","P_2_50_4_00","P_GE_4_00"]]

    report={"schema_version":"radar-goldbet-1x2-drift-decomposition-v1","generated_at":datetime.now(timezone.utc).isoformat(),
      "classification":"ERROR_ANALYSIS_NO_RULE_TUNING",
      "methodology":{"target":"FT 1X2 maximum shortening candidate with movement >=1pp",
        "lead_split":"<360 versus >=360 minutes","controls":["selection side","observed-current price bin"],
        "standardization":"fixed pooled composition across cells with >=5 observations in both groups",
        "bootstrap_draws":10000,"observed_current_is_close":False},
      "source":{"path":str(SRC.relative_to(ROOT)),"sha256":hashlib.sha256(raw).hexdigest()},
      "raw":{"near":summary(near),"far":summary(far),"roi_difference_near_minus_far":summary(near)["roi"]-summary(far)["roi"]},
      "side_composition":side_table,"price_composition":price_table,"side_price_cells":composition,
      "standardized":{"eligible_cells":len(eligible),"covered_near":sum(c["near"]["n"] for c in eligible),
        "covered_far":sum(c["far"]["n"] for c in eligible),"near_minus_far_roi":adjusted,"bootstrap_ci95":adj_ci},
      "decision":"DRIFT_PERSISTS_AFTER_SIDE_PRICE_STANDARDIZATION" if adj_ci and (adj_ci[1]<0 or adj_ci[0]>0) else "DRIFT_NOT_ROBUST_AFTER_STANDARDIZATION"}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"raw_n":[len(near),len(far)],"adjusted":adjusted,"ci":adj_ci,"decision":report["decision"]}))

if __name__=="__main__":main()
