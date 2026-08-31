#!/usr/bin/env python3
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("feed/diretta-goldbet-true-open-index.json")
OUT = Path("feed/historical/open-close/goldbet-true-open-schema-audit-v1.json")
TOKENS = ("open","close","closing","current","kickoff","start","timestamp","observed","outcome","result","score","event","fixture","bookmaker","market","selection","price","odd")

def norm_path(parts):
    return ".".join("[]" if isinstance(p,int) else str(p) for p in parts)

def walk(value, parts, depth, path_counts, type_counts, examples):
    path=norm_path(parts)
    path_counts[path]+=1
    type_counts[(path,type(value).__name__)]+=1
    if not isinstance(value,(dict,list)) and len(examples[path])<3:
        examples[path].append(value)
    if depth>=12:
        return
    if isinstance(value,dict):
        for k,v in value.items():
            walk(v,parts+[k],depth+1,path_counts,type_counts,examples)
    elif isinstance(value,list):
        for i,v in enumerate(value):
            walk(v,parts+[i],depth+1,path_counts,type_counts,examples)

def shape(value, depth=0):
    if depth>=4:
        return type(value).__name__
    if isinstance(value,dict):
        return {k:shape(v,depth+1) for k,v in list(value.items())[:40]}
    if isinstance(value,list):
        return {"type":"list","length":len(value),"first":shape(value[0],depth+1) if value else None}
    return type(value).__name__

def event_container(data):
    if isinstance(data,dict):
        for key in ("events","fixtures","matches","items","data"):
            value=data.get(key)
            if isinstance(value,(dict,list)):
                return key,value
    return None,None

def main():
    raw=SOURCE.read_bytes()
    data=json.loads(raw)
    path_counts=Counter()
    type_counts=Counter()
    examples=defaultdict(list)
    walk(data,[],0,path_counts,type_counts,examples)
    key,container=event_container(data)
    if isinstance(container,list):
        event_count=len(container)
        sample=container[0] if container else None
    elif isinstance(container,dict):
        event_count=len(container)
        sample=next(iter(container.values()),None)
    else:
        event_count=None
        sample=None
    relevant=[]
    for path,count in path_counts.most_common():
        low=path.lower()
        if any(t in low for t in TOKENS):
            relevant.append({
                "path":path,
                "count":count,
                "types":sorted({typ for (p,typ),n in type_counts.items() if p==path}),
                "examples":examples[path],
            })
    audit={
        "schema_version":"radar-goldbet-true-open-schema-audit-v1",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "source":str(SOURCE),
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "source_bytes":len(raw),
        "root_type":type(data).__name__,
        "root_keys":list(data.keys()) if isinstance(data,dict) else None,
        "detected_event_container":key,
        "detected_event_count":event_count,
        "structural_shape":shape(data),
        "sample_event_shape":shape(sample),
        "relevant_field_paths":relevant[:500],
        "method":{
            "read_only":True,
            "no_price_reconstruction":True,
            "no_close_inference":True,
            "no_outcome_inference":True,
            "purpose":"Discover exact persisted schema before any OPEN-to-close-to-outcome join."
        }
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(audit,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"bytes":len(raw),"root_keys":audit["root_keys"],"event_container":key,"event_count":event_count,"relevant_paths":len(relevant)},indent=2))

if __name__=="__main__":
    main()
