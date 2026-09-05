import assert from 'node:assert/strict';
import { chooseOperationalQuote, compareGoldBet } from '../src/quote-source-policy.mjs';

const now = new Date().toISOString();

{
  const result = chooseOperationalQuote([
    { source: 'GoldBet direct', price: 2.5, fetched_at: now },
    { source: 'BetFlag/AAMS direct', price: 2.48, fetched_at: now }
  ]);
  assert.equal(result.ok, true);
  assert.equal(result.operational_quote.source, 'BetFlag/AAMS direct');
  assert.equal(result.blocked_by_goldbet, false);
}

{
  const result = chooseOperationalQuote([
    { source: 'BetFlag/AAMS direct', price: 2.48, fetched_at: now }
  ]);
  assert.equal(result.ok, true);
  assert.equal(result.operational_quote.price, 2.48);
  assert.equal(result.blocked_by_goldbet, false);
}

{
  const result = chooseOperationalQuote([
    { source: 'GoldBet direct', price: 2.5, fetched_at: now }
  ]);
  assert.equal(result.ok, false);
  assert.equal(result.blocked_by_goldbet, false);
  assert.equal(result.reason, 'NO_OPERATIONAL_QUOTE_RECOVERED');
}

{
  const diffs = compareGoldBet(
    { source: 'BetFlag/AAMS direct', price: 2.48 },
    [{ source: 'GoldBet direct', price: 2.5 }]
  );
  assert.equal(diffs.length, 1);
  assert.equal(diffs[0].material, false);
}

console.log('quote-source-policy tests passed');
