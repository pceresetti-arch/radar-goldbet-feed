const clean = s => (s || "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
const quotaRx = /^\d{1,2}[.,]\d{2}$/;
const vietate = ["casa","ospite","giocatori","eventi","supercombo","combo marcatori","super combo marcatori","altre scommesse","marc","sì","si","sport","live","virtuali","home","logout","saldo totale"];
function visibile(el){const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=="none"&&s.visibility!=="hidden";}
function sembraNome(t){t=clean(t);const b=t.toLowerCase();if(!t||t.length>60)return false;if(vietate.some(v=>b===v||b.startsWith(v+" ")))return false;if(quotaRx.test(t)||/\d/.test(t))return false;return /^[A-Za-zÀ-ÿ'’.-]+(?:\s+[A-Za-zÀ-ÿ'’.-]+)+$/.test(t);}
const tutti=[...document.querySelectorAll("body *")].filter(visibile);
const quote=tutti.filter(el=>quotaRx.test(clean(el.innerText))).filter(el=>![...el.children].some(c=>quotaRx.test(clean(c.innerText))));
let risultati=[];
for(const qEl of quote){const quota=clean(qEl.innerText).replace(",",".");const qr=qEl.getBoundingClientRect();const qY=qr.top+qr.height/2;let candidati=[];for(const el of tutti){const nome=clean(el.innerText);if(!sembraNome(nome))continue;const r=el.getBoundingClientRect();const y=r.top+r.height/2;const dy=Math.abs(y-qY);if(dy>45||r.left>=qr.left)continue;candidati.push({nome,dy,dx:Math.abs(qr.left-r.right),area:r.width*r.height});}if(!candidati.length)continue;candidati.sort((a,b)=>a.dy-b.dy||a.dx-b.dx||a.area-b.area);risultati.push({nome:candidati[0].nome,quota,y:qY});}
risultati.sort((a,b)=>a.y-b.y);const visti=new Set();risultati=risultati.filter(r=>{const k=`${r.nome}|${r.quota}`;if(visti.has(k))return false;visti.add(k);return true;});
const pagina=document.body.innerText;let mercato="Mercato giocatore";if(/\bMarc Plus\b/i.test(pagina))mercato="Marc Plus";else if(/\bMarc 1T\b/i.test(pagina))mercato="Marcatore 1T";else if(/\bMarc 2T\b/i.test(pagina))mercato="Marcatore 2T";else if(/\bMarc\b/i.test(pagina))mercato="Marcatore";
completion(mercato+"\n\n"+(risultati.length?risultati.map(r=>`${r.nome} @${r.quota}`).join("\n"):"NESSUNA QUOTA TROVATA"));
