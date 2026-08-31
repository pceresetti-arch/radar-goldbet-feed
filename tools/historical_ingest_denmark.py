#!/usr/bin/env python3
import csv
from collections import Counter
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

SOURCE_PAGE = "https://www.football-data.co.uk/denmark.php"
OUT = Path("feed/historical/denmark")
OUT.mkdir(parents=True, exist_ok=True)

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self._href=None; self._text=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=="a":
            self._href=dict(attrs).get("href"); self._text=[]
    def handle_data(self, data):
        if self._href is not None: self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower()=="a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href=None; self._text=[]

def fetch(url):
    req=Request(url, headers={"User-Agent":"radar-historical-backtest/1.0 (+github-actions)"})
    with urlopen(req, timeout=30) as r:
        return r.read(), getattr(r, "status", 200), dict(r.headers)

def sha256(b): return hashlib.sha256(b).hexdigest()

def parse_match_date(value):
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime((value or "").strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None

def inspect_csv(raw):
    text=raw.decode("utf-8-sig", errors="replace")
    reader=csv.DictReader(StringIO(text))
    rows=list(reader)
    header=reader.fieldnames or []
    required=["Country","League","Season","Date","Home","Away","HG","AG","Res"]
    missing_required={k:sum(not str(r.get(k,"")).strip() for r in rows) for k in required}
    seasons=Counter(str(r.get("Season","")).strip() for r in rows if str(r.get("Season","")).strip())
    leagues=Counter(str(r.get("League","")).strip() for r in rows if str(r.get("League","")).strip())
    season_team_appearances = {}
    season_team_names = {}
    for season in sorted(seasons):
        team_counts = Counter()
        for r in rows:
            if str(r.get("Season","")).strip() == season:
                home=str(r.get("Home","")).strip(); away=str(r.get("Away","")).strip()
                if home: team_counts[home] += 1
                if away: team_counts[away] += 1
        season_team_appearances[season] = dict(sorted(team_counts.items()))
        season_team_names[season] = sorted(team_counts)
    parsed_dates=[parse_match_date(r.get("Date")) for r in rows]
    valid_dates=[x for x in parsed_dates if x]
    fixture_keys=[(r.get("Season","").strip(),r.get("Date","").strip(),r.get("Home","").strip(),r.get("Away","").strip()) for r in rows]
    duplicate_fixture_keys=len(fixture_keys)-len(set(fixture_keys))
    invalid_results=0
    for r in rows:
        try:
            hg=int(r.get("HG","")); ag=int(r.get("AG",""))
            expected="H" if hg>ag else ("A" if ag>hg else "D")
            if r.get("Res","").strip()!=expected: invalid_results+=1
        except (TypeError,ValueError):
            invalid_results+=1
    odds_columns=[x for x in header if x.endswith(("CH","CD","CA"))]
    odds_quality={}
    for col in odds_columns:
        valid=missing=invalid=0
        for r in rows:
            v=str(r.get(col,"")).strip()
            if not v: missing+=1; continue
            try:
                if float(v)>1: valid+=1
                else: invalid+=1
            except ValueError:
                invalid+=1
        odds_quality[col]={"valid":valid,"missing":missing,"invalid_or_nonpositive":invalid}
    return {
      "rows_including_header":len(rows)+1,
      "data_rows":len(rows),
      "columns":header,
      "season_counts":dict(sorted(seasons.items())),
      "league_counts":dict(sorted(leagues.items())),
      "season_team_counts":{s:len(v) for s,v in season_team_names.items()},
      "season_team_names":season_team_names,
      "season_team_appearances":season_team_appearances,
      "date_min":min(valid_dates) if valid_dates else None,
      "date_max":max(valid_dates) if valid_dates else None,
      "unparsed_date_rows":len(rows)-len(valid_dates),
      "missing_required":missing_required,
      "duplicate_fixture_keys":duplicate_fixture_keys,
      "invalid_or_inconsistent_result_rows":invalid_results,
      "odds_quality":odds_quality
    }

def season_tokens(s):
    return sorted(set(re.findall(r"(?:19|20)\d{2}(?:[/_-](?:19|20)?\d{2})?", s or "")))

def main():
    generated=datetime.now(timezone.utc).isoformat()
    report={
      "schema_version":"radar-historical-denmark-source-discovery-v1",
      "generated_at":generated,
      "source":"Football-Data.co.uk",
      "source_page":SOURCE_PAGE,
      "classification":"HISTORICAL_BASELINE_CANDIDATE_NOT_GOLDBET",
      "anti_hindsight_note":"This source may support historical results/market benchmark only. It must never be relabelled GoldBet or TRUE_OPEN_GOLDBET.",
      "page_fetch":{},"discovered_files":[],"errors":[]
    }
    try:
        html,status,headers=fetch(SOURCE_PAGE)
        report["page_fetch"]={"http_status":status,"sha256":sha256(html),"bytes":len(html)}
        p=LinkParser(); p.feed(html.decode("utf-8",errors="replace"))
        candidates=[]
        for href,text in p.links:
            u=urljoin(SOURCE_PAGE,href)
            if re.search(r"\.(csv|CSV)(?:$|\?)",u): candidates.append((u,text))
        seen=set()
        for u,text in candidates:
            if u in seen: continue
            seen.add(u)
            item={"url":u,"anchor_text":text,"season_tokens":season_tokens(u+" "+text),"download_status":"NOT_FETCHED"}
            try:
                raw,st,h=fetch(u)
                item.update({"download_status":"FETCHED","http_status":st,"sha256":sha256(raw),"bytes":len(raw)})
                try:
                    item["csv_profile"]=inspect_csv(raw)
                    if u.lower().endswith("/new/nor.csv"):
                        raw_path=OUT/"football-data-DNK.csv"
                        raw_path.write_bytes(raw)
                        item["persisted_snapshot"]=str(raw_path)
                except Exception as e: item["csv_profile_error"]=repr(e)
            except Exception as e:
                item.update({"download_status":"FAILED","error":repr(e)})
            report["discovered_files"].append(item)
    except Exception as e:
        report["page_fetch"]={"status":"FAILED","error":repr(e)}
        report["errors"].append(repr(e))
    season_values=sorted(set(
      s for x in report["discovered_files"]
      for s in x.get("csv_profile",{}).get("season_counts",{}).keys()
    ))
    primary=next((x for x in report["discovered_files"] if x.get("persisted_snapshot")),None)
    report["summary"]={
      "discovered_csv_count":len(report["discovered_files"]),
      "fetched_csv_count":sum(x.get("download_status")=="FETCHED" for x in report["discovered_files"]),
      "season_tokens_verified_from_source":season_values,
      "structural_baseline_candidate_rows":primary.get("csv_profile",{}).get("data_rows",0) if primary else 0,
      "goldbet_same_book_open_close_eligible":False,
      "modeling_allowed_from_this_discovery_alone":False
    }
    if primary:
        profile={
          "schema_version":"radar-historical-denmark-dataset-profile-v1",
          "generated_at":generated,
          "source":report["source"],
          "source_url":primary["url"],
          "source_sha256":primary["sha256"],
          "snapshot_path":primary["persisted_snapshot"],
          "source_class":"EXTERNAL_HISTORICAL_MARKET_BENCHMARK",
          "forbidden_classes":["GOLDBET_DIRECT","TRUE_OPEN_GOLDBET","PRIMARY_GOLDBET_MMS"],
          "profile":primary["csv_profile"],
          "eligibility":{
            "structural_rolling_baseline":"PENDING_QUALITY_GATE",
            "market_close_benchmark":"PENDING_PROVIDER_SEMANTICS_AND_QUALITY_GATE",
            "primary_goldbet_mms":False
          }
        }
        (OUT/"dataset-profile.json").write_text(json.dumps(profile,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (OUT/"source-discovery.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report["summary"],indent=2))
    if report["page_fetch"].get("status")=="FAILED": return 2
    return 0

if __name__=="__main__": sys.exit(main())
