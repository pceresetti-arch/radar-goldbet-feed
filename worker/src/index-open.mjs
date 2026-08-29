import baseWorker from './index.mjs';

const BETFLAG_AAMS_BASE='https://sportservice.betflag.it/api/sport/pregame';
const AAMS_AGG_TOURNAMENT=1334500001;
const OPEN_ODD_KEYS=['openingOdd','openOdd','opening_odd','open_odd','oo','initialOdd','initial_odd'];
const SOURCE_TIME_KEYS=['publishedAt','published_at','createdAt','created_at','openingAt','opening_at','openAt','open_at','timestamp','ts'];

const CORS_HEADERS={
  'Access-Control-Allow-Origin':'*',
  'Access-Control-Allow-Methods':'GET, OPTIONS',
  'Access-Control-Allow-Headers':'Authorization, Content-Type',
  'Access-Control-Max-Age':'86400'
};

function json(body,status=200){return new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',...CORS_HEADERS}})}
function normalized(v){return String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim()}
function headers(){return {'User-Agent':'Mozilla/5.0 RadarBetFlagStandard/8.0',Accept:'application/json,text/plain,*/*','x-api-version':'1.0','X-Auth-Token':'','X-Brand':'3','X-IdCanale':'0',Origin:'https://www.betflag.it',Referer:'https://www.betflag.it/'}}
function firstValue(nodes,keys){for(const n of nodes){if(!n||typeof n!=='object')continue;for(const k of keys){const v=n[k];if(v!==undefined&&v!==null&&v!=='')return [v,k]}}return [null,null]}
function family(market,selection){const m=normalized(market),s=normalized(selection);if(m.includes('1x2')||m.includes('esito finale')||m.includes('esito 1 x 2'))return '1X2';if(['under/over','over/under','under over','totale gol','totale goal','goal totali','gol totali','u/o','o/u'].some(x=>m.includes(x))||s.startsWith('over')||s.startsWith('under'))return 'TOTAL';return 'OTHER'}

function collect(data){
  const rows=[];
  function walk(node){
    if(Array.isArray(node)){node.forEach(walk);return}
    if(!node||typeof node!=='object')return;
    const eventName=String(node.en||'');
    const sportName=normalized(node.sn);
    if(node.ei!=null&&eventName&&node.mmkW!=null&&!eventName.startsWith('(')&&!sportName.startsWith('giocatori')){
      const mm=Array.isArray(node.mmkW)?node.mmkW:Object.values(node.mmkW||{});
      for(const market of mm){
        if(!market||typeof market!=='object')continue;
        const marketName=String(market.mn||'');
        const spreads=Array.isArray(market.spd)?market.spd.map((v,i)=>[i,v]):Object.entries(market.spd||{});
        for(const [spreadKey,spread] of spreads){
          if(!spread||typeof spread!=='object')continue;
          let line=spread.sl;
          if((line===undefined||line===null||line===''||line===0||line==='0'||line==='0.0')&&!['0','0.0'].includes(String(spreadKey)))line=spreadKey;
          for(const q of spread.asl||[]){
            if(!q||typeof q!=='object'||q.ov==null)continue;
            const [openingOdd,openingOddField]=firstValue([q,spread,market],OPEN_ODD_KEYS);
            const [sourceOpenAt,sourceTimeField]=firstValue([q,spread,market,node],SOURCE_TIME_KEYS);
            rows.push({
              event_id:node.ei,event:eventName,start_time:node.ed,league:node.td,match_market_id:node.mi,
              tournament_id:node.ti,authority_id:node.tai,market:marketName,line,selection:q.sn,odd:q.ov,
              selection_id:q.si,selection_type:q.sti,market_type:q.mti,market_id:q.mi,odds_id:q.oi,
              family:family(marketName,q.sn),betflag_opening_odd:openingOdd,betflag_opening_odd_field:openingOddField,
              betflag_source_open_at:sourceOpenAt,betflag_source_time_field:sourceTimeField
            });
          }
        }
      }
    }
    Object.values(node).forEach(walk);
  }
  walk(data);return rows;
}

async function standardOdds(url){
  const started=Date.now();
  const upstream=`${BETFLAG_AAMS_BASE}/getOverviewEventsAams/0/1/0/${AAMS_AGG_TOURNAMENT}/0/0/0?channelId=0`;
  const r=await fetch(upstream,{headers:headers()});
  const text=await r.text();let data;try{data=JSON.parse(text)}catch{data={raw:text.slice(0,2000)}}
  if(!r.ok)return json({generated_at:new Date().toISOString(),source_class:'BETFLAG_AAMS_DIRECT_STANDARD',source_healthy:false,upstream_status:r.status,error:'BetFlag standard upstream failed'},502);
  let rows=collect(data);
  const q=normalized(url.searchParams.get('q'));
  const fam=normalized(url.searchParams.get('family'));
  const eventId=normalized(url.searchParams.get('event_id'));
  const matchMarketId=normalized(url.searchParams.get('match_market_id'));
  if(q)rows=rows.filter(x=>[x.event,x.league,x.market,x.selection].map(normalized).join(' ').includes(q));
  if(fam)rows=rows.filter(x=>normalized(x.family)===fam);
  if(eventId)rows=rows.filter(x=>normalized(x.event_id)===eventId);
  if(matchMarketId)rows=rows.filter(x=>normalized(x.match_market_id)===matchMarketId);
  const limit=Math.max(1,Math.min(5000,Number.parseInt(url.searchParams.get('limit')||'5000',10)||5000));
  rows=rows.slice(0,limit);
  return json({generated_at:new Date().toISOString(),source_class:'BETFLAG_AAMS_DIRECT_STANDARD',source:'sportservice.betflag.it via radar-betflag-v7',source_healthy:true,upstream_status:r.status,elapsed_ms:Date.now()-started,true_open_definition:'REAL_BETFLAG_OPENING_PRICE_ONLY',row_count:rows.length,rows});
}

export default {
  async fetch(request,env,ctx){
    const url=new URL(request.url);
    const endpoint=url.pathname.replace(/^\/+|\/+$/g,'')||'health';
    if(request.method==='OPTIONS')return new Response(null,{status:204,headers:CORS_HEADERS});
    if(endpoint==='live/standard-odds'){
      if(request.method!=='GET')return json({error:'Method not allowed'},405);
      try{return await standardOdds(url)}catch(e){return json({generated_at:new Date().toISOString(),source_class:'BETFLAG_AAMS_DIRECT_STANDARD',source_healthy:false,error:e instanceof Error?e.message:String(e)},502)}
    }
    return baseWorker.fetch(request,env,ctx);
  }
};
