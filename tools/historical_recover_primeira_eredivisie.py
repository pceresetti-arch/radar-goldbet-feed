#!/usr/bin/env python3
"""Recover the frozen Primeira Liga + Eredivisie early-to-CLOSE diagnostic.

Football-Data's unprefixed Bet365 odds are treated as an observed early
pre-closing snapshot, never TRUE OPEN. Signal selection uses later CLOSE
movement, therefore early-price ROI is retrospective diagnostic evidence.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path("feed/historical/open-close/primeira-eredivisie-clean-source")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
FILES = [("2425", "P1"), ("2425", "N1"), ("2526", "P1"), ("2526", "N1")]
THRESHOLDS = [1.0, 2.0, 3.0]
AVG_CONFIRM_PP = 0.5
BOOTSTRAP_DRAWS = 4000
SEED = 20260815

PUBLISHED = {
    ("2425","1X2",1.0): {"roi_early":.0726,"clv":.1135,"roi_close":-.0391},
    ("2425","1X2",2.0): {"roi_early":.0875,"clv":.1366,"roi_close":-.0487},
    ("2425","1X2",3.0): {"roi_early":.1276,"clv":.1531,"roi_close":-.0221},
    ("2526","1X2",1.0): {"roi_early":-.0379,"clv":.1087,"roi_close":-.1282},
    ("2526","1X2",2.0): {"roi_early":.0067,"clv":.1316,"roi_close":-.1039},
    ("2526","1X2",3.0): {"roi_early":.0020,"clv":.1522,"roi_close":-.1188},
    ("2425","OU2.5",1.0): {"roi_early":-.0193,"clv":.0679,"roi_close":-.0831},
    ("2425","OU2.5",2.0): {"roi_early":.0331,"clv":.0835,"roi_close":-.0469},
    ("2425","OU2.5",3.0): {"roi_early":.0473,"clv":.1000,"roi_close":-.0485},
    ("2526","OU2.5",1.0): {"roi_early":.0514,"clv":.0664,"roi_close":-.0132},
    ("2526","OU2.5",2.0): {"roi_early":.0642,"clv":.0808,"roi_close":-.0142},
    ("2526","OU2.5",3.0): {"roi_early":.0920,"clv":.1002,"roi_close":-.0058},
}

def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent":"radar-historical-backtest/1.0 (+github-actions)"})
    with urlopen(req, timeout=40) as response:
        if getattr(response, "status", 200) != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read()

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def number(row, key):
    try:
        value=float(row.get(key,""))
        return value if value > 1.0 else None
    except (TypeError, ValueError):
        return None

def devig(odds):
    if any(x is None for x in odds):
        return None
    inv=[1.0/x for x in odds]
    total=sum(inv)
    return [x/total for x in inv]

def quantile(values, q):
    values=sorted(values)
    if not values: return None
    pos=(len(values)-1)*q
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi: return values[lo]
    return values[lo]*(hi-pos)+values[hi]*(pos-lo)

def block_bootstrap(rows, draws=BOOTSTRAP_DRAWS):
    blocks=defaultdict(lambda:[0.0,0])
    for row in rows:
        blocks[row["match_id"]][0]+=row["profit"]
        blocks[row["match_id"]][1]+=1
    values=list(blocks.values())
    rng=random.Random(SEED)
    sampled=[]
    for _ in range(draws):
        total_profit=total_n=0.0
        for _ in range(len(values)):
            profit,n=rng.choice(values)
            total_profit+=profit; total_n+=n
        sampled.append(total_profit/total_n)
    return [quantile(sampled,.025),quantile(sampled,.975)]

def signal_rows(source_rows):
    output=[]
    for src in source_rows:
        match_id="|".join([src["_league"],src["_season"],src.get("Date",""),src.get("HomeTeam",""),src.get("AwayTeam","")])
        markets=[
          ("1X2",["H","D","A"],["B365H","B365D","B365A"],["B365CH","B365CD","B365CA"],
           ["AvgH","AvgD","AvgA"],["AvgCH","AvgCD","AvgCA"]),
          ("OU2.5",["Over","Under"],["B365>2.5","B365<2.5"],["B365C>2.5","B365C<2.5"],
           ["Avg>2.5","Avg<2.5"],["AvgC>2.5","AvgC<2.5"])
        ]
        for market,selections,early_cols,close_cols,avg_early_cols,avg_close_cols in markets:
            early=[number(src,x) for x in early_cols]
            close=[number(src,x) for x in close_cols]
            avg_early=[number(src,x) for x in avg_early_cols]
            avg_close=[number(src,x) for x in avg_close_cols]
            p_early,p_close,p_avg_early,p_avg_close=map(devig,[early,close,avg_early,avg_close])
            if any(x is None for x in [p_early,p_close,p_avg_early,p_avg_close]):
                continue
            goals=None
            try: goals=int(src["FTHG"])+int(src["FTAG"])
            except (TypeError,ValueError): pass
            for i,selection in enumerate(selections):
                won=(src.get("FTR")==selection) if market=="1X2" else (
                    goals is not None and (goals>2.5 if selection=="Over" else goals<2.5))
                output.append({
                  "match_id":match_id,"season":src["_season"],"league":src["_league"],
                  "market":market,"selection":selection,
                  "early_odds":early[i],"close_odds":close[i],
                  "p_early":p_early[i],"p_close":p_close[i],
                  "move_pp":(p_close[i]-p_early[i])*100,
                  "avg_move_pp":(p_avg_close[i]-p_avg_early[i])*100,
                  "won":bool(won),"profit":early[i]-1 if won else -1.0,
                  "profit_close":close[i]-1 if won else -1.0
                })
    return output

def score(rows):
    if not rows: return {"n":0}
    return {
      "n":len(rows),"matches":len({x["match_id"] for x in rows}),
      "strike_rate":sum(x["won"] for x in rows)/len(rows),
      "roi_early":sum(x["profit"] for x in rows)/len(rows),
      "roi_early_ci95_block_bootstrap":block_bootstrap(rows),
      "clv_ratio":sum(x["early_odds"]/x["close_odds"]-1 for x in rows)/len(rows),
      "roi_close":sum(x["profit_close"] for x in rows)/len(rows)
    }

def main():
    source_rows=[]; source_manifest=[]
    for season,league in FILES:
        url=BASE.format(season=season,league=league)
        raw=fetch(url)
        path=OUT/f"{league}_{season}.csv"
        path.write_bytes(raw)
        reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig",errors="strict")))
        rows=list(reader)
        for row in rows:
            row["_season"]=season; row["_league"]=league
        source_rows.extend(rows)
        source_manifest.append({
          "season":season,"league":league,"url":url,"path":str(path),
          "bytes":len(raw),"sha256":sha256(raw),"rows":len(rows),
          "columns":reader.fieldnames
        })

    expected={("2425","P1"):306,("2425","N1"):306,("2526","P1"):306,("2526","N1"):306}
    for item in source_manifest:
        key=(item["season"],item["league"])
        if item["rows"] != expected[key]:
            raise RuntimeError(f"Unexpected fixture count {key}: {item['rows']} != {expected[key]}")

    signals=signal_rows(source_rows)
    fields=["match_id","season","league","market","selection","early_odds","close_odds",
            "p_early","p_close","move_pp","avg_move_pp","won","profit","profit_close"]
    with (OUT/"signals.csv").open("w",encoding="utf-8",newline="") as fh:
        writer=csv.DictWriter(fh,fieldnames=fields)
        writer.writeheader(); writer.writerows(signals)

    cells=[]
    for season in ["2425","2526"]:
        for market in ["1X2","OU2.5"]:
            for threshold in THRESHOLDS:
                selected=[x for x in signals if x["season"]==season and x["market"]==market
                          and x["move_pp"]>=threshold and x["avg_move_pp"]>=AVG_CONFIRM_PP]
                metrics=score(selected)
                published=PUBLISHED[(season,market,threshold)]
                key_map={"roi_early":"roi_early","clv_ratio":"clv","roi_close":"roi_close"}
                comparison={
                  metric_key:{"recomputed":metrics[metric_key],"published_rounded":published[published_key],
                              "absolute_difference":abs(metrics[metric_key]-published[published_key])}
                  for metric_key,published_key in key_map.items()
                }
                cells.append({"season":season,"market":market,"threshold_pp":threshold,
                              **metrics,"published_comparison":comparison})

    all_match_ids={x["match_id"] for x in signals}
    report={
      "schema_version":"radar-primeira-eredivisie-clean-source-recovery-v1",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "status":"CLEAN_SOURCE_FETCHED_AND_BOTH_MARKETS_REBUILT",
      "source_class":"FOOTBALL_DATA_OBSERVED_EARLY_TO_CLOSE_DIAGNOSTIC",
      "source_manifest":source_manifest,
      "sample":{"source_fixtures":len(source_rows),"unique_matches":len(all_match_ids),
                "signal_rows":len(signals),
                "by_market":{m:sum(x["market"]==m for x in signals) for m in ["1X2","OU2.5"]}},
      "rule":{"signal_bookmaker":"Bet365","thresholds_pp":THRESHOLDS,
              "market_average_confirmation_pp":AVG_CONFIRM_PP,
              "selection_time":"CLOSE","pinnacle_used":False},
      "cells":cells,
      "anti_hindsight":{"prices_reconstructed":False,"timestamps_invented":False,
          "early_is_true_open":False,"selection_uses_later_close":True,
          "early_roi_is_executable":False,
          "outcomes_used_only_for_evaluation":True},
      "decision":"DIAGNOSTIC_REPLICATION_ONLY_NO_THRESHOLD_OR_STAKE_PROMOTION"
    }
    (OUT/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"sample":report["sample"],"cells":len(cells)},indent=2))

if __name__=="__main__":
    main()
