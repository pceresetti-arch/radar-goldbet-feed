import json,pathlib,urllib.request
from datetime import datetime,timezone
BASE='https://sportservice.betflag.it/api/sport/pregame';AGG=1334500001
H={'Accept':'application/json,text/plain,*/*','x-api-version':'1.0','X-Auth-Token':'','X-Brand':'3','X-IdCanale':'0','Origin':'https://www.betflag.it','Referer':'https://www.betflag.it/','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36'}
def main():
 req=urllib.request.Request(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0',headers=H)
 with urllib.request.urlopen(req,timeout=30) as r: st=r.status; data=json.loads(r.read().decode())
 l=data.get('lmtW') if isinstance(data,dict) else None
 out={'generated_at':datetime.now(timezone.utc).isoformat(),'status':st,'lmtW_type':type(l).__name__,'lmtW':l,'tai':data.get('tai'),'ti':data.get('ti'),'tn':data.get('tn'),'di':data.get('di')}
 pathlib.Path('feed').mkdir(exist_ok=True)
 pathlib.Path('feed/betflag-lmtw-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'status':st,'lmtW_type':type(l).__name__,'lmtW_len':len(l) if hasattr(l,'__len__') else None,'lmtW_preview':str(l)[:3000]},ensure_ascii=False))
if __name__=='__main__':main()
