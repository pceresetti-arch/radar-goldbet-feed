"""Fast CURRENT wrapper for BetFlag residential player quotes.

The full collector dynamically discovers hundreds of player-like slots. That is useful
for catalog discovery, but it is too slow for the 5-minute CURRENT lane and can prevent
fresh snapshots from being published. This wrapper keeps the canonical static player
markets in the critical path; full discovery remains available through the original
collector and the dedicated combo/discovery workflows.
"""
import betflag_residential_collector as collector

_original_merge_targets = collector.merge_targets


def _fast_merge_targets(discovered):
    # CURRENT must be deterministic and finish well inside the scheduler window.
    # Query only the canonical static seeds here. Discovery/combos run separately.
    return _original_merge_targets([])


collector.merge_targets = _fast_merge_targets
collector.main()
