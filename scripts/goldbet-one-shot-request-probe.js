// Radar GoldBet — one-shot request/response probe for iOS Safari Shortcuts.
// Goal: inspect the ORIGINAL GoldBet API request triggered by switching tabs,
// without persisting hooks across Shortcut executions.
// Captures sport API URL/method/body and a short response prefix.
// Sensitive headers/body fields are redacted. No cookies are read.
(async () => {
  const logs = [];
  const SENSITIVE = /(authorization|cookie|token|session|jwt|password|secret|signature|api[-_]?key|fingerprint)/i;
  const clean = s => (s || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
  const redactText = s => String(s || '')
    .replace(/("(?:token|auth|authorization|session|cookie|jwt|password|secret|signature|apiKey|apikey|key)"\s*:\s*)"[^"]*"/gi, '$1"[REDACTED]"')
    .replace(/((?:token|auth|authorization|session|cookie|jwt|password|secret|signature|apikey|key)=)[^&\s]+/gi, '$1[REDACTED]');

  const oldOpen = XMLHttpRequest.prototype.open;
  const oldSend = XMLHttpRequest.prototype.send;
  const oldHeader = XMLHttpRequest.prototype.setRequestHeader;
  const oldFetch = window.fetch;

  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.__radar = {type:'XHR', method:String(method || 'GET'), url:String(url || ''), headers:[], body:'', status:null, response:''};
    return oldOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.setRequestHeader = function(k, v) {
    if (this.__radar && !SENSITIVE.test(String(k))) this.__radar.headers.push(`${k}: ${v}`);
    return oldHeader.call(this, k, v);
  };
  XMLHttpRequest.prototype.send = function(body) {
    const info = this.__radar;
    if (info && /\/api\/sport\//i.test(info.url)) {
      info.body = redactText(body).slice(0, 1800);
      logs.push(info);
      this.addEventListener('loadend', () => {
        try { info.status = this.status; } catch {}
        try {
          if (this.responseType === '' || this.responseType === 'text') {
            info.response = redactText(this.responseText).slice(0, 5000);
          }
        } catch {}
      }, {once:true});
    }
    return oldSend.call(this, body);
  };

  window.fetch = function(input, init={}) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (/\/api\/sport\//i.test(url)) {
      const info = {type:'FETCH', method:String(init.method || 'GET'), url:String(url), headers:[], body:redactText(init.body).slice(0,1800), status:null, response:''};
      try {
        const h = new Headers(init.headers || (input && input.headers) || {});
        for (const [k,v] of h.entries()) if (!SENSITIVE.test(k)) info.headers.push(`${k}: ${v}`);
      } catch {}
      logs.push(info);
      const p = oldFetch.apply(this, arguments);
      p.then(async r => {
        info.status = r.status;
        try { info.response = redactText(await r.clone().text()).slice(0,5000); } catch {}
      }).catch(()=>{});
      return p;
    }
    return oldFetch.apply(this, arguments);
  };

  function visible(el) {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
  }
  function clickExact(label) {
    const all = [...document.querySelectorAll('button,[role="button"],a,div,span')]
      .filter(visible)
      .filter(el => clean(el.innerText).toUpperCase() === label.toUpperCase());
    all.sort((a,b) => (a.getBoundingClientRect().width*a.getBoundingClientRect().height) - (b.getBoundingClientRect().width*b.getBoundingClientRect().height));
    if (!all.length) return false;
    all[0].click();
    return true;
  }

  // Trigger tab changes. React/Angular usually issue the HTTP call synchronously or on the next task.
  clickExact('EVENTI');
  await new Promise(r => setTimeout(r, 120));
  clickExact('GIOCATORI');
  await new Promise(r => setTimeout(r, 650));

  XMLHttpRequest.prototype.open = oldOpen;
  XMLHttpRequest.prototype.send = oldSend;
  XMLHttpRequest.prototype.setRequestHeader = oldHeader;
  window.fetch = oldFetch;

  const interesting = logs.filter(x => /pregame|getDetails|player|giocator|market|event/i.test(x.url));
  const use = interesting.length ? interesting : logs;
  const payload = use.slice(0,12).map((x,i) => ({
    n:i+1, type:x.type, method:x.method,
    url:(() => { try { const u=new URL(x.url,location.href); return u.pathname+u.search; } catch { return x.url; } })(),
    headers:x.headers,
    body:x.body || '', status:x.status,
    response:x.response || ''
  }));
  completion(JSON.stringify({title:document.title, url:location.href, captured:payload.length, requests:payload}, null, 2));
})();
