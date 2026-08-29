# BetFlag Residential Runner — one-time setup

## Why this is required
BetFlag/Akamai currently blocks datacenter-origin requests (GitHub-hosted runners and Cloudflare Worker egress) with HTTP 403 Access Denied. The operational collector therefore runs on a self-hosted Windows runner connected to a normal Italian residential/office network.

## One-time setup
1. On an always-on Windows PC connected to the normal network, open the repository:
   `pceresetti-arch/radar-goldbet-feed`
2. GitHub → Settings → Actions → Runners → New self-hosted runner → Windows x64.
3. Follow GitHub's displayed download/configuration commands.
4. During runner configuration add the custom label:
   `betflag-residential`
5. Install the runner as a Windows service when prompted so it starts automatically after reboot.

No Python installation is required permanently: the workflows use `actions/setup-python`.

## Workflows enabled
- `.github/workflows/betflag-residential-feed.yml`
  - runs every 5 minutes;
  - pulls BetFlag/AAMS player markets through the local network;
  - writes `feed/betflag-residential-current.json` plus history.

- `.github/workflows/betflag-residential-price-proof.yml`
  - triggers whenever `betflag-price-proof-request.json` changes;
  - refreshes the player feed;
  - resolves exact fixture + player + market + selection;
  - writes `feed/betflag-price-proof-latest.json`;
  - sets `price_gate_eligible=true` only for a unique healthy direct BetFlag quote.

The previous GitHub-hosted exact-price workflow is manual diagnostic only and no longer writes the operational proof file, preventing 403 results from overwriting a good residential proof.

## Acceptance test
After the runner is online:
1. Run `BetFlag residential feed` manually once.
2. Confirm `feed/betflag-residential-current.json` has `source_healthy: true` and `rows > 0`.
3. Update `betflag-price-proof-request.json` with a currently quoted player (for example a scorer market).
4. Confirm `feed/betflag-price-proof-latest.json` contains exactly one quote and `price_gate_eligible: true`.

Once these conditions pass, BetFlag player props are autonomous again and the Radar no longer needs manually supplied prices.
