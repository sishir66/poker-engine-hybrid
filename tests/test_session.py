import random

from src.engine.agent import Fish, Grinder, QuantGrid, Whale
from src.engine.ledger import Ledger
from src.engine.session import run_session
from src.engine.table import Table
from tests.test_engine import make_real_engine
from tests.test_hand_runner import ScriptedAgent


# =============================================================================
# Group: reproducibility -- the reason global random/np.random get seeded
# =============================================================================

class TestReproducibility:
    def test_same_seed_reproduces_cards_and_outcomes(self):
        """
        Grinder vs Whale exercises BOTH global randomness sources at once:
        Grinder's decide() reads global random directly, Whale's decide()
        reads global random AND calls calculate_win_odds() (global
        np.random) on every decision. Two independent sessions at the same
        seed must match on cards dealt (hole/community), showdown outcome,
        and chip deltas for every hand -- not just the cards, which is the
        exact gap the Dealer-only-seeding design left open.
        """
        engine = make_real_engine()
        table1 = Table(["grinder", "whale"], small_blind=1, big_blind=2)
        table2 = Table(["grinder", "whale"], small_blind=1, big_blind=2)
        agents1 = {"grinder": Grinder(), "whale": Whale(engine)}
        agents2 = {"grinder": Grinder(), "whale": Whale(engine)}

        result1 = run_session(agents1, table1, engine, num_hands=10,
                               seed=777, return_hand_details=True)
        result2 = run_session(agents2, table2, engine, num_hands=10,
                               seed=777, return_hand_details=True)

        assert result1["totals"] == result2["totals"]
        assert len(result1["hands"]) == len(result2["hands"]) == 10
        for h1, h2 in zip(result1["hands"], result2["hands"]):
            assert h1["button"] == h2["button"]
            assert h1["hole"] == h2["hole"]
            assert h1["community"] == h2["community"]
            assert h1["went_to_showdown"] == h2["went_to_showdown"]
            assert h1["deltas"] == h2["deltas"]

    def test_different_seed_diverges(self):
        """Guards the test above from passing vacuously (e.g. if seeding
        were silently a no-op, both runs would still trivially "match" only
        if they happened to be identical by luck -- this proves the two
        seeds actually produce different play)."""
        engine = make_real_engine()
        table1 = Table(["grinder", "whale"], small_blind=1, big_blind=2)
        table2 = Table(["grinder", "whale"], small_blind=1, big_blind=2)
        agents1 = {"grinder": Grinder(), "whale": Whale(engine)}
        agents2 = {"grinder": Grinder(), "whale": Whale(engine)}

        result1 = run_session(agents1, table1, engine, num_hands=10,
                               seed=1, return_hand_details=True)
        result2 = run_session(agents2, table2, engine, num_hands=10,
                               seed=2, return_hand_details=True)

        hole1 = [h["hole"] for h in result1["hands"]]
        hole2 = [h["hole"] for h in result2["hands"]]
        assert hole1 != hole2


# =============================================================================
# Group: button rotation
# =============================================================================

class TestButtonRotation:
    def test_button_alternates_every_hand(self):
        """Both agents always fold -- heads-up preflop first-to-act is the
        button/SB (hand_runner.py first_to_act logic), so each hand is
        exactly one decide() call: the button folds, loses its 1-chip SB."""
        table = Table(["p1", "p2"], small_blind=1, big_blind=2)
        agents = {
            "p1": ScriptedAgent([("fold", 0), ("fold", 0)]),
            "p2": ScriptedAgent([("fold", 0), ("fold", 0)]),
        }
        engine = make_real_engine()

        result = run_session(agents, table, engine, num_hands=4,
                              seed=5, return_hand_details=True)

        buttons = [h["button"] for h in result["hands"]]
        assert buttons == ["p1", "p2", "p1", "p2"]
        for i, h in enumerate(result["hands"]):
            button = buttons[i]
            other = "p2" if button == "p1" else "p1"
            assert h["deltas"] == {button: -1, other: 1}
        assert table.button_seat == "p1"


# =============================================================================
# Group: totals / return-shape contract
# =============================================================================

