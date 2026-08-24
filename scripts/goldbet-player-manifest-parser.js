// Radar GoldBet — manifest-level player parser
// Goal: collect all player odds currently rendered on a GoldBet Giocatori/Marcatori page
// in one execution, grouping rows by the nearest visible event/match label.
// No cookies, credentials, account data or tokens are read.

(() => {
  const clean = s => (s || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
  const oddRx = /^\d{1,2}[.,]\d{2}$/;
  const nameRx = /^[A-Za-zÀ-ÿ'’.-]+(?:\s+[A-Za-zÀ-ÿ'’.-]+)+$/;
  const marketWords = [
    'marc','marcatore','marcatori','marc plus','marc o sost','marc 1t','marc 2t',
    'primo marcatore','1° marc','gol o assist','assist','tiri','tiri in porta',
    'u/o tiri','ammon','quasi marc','mvp'
  ];
  const ignore = new Set([
    'si','sì','no','casa','ospite','eventi','evento','giocatori','supercombo','top bet',
    'speciali plus','speciali giocatori','sanzioni giocatori','combo marcatori','marcatori',
    'home','sport','live','virtuali','logout','saldo totale'
  ]);

  function visible(el) {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
  }

  function leafText(el) {
    if (!visible(el)) return '';
    const t = clean(el.innerText);
    if (!t || t.length > 140) return '';
    const sameChild = [...el.children].some(c => visible(c) && clean(c.innerText) === t);
    return sameChild ? '' : t;
  }

  const nodes = [...document.querySelectorAll('body *')]
    .map(el => ({ el, text: leafText(el) }))
    .filter(x => x.text);

  const odds = nodes
    .filter(x => oddRx.test(x.text))
    .map(x => {
      const r = x.el.getBoundingClientRect();
      return { el: x.el, price: Number(x.text.replace(',', '.')), x: r.left + r.width / 2, y: r.top + r.height / 2 };
    })
    .filter(x => x.price >= 1.01 && x.price <= 100);

  const names = nodes
    .filter(x => {
      const l = x.text.toLowerCase();
      if (ignore.has(l) || oddRx.test(x.text) || /\d/.test(x.text)) return false;
      if (!nameRx.test(x.text)) return false;
      if (marketWords.some(w => l.includes(w))) return false;
      return x.text.length <= 70;
    })
    .map(x => {
      const r = x.el.getBoundingClientRect();
      return { player: x.text, left: r.left, right: r.right, y: r.top + r.height / 2 };
    });

  const markets = nodes
    .filter(x => {
      const l = x.text.toLowerCase();
      return marketWords.some(w => l.includes(w)) && !oddRx.test(x.text) && x.text.length <= 90;
    })
    .map(x => {
      const r = x.el.getBoundingClientRect();
      return { market: x.text, x: r.left + r.width / 2, y: r.top + r.height / 2 };
    });

  // Match/event labels: text containing a separator or two team-like chunks, not a player/market label.
  const eventLabels = nodes
    .filter(x => {
      const t = x.text;
      const l = t.toLowerCase();
      if (t.length < 5 || t.length > 120) return false;
      if (oddRx.test(t) || marketWords.some(w => l.includes(w))) return false;
      if (ignore.has(l)) return false;
      return /\s[-–]\s/.test(t) || /\svs\.?\s/i.test(t);
    })
    .map(x => {
      const r = x.el.getBoundingClientRect();
      return { event: x.text, y: r.top + r.height / 2 };
    });

  function nearestName(o) {
    return names
      .filter(n => n.right < o.x && Math.abs(n.y - o.y) <= 48)
      .map(n => ({ ...n, score: Math.abs(n.y - o.y) * 20 + Math.max(0, o.x - n.right) }))
      .sort((a, b) => a.score - b.score)[0] || null;
  }

  function nearestMarket(o) {
    return markets
      .filter(m => m.y <= o.y && o.y - m.y <= 520)
      .map(m => ({ ...m, score: (o.y - m.y) + Math.abs(o.x - m.x) * 1.5 }))
      .sort((a, b) => a.score - b.score)[0] || null;
  }

  function nearestEvent(o) {
    return eventLabels
      .filter(e => e.y <= o.y)
      .map(e => ({ ...e, d: o.y - e.y }))
      .sort((a, b) => a.d - b.d)[0]?.event || null;
  }

  const selections = [];
  const seen = new Set();
  for (const o of odds) {
    const n = nearestName(o);
    if (!n) continue;
    const m = nearestMarket(o);
    const event = nearestEvent(o);
    const row = {
      event,
      player: n.player,
      market: m ? m.market : null,
      price: o.price
    };
    const key = JSON.stringify(row);
    if (!seen.has(key)) {
      seen.add(key);
      selections.push(row);
    }
  }

  const grouped = {};
  for (const s of selections) {
    const k = s.event || 'EVENTO_CORRENTE';
    (grouped[k] ||= []).push({ player: s.player, market: s.market, price: s.price });
  }

  const result = {
    capturedAt: new Date().toISOString(),
    title: document.title,
    url: location.href,
    eventLabelsFound: eventLabels.map(x => x.event),
    totalSelections: selections.length,
    events: grouped
  };

  completion(JSON.stringify(result, null, 2));
})();
