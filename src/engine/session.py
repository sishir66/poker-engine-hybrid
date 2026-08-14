import random

import numpy as np

from src.engine.dealer import Dealer
from src.engine.hand_runner import play_hand


def run_session(agents, table, engine, num_hands, seed=None, ledger=None,
                 return_hand_details=False):
    """
    Plays num_hands in sequence: one shared rng stream feeding a fresh
    Dealer per hand, table.rotate_button() between hands, a session-wide
    sum(deltas)==0 check independent of play_hand()'s own per-hand asserts.
    Heads-up only, matching play_hand()'s own scope (Stage 3, no side pots).

    Seeding: `seed` seeds the GLOBAL random and np.random modules, not just
    the Dealer's rng. All four agents' decide() dice rolls read global
    random (agent.py), and calculate_win_odds()'s Monte Carlo reads global
    np.random (simulation.py) -- neither accepts an injectable rng. Seeding
    only an injected Dealer rng (the original design) does NOT make a
    session reproducible: two same-seed runs would deal identical cards but
    diverge in outcome, because the agents' own randomness carries leftover
    state from whatever ran before. This mutates global interpreter state;
    accepted as the only lever available without changing agent.py/
    simulation.py, which is out of scope for this stage.

    The Dealer's own rng is deliberately NOT random.Random(seed) directly --
    that would start the deck shuffle from the exact same MT19937 state the
    freshly-seeded global generator starts from, correlating the cards
    dealt with the first decisions made on them. Drawing the Dealer's seed
    from the freshly-seeded global instead gives a disjoint stream while
    staying fully reproducible (same `seed` -> same getrandbits(64) draw ->
    same deck every run).

    return_hand_details=False (default): returns only {"totals", "num_hands"}
    -- O(1) memory regardless of num_hands, for large production runs.
    return_hand_details=True: also returns "hands", a list of play_hand()'s
    own result dicts (unmodified) plus that hand's button seat -- for small-N
    debugging and reproducibility verification, where the memory cost is
    irrelevant.

    ledger is optional side-channel instrumentation, passed straight through
    to play_hand() (which already no-ops when ledger is None). totals is
    computed by summing play_hand()'s own deltas, independent of ledger --
    run_session()'s basic output never depends on a Ledger existing.
    """
    assert len(table.seats) == 2, "Stage 3 is heads-up only -- N>2 needs side-pot logic"

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    dealer_rng = random.Random(random.getrandbits(64) if seed is not None else None)

    totals = {s: 0 for s in table.seats}
    hands = [] if return_hand_details else None

    for _ in range(num_hands):
        button = table.button_seat  # read before this hand's rotate_button()
        result = play_hand(agents, table, engine,
                            dealer=Dealer(rng=dealer_rng), ledger=ledger)
        for seat, delta in result["deltas"].items():
            totals[seat] += delta
        if return_hand_details:
            hands.append({**result, "button": button})
        table.rotate_button()

    assert sum(totals.values()) == 0, "session-wide chip conservation violated"

    out = {"totals": totals, "num_hands": num_hands}
    if return_hand_details:
        out["hands"] = hands
    return out
