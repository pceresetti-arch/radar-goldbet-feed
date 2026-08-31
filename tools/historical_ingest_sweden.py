#!/usr/bin/env python3
import csv
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

SOURCE_PAGE = "https://www.football-data.co.uk/sweden.php"
OUT = Path("feed/historical/sweden")
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

def inspect_csv(raw):
    text=raw.decode("utf-8-sig", errors="replace")
    rows=list(csv.reader(StringIO(text)))
    header=rows[0] if rows else []
    return {"rows_including_header":len(rows),"data_rows":max(0,len(rows)-1),"columns":header}

def season_tokens(s):
    return sorted(set(re.findall(r"(?:19|20)\d{2}(?:[/_-](?:19|20)?\d{2})?", s or "")))

def main():
    generated=datetime.now(timezone.utc).isoformat()
    report={
      "schema_version":"radar-historical-sweden-source-discovery-v1",
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
                try: item["csv_profile"]=inspect_csv(raw)
                except Exception as e: item["csv_profile_error"]=repr(e)
            except Exception as e:
                item.update({"download_status":"FAILED","error":repr(e)})
            report["discovered_files"].append(item)
    except Exception as e:
        report["page_fetch"]={"status":"FAILED","error":repr(e)}
        report["errors"].append(repr(e))
    report["summary"]={
      "discovered_csv_count":len(report["discovered_files"]),
      "fetched_csv_count":sum(x.get("download_status")=="FETCHED" for x in report["discovered_files"]),
      "season_tokens_verified_from_source":sorted(set(t for x in report["discovered_files"] for t in x.get("season_tokens",[]))),
      "goldbet_same_book_open_close_eligible":False,
      "modeling_allowed_from_this_discovery_alone":False
    }
    (OUT/"source-discovery.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report["summary"],indent=2))
    if report["page_fetch"].get("status")=="FAILED": return 2
    return 0

if __name__=="__main__": sys.exit(main())
