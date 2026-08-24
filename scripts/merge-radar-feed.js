const fs = require('fs');
const stdPath = process.argv[2] || 'feed/latest.json';
const playerPath = process.argv[3] || 'feed/player-props.json';
const outPath = process.argv[4] || 'feed/radar-unified.json';

const std = fs.existsSync(stdPath) ? JSON.parse(fs.readFileSync(stdPath, 'utf8')) : {};
const pp = fs.existsSync(playerPath) ? JSON.parse(fs.readFileSync(playerPath, 'utf8')) : { rows: [] };
const result = {
  generated_at: new Date().toISOString(),
  bookmaker: 'goldbet.it',
  standard: {
    source_count: std.source_count ?? std.count ?? null,
    records_scanned: std.source_records_scanned ?? std.source_records ?? null,
    filtered_records: std.filtered_records ?? null,
    odds: std.odds || []
  },
  player_props: pp.rows || [],
  player_prop_count: (pp.rows || []).length
};
fs.writeFileSync(outPath, JSON.stringify(result, null, 2));
console.log(`wrote ${outPath} with ${(pp.rows || []).length} player props`);
