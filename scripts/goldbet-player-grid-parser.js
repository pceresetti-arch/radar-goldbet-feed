// Radar GoldBet — one-shot player grid parser prototype
// Designed for GoldBet "Giocatori" / "Top Bet" pages.
// Reads only visible betting labels + odds from the rendered page.
// No cookies, credentials, tokens or account data are collected.

(() => {
  const clean = s => (s || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
  const oddRx = /^\d{1,2}[.,]\d{2}$/;
  const nameRx = /^[A-Za-zÀ-ÿ'’.-]+(?:\s+[A-Za-zÀ-ÿ'’.-]+)+$/;

  const marketWords = [
    'marc','marcatore','marc plus','marc o sost','marc 1t','marc 2t','primo','ultimo',
    'gol o assist','assist','ammon','tiri','tiri in porta','u/o tiri','quasi marc','mvp'
  ];
  const ignore = new Set([
    'si','sì','no','casa','ospite','eventi','evento','giocatori','supercombo','top bet',
    'speciali plus','speciali giocatori','sanzioni giocatori','combo marcatori','marcatori'
  ]);

  function visible(el) {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
  }
  function leafText(el) {
    if (!visible(el)) return '';
    const t = clean(el.innerText);
    if (!t || t.length > 120) return '';
    const childSame = [...el.children].some(c => clean(c.innerText) === t && visible(c));
    return childSame ? '' : t;
  }

  const els = [...document.querySelectorAll('body *')];
  const leaves = els.map(el => ({el, t: leafText(el)})).filter(x => x.t);

  const odds = leaves.filter(x => oddRx.test(x.t)).map(x => {
    const r=x.el.getBoundingClientRect();
    return {el:x.el, odd:x.t.replace(',','.'), x:r.left+r.width/2, y:r.top+r.height/2};
  });

  const labels = leaves.filter(x => {
    const l=x.t.toLowerCase();
    return marketWords.some(w => l.includes(w)) && !oddRx.test(x.t);
  }).map(x => {
    const r=x.el.getBoundingClientRect();
    return {text:x.t, x:r.left+r.width/2, y:r.top+r.height/2};
  });

  const names = leaves.filter(x => {
    const l=x.t.toLowerCase();
    if (ignore.has(l) || oddRx.test(x.t) || /\d/.test(x.t)) return false;
    if (!nameRx.test(x.t)) return false;
    if (marketWords.some(w => l.includes(w))) return false;
    return x.t.length <= 65;
  }).map(x => {
    const r=x.el.getBoundingClientRect();
    return {name:x.t, x:r.left+r.width/2, right:r.right, y:r.top+r.height/2};
  });

  function nearestName(o) {
    return names
      .filter(n => n.right < o.x && Math.abs(n.y-o.y) <= 42)
      .sort((a,b) => Math.abs(a.y-o.y)-Math.abs(b.y-o.y) || (o.x-a.right)-(o.x-b.right))[0];
  }
  function nearestMarket(o) {
    // Column header normally sits above the quote. Penalise labels far away horizontally.
    return labels
      .filter(m => m.y < o.y && o.y-m.y < 420)
      .map(m => ({...m, score: Math.abs(m.x-o.x)*2 + (o.y-m.y)}))
      .sort((a,b)=>a.score-b.score)[0];
  }

  const rows=[];
  const seen=new Set();
  for (const o of odds) {
    const n=nearestName(o); if (!n) continue;
    const m=nearestMarket(o);
    const row={player:n.name, market:m ? m.text : null, price:Number(o.odd), y:o.y};
    const k=`${row.player}|${row.market}|${row.price}`;
    if (!seen.has(k)) { seen.add(k); rows.push(row); }
  }

  rows.sort((a,b)=>a.y-b.y || a.player.localeCompare(b.player) || a.price-b.price);

  const result={
    capturedAt:new Date().toISOString(),
    title:document.title,
    url:location.href,
    visiblePlayerOdds:rows.length,
    selections:rows.map(({y,...r})=>r)
  };

  completion(JSON.stringify(result,null,2));
})();
