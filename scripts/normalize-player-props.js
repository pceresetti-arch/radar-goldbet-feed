const fs = require('fs');

const input = process.argv[2];
const output = process.argv[3] || 'feed/player-props.json';
if (!input) throw new Error('Usage: node scripts/normalize-player-props.js <input.json> [output.json]');
const raw = JSON.parse(fs.readFileSync(input, 'utf8'));

const aliases = [
  [/marc(?:atore)?\s*1t|marc\s*1°\s*tempo/i, 'MARCATORE_1T'],
  [/marc(?:atore)?\s*2t|marc\s*2°\s*tempo/i, 'MARCATORE_2T'],
  [/primo\s*marc|1°\s*marc/i, 'PRIMO_MARCATORE'],
  [/gol\s*o\s*assist/i, 'GOL_O_ASSIST'],
  [/marc\s*o\s*sost/i, 'MARCATORE_O_SOSTITUTO'],
  [/marc\s*plus/i, 'MARCATORE_PLUS'],
  [/tiri\s*in\s*porta/i, 'TIRI_IN_PORTA'],
  [/u\/?o\s*tiri|tiri\s*totali|\btiri\b/i, 'TIRI_TOTALI'],
  [/\bassist\b/i, 'ASSIST'],
  [/marc(?:atore)?/i, 'MARCATORE_ANYTIME']
];

function marketCode(name = '') {
  for (const [rx, code] of aliases) if (rx.test(name)) return code;
  return String(name || 'ALTRO').toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_|_$/g, '');
}

const rows = [];
const events = raw.events || {};
for (const [event, selections] of Object.entries(events)) {
  for (const s of selections || []) {
    if (!s || !s.player || !s.price) continue;
    rows.push({
      captured_at: raw.capturedAt || raw.generated_at || new Date().toISOString(),
      bookmaker: 'goldbet.it',
      event,
      player: s.player,
      market_raw: s.market || null,
      market_code: marketCode(s.market || ''),
      line: s.line ?? null,
      side: s.side ?? null,
      price: Number(s.price)
    });
  }
}

fs.mkdirSync(require('path').dirname(output), { recursive: true });
fs.writeFileSync(output, JSON.stringify({ count: rows.length, rows }, null, 2));
console.log(`normalized ${rows.length} player-prop rows -> ${output}`);
