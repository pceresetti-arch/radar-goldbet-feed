# Radar GoldBet fast-track

1. Paginate OddsPapi GoldBet prematch records until a target event is found.
2. Persist full event markets into `feed/latest.json`.
3. Use direct GoldBet page extraction for player props when provider coverage is absent.
4. Normalize player markets into `{event, player, market, price}` rows.
5. Keep the collector independent of account cookies/credentials whenever possible.