class TestTotals:
    def test_totals_equal_summed_per_hand_deltas_and_are_zero_sum(self):
        table = Table(["fish", "grinder"], small_blind=1, big_blind=2)
        agents = {"fish": Fish(), "grinder": Grinder()}
        engine = make_real_engine()

        result = run_session(agents, table, engine, num_hands=200,
                              seed=42, return_hand_details=True)

        recomputed = {"fish": 0, "grinder": 0}
        for h in result["hands"]:
            for seat, delta in h["deltas"].items():
                recomputed[seat] += delta

        assert recomputed == result["totals"]
        assert sum(result["totals"].values()) == 0


class TestDefaultReturnShape:
    def test_default_return_omits_per_hand_data(self):
        table = Table(["fish", "grinder"], small_blind=1, big_blind=2)
        agents = {"fish": Fish(), "grinder": Grinder()}
        engine = make_real_engine()

        result = run_session(agents, table, engine, num_hands=5, seed=1)

        assert set(result) == {"totals", "num_hands"}
        assert result["num_hands"] == 5


# =============================================================================
# Group: ledger is optional side-channel instrumentation
# =============================================================================

class TestLedgerOptional:
    def test_ledger_is_optional_and_totals_do_not_depend_on_it(self):
        engine = make_real_engine()

        table_no_ledger = Table(["fish", "grinder"], small_blind=1, big_blind=2)
        agents_no_ledger = {"fish": Fish(), "grinder": Grinder()}
        result_no_ledger = run_session(agents_no_ledger, table_no_ledger, engine,
                                        num_hands=50, seed=99)

        table_ledger = Table(["fish", "grinder"], small_blind=1, big_blind=2)
        agents_ledger = {"fish": Fish(), "grinder": Grinder()}
        ledger = Ledger()
        result_with_ledger = run_session(agents_ledger, table_ledger, engine,
                                          num_hands=50, seed=99, ledger=ledger)

        assert result_no_ledger["totals"] == result_with_ledger["totals"]
        assert ledger.hands_played("fish") == 50
        assert ledger.hands_played("grinder") == 50


# =============================================================================
# Group: behavioral regression -- Grinder must actually beat Fish
# =============================================================================

class TestBehavioralEdge:
    def test_grinder_beats_fish_over_20000_hands(self):
        """
        Directional-edge test with demonstrated power (see plan/HANDOFF-3.md
        §3): a symmetric self-play sanity check would pass against a fully
        broken decide() (a fold/raise inversion applied identically to both
        sides still averages ~0). This asserts a real, signed edge instead:
        Grinder's bb_per_100 mean is positive with a 95% CI that excludes
        zero, and Fish's is negative.

        n=20000, not HANDOFF-3.md's cited 5000 -- re-derived this session,
        not carried forward. A 10-seed sweep at n=5000 found the MEAN
        positive in 10/10 seeds but the CI excluding zero in only 3/10 --
        HANDOFF-3.md's "5000 is the smallest n where CI excludes zero" was
        one seed's outcome from a throwaway script, not a property of the
        sample size. The same sweep found n=20000 reliable at 10/10 seeds
        (n=10000 was still only 5/10) -- though not uniformly comfortable:
        per-seed means at n=20000 ranged 12.02-37.74 BB/100 and one seed's
        CI lower bound sat at only 0.28, barely clearing zero (full 10-seed
        table: HANDOFF-4.md). seed=555 (37.74, one of the stronger seeds,
        NOT representative of the ~23.7 mean-of-means) is pinned here
        purely for reproducibility, the same way test_hand_runner.py's
        200-hand chip-conservation sweep pins seed=42 -- not because it's
        a typical draw. Runtime at n=20000: ~1.9s measured (not "well
        under a second" -- that estimate was for the superseded n=5000).
        """
        table = Table(["grinder", "fish"], small_blind=1, big_blind=2)
        agents = {"grinder": Grinder(), "fish": Fish()}
        engine = make_real_engine()
        ledger = Ledger()

        run_session(agents, table, engine, num_hands=20000, seed=555,
                    ledger=ledger)

        grinder_mean, grinder_ci = ledger.bb_per_100("grinder")
        fish_mean, fish_ci = ledger.bb_per_100("fish")

        assert grinder_mean > 0
        assert grinder_mean - grinder_ci > 0
        assert fish_mean < 0
