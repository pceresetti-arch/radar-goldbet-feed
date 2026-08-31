#!/usr/bin/env python3
import hashlib,json,re,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

STATE=Path("feed/goldbet-diretta-movement-state.json")
OUT=Path("feed/historical/open-close/flashscore-outcome-endpoint-probe-v1.json")
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/139.0.0.0 Safari/537.36"
PREFIXES=("df_sui_1_","df_st_1_","df_scr_1_")

def fetch(url):
    h={"User-Agent":UA,"Accept":"*/*","Accept-Language":"it-IT,it;q=0.9,en;q=0.8","Referer":"https://www.diretta.it/","x-fsign":"SW9D1eZo"}
    try:
        with urlopen(Request(url,headers=h),timeout=30) as r:return r.status,r.read(2000000)
    except HTTPError as e:return e.code,e.read(200000)
    except Exception as e:return None,repr(e).encode()

def field_keys(text):
    return Counter(re.findall(r"(?:^|[~¬])([A-Z]{1,3})÷",text))

def main():
    state=json.loads(STATE.read_text(encoding="utf-8"))
    records=list((state.get("records") or {}).values())
    ids=[]; meta={}
    for r in records:
        fid=r.get("flashscore_event_id")
        if fid and fid not in ids:ids.append(fid);meta[fid]={"event":r.get("event"),"start_time":r.get("start_time")}
    probes=[]
    for fid in ids:
        for prefix in PREFIXES:
            url=f"https://www.flashscore.com/x/feed/{prefix}{fid}"
            status,body=fetch(url); text=body.decode("utf-8","replace")
            probes.append({
              "flashscore_event_id":fid,"event":meta[fid]["event"],"start_time":meta[fid]["start_time"],
              "endpoint":prefix,"url":url,"status":status,"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest(),
              "field_keys":dict(field_keys(text)),"snippet":text[:2500]
            })
            time.sleep(.15)
    report={"schema_version":"radar-flashscore-outcome-endpoint-probe-v1","generated_at":datetime.now(timezone.utc).isoformat(),"event_count":len(ids),"probes":probes,"decision":"SCHEMA_DISCOVERY_ONLY_NO_OUTCOME_JOIN"}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps([{"id":p["flashscore_event_id"],"endpoint":p["endpoint"],"status":p["status"],"bytes":p["bytes"],"keys":p["field_keys"]} for p in probes],indent=2))

if __name__=="__main__":main()
