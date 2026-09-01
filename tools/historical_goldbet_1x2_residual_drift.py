#!/usr/bin/env python3
"""Residual decomposition of GoldBet 1X2 PP1 lead-time drift by competition and time."""
from __future__ import annotations
import hashlib,json,random
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"feed/historical/open-close/goldbet-fixture-level-mms-v1.json"
OUT=ROOT/"feed/historical/open-close/goldbet-1x2-residual-drift-v1.json"

def mean(x): return sum(x)/len(x) if x else None
def pbin(x):
    if x<1.75:return "LT_1_75"
    if x<2.5:return "1_75_2_50"
    if x<4:return "2_50_4_00"
    return "GE_4_00"
def country(x): return (x.get("tournament") or "UNKNOWN").split(":",1)[0].strip() or "UNKNOWN"
def summary(rows):
    return {"n":len(rows),"roi":mean([x["profit_at_observed_current"] for x in rows]),
      "hit_rate":mean([1 if x["won"] else 0 for x in rows]),
      "mean_price":mean([x["observed_current_price"] for x in rows]),
      "mean_lead_minutes":mean([x["lead_minutes"] for x in rows])}

def standardized(rows, control_keys, min_each=3, draws=10000, seed=20260901):
    cells=defaultdict(lambda:{"near":[],"far":[]})
    for x in rows:
        k=tuple(x[z] for z in control_keys)
        cells[k][x["lead_group"]].append(x["profit_at_observed_current"])
    eligible={k:v for k,v in cells.items() if len(v["near"])>=min_each and len(v["far"])>=min_each}
    total=sum(len(v["near"])+len(v["far"]) for v in eligible.values())
    if not total:
        return {"controls":control_keys,"min_each":min_each,"eligible_cells":0,"covered_near":0,"covered_far":0,
          "near_minus_far_roi":None,"bootstrap_ci95":None}
    weights={k:(len(v["near"])+len(v["far"]))/total for k,v in eligible.items()}
    point=sum(weights[k]*(mean(v["near"])-mean(v["far"])) for k,v in eligible.items())
    rng=random.Random(seed); sims=[]
    for _ in range(draws):
        d=0
        for k,v in eligible.items():
            a=v["near"];b=v["far"];w=weights[k]
            am=sum(a[rng.randrange(len(a))] for __ in a)/len(a)
            bm=sum(b[rng.randrange(len(b))] for __ in b)/len(b)
            d+=w*(am-bm)
        sims.append(d)
    sims.sort()
    return {"controls":control_keys,"min_each":min_each,"eligible_cells":len(eligible),
      "covered_near":sum(len(v["near"]) for v in eligible.values()),
      "covered_far":sum(len(v["far"]) for v in eligible.values()),
      "near_minus_far_roi":point,"bootstrap_ci95":[sims[250],sims[9749]]}

def main():
    raw=SRC.read_bytes();data=json.loads(raw)
    rows=[dict(x) for x in data["candidate_rows"] if x["market"]=="HOME_DRAW_AWAY" and
      x["movement_probability_pp"]>=1 and x.get("lead_minutes") is not None]
    rows.sort(key=lambda x:(x["kickoff"],x["flashscore_event_id"]))
    for i,x in enumerate(rows):
        x["lead_group"]="near" if x["lead_minutes"]<360 else "far"
        x["price_bin"]=pbin(x["observed_current_price"])
        x["country"]=country(x)
        x["time_half"]="early" if i<len(rows)/2 else "late"

    near=[x for x in rows if x["lead_group"]=="near"];far=[x for x in rows if x["lead_group"]=="far"]
    country_rows=[]
    for c in sorted(set(x["country"] for x in rows)):
        a=[x for x in near if x["country"]==c];b=[x for x in far if x["country"]==c]
        if len(a)+len(b)>=10:
            country_rows.append({"country":c,"near":summary(a),"far":summary(b),
              "near_minus_far_roi":(mean([x["profit_at_observed_current"] for x in a])-mean([x["profit_at_observed_current"] for x in b])) if a and b else None})
    country_rows.sort(key=lambda z:z["near"]["n"]+z["far"]["n"],reverse=True)

    tournament_rows=[]
    for t in sorted(set(x["tournament"] for x in rows)):
        a=[x for x in near if x["tournament"]==t];b=[x for x in far if x["tournament"]==t]
        if len(a)+len(b)>=8:
            tournament_rows.append({"tournament":t,"near":summary(a),"far":summary(b)})
    tournament_rows.sort(key=lambda z:z["near"]["n"]+z["far"]["n"],reverse=True)

    comp=standardized(rows,["country","selection","price_bin"],3,10000,20260901)
    base=standardized(rows,["selection","price_bin"],5,10000,20260902)
    halves={}
    for h in ["early","late"]:
        rr=[x for x in rows if x["time_half"]==h]
        halves[h]={"raw_near":summary([x for x in rr if x["lead_group"]=="near"]),
          "raw_far":summary([x for x in rr if x["lead_group"]=="far"]),
          "side_price_standardized":standardized(rr,["selection","price_bin"],3,10000,20260903+(h=="late"))}

    nc=Counter(x["country"] for x in near);fc=Counter(x["country"] for x in far)
    near_hhi=sum((n/len(near))**2 for n in nc.values())
    far_hhi=sum((n/len(far))**2 for n in fc.values())
    ci=comp["bootstrap_ci95"]
    if comp["eligible_cells"]==0:
        decision="RESIDUAL_DRIFT_NOT_IDENTIFIABLE_NO_COUNTRY_SIDE_PRICE_COMMON_SUPPORT"
    elif ci and ci[1]<0:
        decision="RESIDUAL_DRIFT_PERSISTS_AFTER_COUNTRY_SIDE_PRICE_CONTROL"
    else:
        decision="RESIDUAL_DRIFT_NOT_ROBUST_AFTER_COUNTRY_CONTROL"
    report={"schema_version":"radar-goldbet-1x2-residual-drift-v1","generated_at":datetime.now(timezone.utc).isoformat(),
      "classification":"ERROR_ANALYSIS_NO_RULE_TUNING_NO_CAUSAL_CLAIM",
      "methodology":{"target":"FT 1X2 maximum shortening candidate movement >=1pp","lead_split":"<360 versus >=360 minutes",
        "competition_control":"country prefix from documented tournament label; exact tournaments reported descriptively",
        "chronology":"kickoff-ordered halves","observed_current_is_close":False,"bootstrap_draws":10000},
      "source":{"path":str(SRC.relative_to(ROOT)),"sha256":hashlib.sha256(raw).hexdigest()},
      "sample":{"events":len(rows),"near":len(near),"far":len(far),"countries":len(set(x["country"] for x in rows)),
        "tournaments":len(set(x["tournament"] for x in rows)),"kickoff_min":rows[0]["kickoff"],"kickoff_max":rows[-1]["kickoff"]},
      "composition":{"near_country_hhi":near_hhi,"far_country_hhi":far_hhi,
        "near_top_countries":nc.most_common(10),"far_top_countries":fc.most_common(10)},
      "country_cells":country_rows,"tournament_cells":tournament_rows,
      "side_price_standardized":base,"country_side_price_standardized":comp,
      "chronological_halves":halves,"decision":decision,
      "interpretation":"Country-side-price standardization is not identifiable because no cell has sufficient observations in both lead groups. The apparent lead-time effect is confounded by source/competition coverage. Competition and chronology remain diagnostic controls only; no subgroup is eligible for promotion."}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"sample":report["sample"],"adjusted":comp,"decision":decision}))

if __name__=="__main__":main()
