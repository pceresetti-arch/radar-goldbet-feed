// Radar GoldBet — manifestation-wide player parser prototype
// Goal: one Safari share from Marcatori > Giocatori > Top Bet.
// It extracts all player markets currently rendered and, within a strict time budget,
// attempts to cycle visible event tabs that update from already-cached DOM data.
// It does NOT read cookies, localStorage, credentials, account identifiers, or tokens.

(async () => {
  const START = performance.now();
  const BUDGET_MS = 1800;
  const clean = s => (s || '').replace(/\u00a0/g,' ').replace(/\s+/g,' ').trim();
  const oddRx = /^\d{1,2}[.,]\d{2}$/;
  const nameRx = /^[A-Za-zÀ-ÿ'’.-]+(?:\s+[A-Za-zÀ-ÿ'’.-]+)+$/;

  const marketWords = [
    'marc','marcatore','marc plus','marc o sost','marc 1t','marc 2t','1° marc','primo marcatore','ultimo marcatore',
    'gol o assist','assist','ammon','tiri','tiri in porta','u/o tiri','tiro in porta','tiro','mvp','sost'
  ];
  const ignore = new Set([
    'si','sì','no','casa','ospite','eventi','evento','giocatori','supercombo','top bet','tutte',
    'speciali plus','speciali giocatori','sanzioni giocatori','combo marcatori','marcatori','altre scommesse'
  ]);

  function visible(el){
    if (!el) return false;
    const r=el.getBoundingClientRect();
    const s=getComputedStyle(el);
    return r.width>0 && r.height>0 && s.display!=='none' && s.visibility!=='hidden';
  }

  function leafText(el){
    if(!visible(el)) return '';
    const t=clean(el.innerText);
    if(!t || t.length>140) return '';
    const childSame=[...el.children].some(c=>visible(c)&&clean(c.innerText)===t);
    return childSame?'':t;
  }

  function eventTabs(){
    const out=[]; const seen=new Set();
    for(const el of document.querySelectorAll('button,[role="tab"],[role="button"],a,li,div')){
      if(!visible(el)) continue;
      const t=clean(el.innerText);
      if(!t || t.length>35) continue;
      const aria=(el.getAttribute('aria-selected')||'').toLowerCase();
      const cls=String(el.className||'').toLowerCase();
      // Typical GoldBet manifestation tabs are compact match labels (e.g. ISL-POR) or short team-v-team labels.
      const tabLike = /^[A-Za-zÀ-ÿ0-9.'’ ]{2,16}\s*[-–]\s*[A-Za-zÀ-ÿ0-9.'’ ]{2,16}$/.test(t)
        || el.getAttribute('role')==='tab';
      if(!tabLike || seen.has(t)) continue;
      seen.add(t);
      const r=el.getBoundingClientRect();
      out.push({el,text:t,y:r.top,x:r.left,active:aria==='true'||/active|selected|attivo/.test(cls)});
    }
    // Tabs normally sit together in the upper half; keep the densest horizontal band.
    if(out.length<2) return out;
    let best=out, bestCount=0;
    for(const a of out){
      const band=out.filter(b=>Math.abs(b.y-a.y)<50);
      if(band.length>bestCount){best=band;bestCount=band.length;}
    }
    return best.sort((a,b)=>a.x-b.x);
  }

  function capture(activeEvent){
    const els=[...document.querySelectorAll('body *')];
    const leaves=els.map(el=>({el,t:leafText(el)})).filter(x=>x.t);

    const odds=leaves.filter(x=>oddRx.test(x.t)).map(x=>{
      const r=x.el.getBoundingClientRect();
      return {odd:Number(x.t.replace(',','.')),x:r.left+r.width/2,y:r.top+r.height/2};
    }).filter(o=>o.odd>=1.01 && o.odd<=100);

    const labels=leaves.filter(x=>{
      const l=x.t.toLowerCase();
      return marketWords.some(w=>l.includes(w))&&!oddRx.test(x.t);
    }).map(x=>{const r=x.el.getBoundingClientRect();return{text:x.t,x:r.left+r.width/2,y:r.top+r.height/2};});

    const names=leaves.filter(x=>{
      const l=x.t.toLowerCase();
      if(ignore.has(l)||oddRx.test(x.t)||/\d/.test(x.t)||x.t.length>65) return false;
      if(!nameRx.test(x.t)||marketWords.some(w=>l.includes(w))) return false;
      return true;
    }).map(x=>{const r=x.el.getBoundingClientRect();return{name:x.t,right:r.right,x:r.left+r.width/2,y:r.top+r.height/2};});

    const nearestName=o=>names
      .filter(n=>n.right<o.x&&Math.abs(n.y-o.y)<=46)
      .sort((a,b)=>Math.abs(a.y-o.y)-Math.abs(b.y-o.y)||(o.x-a.right)-(o.x-b.right))[0];

    const nearestMarket=o=>labels
      .filter(m=>m.y<o.y&&o.y-m.y<520)
      .map(m=>({...m,score:Math.abs(m.x-o.x)*1.7+(o.y-m.y)}))
      .sort((a,b)=>a.score-b.score)[0];

    const rows=[]; const seen=new Set();
    for(const o of odds){
      const n=nearestName(o); if(!n) continue;
      const m=nearestMarket(o);
      const row={event:activeEvent||null,player:n.name,market:m?m.text:null,price:o.odd};
      const k=`${row.event}|${row.player}|${row.market}|${row.price}`;
      if(!seen.has(k)){seen.add(k);rows.push(row);}
    }
    return rows;
  }

  const tabs=eventTabs();
  const results=[]; const captured=new Set();

  function addRows(rows){
    for(const r of rows){
      const k=JSON.stringify(r);
      if(!captured.has(k)){captured.add(k);results.push(r);}
    }
  }

  const initialActive=(tabs.find(t=>t.active)||tabs[0])?.text || null;
  addRows(capture(initialActive));

  // Fast cycle only. If a tab requires a slow network fetch, skip it rather than timing out Shortcuts.
  for(const tab of tabs){
    if(performance.now()-START>BUDGET_MS) break;
    if(tab.text===initialActive) continue;
    try{
      tab.el.click();
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      addRows(capture(tab.text));
    }catch{}
  }

  const output={
    capturedAt:new Date().toISOString(),
    title:document.title,
    url:location.href,
    detectedEventTabs:tabs.map(t=>t.text),
    activeEventAtStart:initialActive,
    selections:results,
    elapsedMs:Math.round(performance.now()-START),
    note:'Tabs requiring a network reload may need a separate strategy; cached/rendered tabs are captured in this single run.'
  };

  completion(JSON.stringify(output,null,2));
})();
