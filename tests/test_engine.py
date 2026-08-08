"""
Automated regression coverage converted from manual scratchpad verification.

Every assertion below traces to a specific prior commit/verification —
see PokerEngine_Blueprint.md for full rationale on each group. Nothing
here is a newly-invented "expected" value; each one was independently
re-derived against current source before being written as a test.

TODO: check_tilt()'s trigger logic (Blueprint §5.2) has no coverage.
Design exists but was never exercised with confirmed printed output
this session (unlike the to_dict/from_dict round-trip below, which
was). Queued as a separate task alongside the tilt-compounding bug
fix — do not add tests here without first generating real reference
output to test against.
"""

import sys
import types
import itertools
import pytest

# --- seaborn shim ----------------------------------------------------------
# simulation.py imports seaborn at module level but never calls anything on
# it; seaborn isn't installed in this venv and isn't listed in any
# requirements file. Test-only workaround — source code is untouched.
try:
    import seaborn  # noqa: F401
except ImportError:
    sys.modules['seaborn'] = types.ModuleType('seaborn')

from src.engine.preflop import chen_score
from src.engine.risk import calculate_kelly_fraction, clamp_to_bankroll
from src.engine.hand import Hand
from src.engine.agent import Agent, Fish, Grinder, QuantGrid, Whale
from src.engine.simulation import PokerEngine
from src.utils.card import Card


# =============================================================================
# Fixtures
# =============================================================================

class FakeEngine:
    """
    Duck-typed stand-in for PokerEngine. Returns a fixed, caller-supplied
    win_odds instead of running a real Monte Carlo simulation, so
    QuantGrid/Whale decision-tree tests can hit exact kelly_f boundaries
    deterministically instead of replaying noisy real simulation output.
    """
    def __init__(self, win_odds):
        self.win_odds = win_odds

    def calculate_win_odds(self, hole_cards, community_cards, num_opponents=1, simulations=1000):
        return self.win_odds


def make_real_engine():
    """
    Real PokerEngine, constructed WITHOUT calling __init__ (which crashes
    on a fresh clone — model files are gitignored). Same bypass technique
    already used and trusted in this project's prior verification scripts.
    Not a fix for that bug — just a test technique.
    """
    engine = PokerEngine.__new__(PokerEngine)
    engine.cache_odds = None
    engine.cache_cards = None
    return engine


def win_odds_for_kelly_f(target_kf, pot_size, cost_to_call):
    """
    Solve calculate_kelly_fraction's formula f* = (b*p - q) / b for p,
    given a target kelly_f and pot odds. Lets tests hit exact threshold
    boundaries (already-documented values like 0.05, 0.35, 0.03) without
    depending on noisy real Monte Carlo win_odds.
    """
    b = pot_size / cost_to_call
    # f = p - (1-p)/b  =>  p = (f + 1/b) / (1 + 1/b)
    return (target_kf + 1 / b) / (1 + 1 / b)


# =============================================================================
# Group 0 — Kelly fraction formula (risk.py::calculate_kelly_fraction)
# Source: Blueprint §4.7 documented formula
# =============================================================================

class TestKellyFraction:
    def test_zero_cost_returns_one(self):
        assert calculate_kelly_fraction(0.5, 200, 0) == 1.0

    def test_positive_edge_exact_value(self):
        # b=2, p=0.85, q=0.15 -> (2*0.85 - 0.15)/2 = 0.775
        result = calculate_kelly_fraction(0.85, 200, 100)
        assert result == pytest.approx(0.775)

    def test_negative_edge_clamped_to_zero(self):
        # b=1, p=0.2, q=0.8 -> (1*0.2 - 0.8)/1 = -0.6, clamped to 0
        result = calculate_kelly_fraction(0.2, 100, 100)
        assert result == 0

    def test_breakeven_boundary(self):
        # b=2: breakeven at p = 1/(1+b) = 1/3
        result = calculate_kelly_fraction(1 / 3, 200, 100)
        assert result == pytest.approx(0, abs=1e-9)


# =============================================================================
# Group 1 — Chen formula (preflop.py::chen_score)
# Source: Blueprint §4.2 reference values
# =============================================================================

class TestChenFormula:
    def test_AA(self):
        assert chen_score(Card(14, 0), Card(14, 1)) == 20

    def test_AKs(self):
        assert chen_score(Card(14, 0), Card(13, 0)) == 12

    def test_AKo(self):
        assert chen_score(Card(14, 0), Card(13, 1)) == 10

    def test_KQs(self):
        assert chen_score(Card(13, 0), Card(12, 0)) == 10

    def test_77(self):
        assert chen_score(Card(7, 0), Card(7, 1)) == 7

    def test_JTs(self):
        assert chen_score(Card(11, 0), Card(10, 0)) == 8

    def test_A9o(self):
        assert chen_score(Card(14, 0), Card(9, 1)) == 5

    def test_wheel_hands_tie_at_7(self):
        # Documented non-bug limitation: A2s-A5s all tie at 7 — Chen's
        # gap cap can't distinguish among them (§4.2).
        a2s = chen_score(Card(14, 0), Card(2, 0))
        a3s = chen_score(Card(14, 0), Card(3, 0))
        a4s = chen_score(Card(14, 0), Card(4, 0))
        a5s = chen_score(Card(14, 0), Card(5, 0))
        assert a2s == a3s == a4s == a5s == 7

    def test_95s(self):
        assert chen_score(Card(9, 0), Card(5, 0)) == 4

    def test_72o(self):
        assert chen_score(Card(7, 0), Card(2, 1)) == 0

    def test_AQs(self):
        assert chen_score(Card(14, 0), Card(12, 0)) == 11

    def test_AJs(self):
        assert chen_score(Card(14, 0), Card(11, 0)) == 10

    def test_ATs(self):
        assert chen_score(Card(14, 0), Card(10, 0)) == 8


# =============================================================================
# Group 2 — Fish legacy heuristic (Fish.score_hand())
# Source: Blueprint §4.3 reference values
# =============================================================================

class TestFishHeuristic:
    def _score(self, r1, s1, r2, s2):
        fish = Fish()
        return fish.score_hand([Card(r1, s1), Card(r2, s2)], [])

    def test_AA(self):
        assert self._score(14, 0, 14, 1) == 78

    def test_AKs(self):
        assert self._score(14, 0, 13, 0) == 63

    def test_AKo(self):
        assert self._score(14, 0, 13, 1) == 43

    def test_A9o(self):
        assert self._score(14, 0, 9, 1) == 14

    def test_A8o(self):
        assert self._score(14, 0, 8, 1) == 6

    def test_A5s(self):
        assert self._score(14, 0, 5, 0) == 34

    def test_77(self):
        assert self._score(7, 0, 7, 1) == 44

    def test_KQs(self):
        assert self._score(13, 0, 12, 0) == 58

    def test_77_beats_AKo(self):
        # Documented emergent quirk (§4.3): Fish's flat +30 pair bonus
        # makes 77 outscore AKo, a real deliberate bias, not a bug.
        assert self._score(7, 0, 7, 1) > self._score(14, 0, 13, 1)


# =============================================================================
# Group 3 — Hand evaluator (hand.py::Hand)
# Source: Blueprint §4.4 rank-value/key rules + §9 rule 5 (explicit
# edge-case verification requirement)
# =============================================================================

class TestHandEvaluator:
    def test_high_card_key(self):
        cards = [Card(2, 0), Card(5, 1), Card(9, 2), Card(11, 3), Card(14, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 0
        assert h.get_hand_key() == (0, 14, 11, 9, 5, 2)

    def test_pair_key_uses_explicit_sort_not_most_common(self):
        # Two pair-eligible ranks in the counter iteration order shouldn't
        # matter — pair_r must be the actual pair, kickers sorted desc.
        cards = [Card(5, 0), Card(5, 1), Card(2, 2), Card(9, 3), Card(11, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 1
        assert h.get_hand_key() == (1, 5, 11, 9, 2)

    def test_two_pair_key(self):
        cards = [Card(5, 0), Card(5, 1), Card(9, 2), Card(9, 3), Card(11, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 2
        assert h.get_hand_key() == (2, 9, 5, 11)

    def test_trips_key(self):
        cards = [Card(7, 0), Card(7, 1), Card(7, 2), Card(2, 3), Card(9, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 3
        assert h.get_hand_key() == (3, 7, 9, 2)

    def test_straight_key(self):
        cards = [Card(6, 0), Card(7, 1), Card(8, 2), Card(9, 3), Card(10, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 4
        assert h.get_hand_key() == (4, 10)

    def test_flush_key(self):
        cards = [Card(2, 0), Card(5, 0), Card(9, 0), Card(11, 0), Card(13, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 5
        assert h.get_hand_key() == (5, 13, 11, 9, 5, 2)

    def test_full_house_key(self):
        cards = [Card(7, 0), Card(7, 1), Card(7, 2), Card(4, 3), Card(4, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 6
        assert h.get_hand_key() == (6, 7, 4)

    def test_four_of_a_kind_key(self):
        cards = [Card(9, 0), Card(9, 1), Card(9, 2), Card(9, 3), Card(2, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 7
        assert h.get_hand_key() == (7, 9, 2)

    def test_straight_flush_key(self):
        cards = [Card(6, 0), Card(7, 0), Card(8, 0), Card(9, 0), Card(10, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 8
        assert h.get_hand_key() == (8, 10)

    def test_royal_flush_key(self):
        cards = [Card(10, 0), Card(11, 0), Card(12, 0), Card(13, 0), Card(14, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 9
        assert h.get_hand_key() == (9, 14)

    def test_wheel_straight_is_5_high_not_ace_high(self):
        cards = [Card(14, 0), Card(2, 1), Card(3, 2), Card(4, 3), Card(5, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 4
        assert h.get_hand_key() == (4, 5)

    def test_six_high_straight_beats_wheel(self):
        wheel = Hand([Card(14, 0), Card(2, 1), Card(3, 2), Card(4, 3), Card(5, 0)])
        six_high = Hand([Card(2, 0), Card(3, 1), Card(4, 2), Card(5, 3), Card(6, 0)])
        assert six_high.get_hand_key() > wheel.get_hand_key()

    def test_wheel_straight_flush_is_5_high(self):
        cards = [Card(14, 0), Card(2, 0), Card(3, 0), Card(4, 0), Card(5, 0)]
        h = Hand(cards)
        assert h.get_rank_value() == 8
        assert h.get_hand_key() == (8, 5)

    def test_three_pair_in_seven_cards_resolves_correct_two_pair(self):
        # §9 rule 5: explicit edge-case coverage requirement. Seven cards
        # containing three distinct pairs — the best 5-card two-pair must
        # use the TWO HIGHEST pairs, not an arbitrary/incorrect selection.
        # Uses the exact combination-search pattern get_best_hand() and
        # calculate_win_odds() use internally — no PokerEngine import needed.
        seven_cards = [
            Card(4, 0), Card(4, 1),
            Card(8, 0), Card(8, 1),
            Card(11, 0), Card(11, 1),
            Card(2, 2),
        ]
        best_key = max(
            Hand(list(combo)).get_hand_key()
            for combo in itertools.combinations(seven_cards, 5)
        )
        # Best two pair must be Jacks and Eights (the two highest pairs),
        # kicker = 4 (the highest remaining card).
        assert best_key == (2, 11, 8, 4)


# =============================================================================
# Group 4 — calculate_win_odds() Monte Carlo benchmarks (real engine)
# Source: Blueprint §10 row 1 / commit 3b4e339
# =============================================================================

class TestWinOddsBenchmarks:
    def test_AA_vs_random_heads_up(self):
        engine = make_real_engine()
        result = engine.calculate_win_odds(
            [Card(14, 0), Card(14, 1)], [], num_opponents=1, simulations=3000
        )
        assert 0.82 <= result <= 0.88

    def test_AKs_beats_KQs(self):
        engine = make_real_engine()
        aks = engine.calculate_win_odds(
            [Card(14, 0), Card(13, 0)], [], num_opponents=1, simulations=3000
        )
        engine.cache_odds = None
        engine.cache_cards = None
        kqs = engine.calculate_win_odds(
            [Card(13, 1), Card(12, 1)], [], num_opponents=1, simulations=3000
        )
        assert aks > kqs

    def test_forced_tie_exact_half(self):
        # Broadway board (A-K-Q-J-T, mixed suits, complete) — no villain
        # hole-card draw can beat or differ from the board's own straight:
        # flush is impossible (only 2 cards share a suit), a higher
        # straight is impossible (Ace is already the top), and any
        # pair/trips/two-pair villain forms is still weaker than a
        # straight. our_key == opp_key == (4, 14) every simulation, every
        # run, zero variance -> exact 0.5, not a tolerance band.
        engine = make_real_engine()
        result = engine.calculate_win_odds(
            [Card(2, 0), Card(3, 0)],
            [Card(14, 0), Card(13, 1), Card(12, 2), Card(11, 3), Card(10, 0)],
            num_opponents=1,
            simulations=500,
        )
        assert result == 0.5


# =============================================================================
# Group 5 — QuantGrid decision tree (via FakeEngine)
# Source: Blueprint §5.5 / commit 6c31c50
# =============================================================================

class TestQuantGridThresholds:
    def _decide(self, win_odds, pot_size, cost_to_call, min_raise=10, bankroll=1000):
        qg = QuantGrid(FakeEngine(win_odds))
        qg.score_hand([Card(14, 0), Card(14, 1)], [])
        return qg.decide(pot_size, cost_to_call, min_raise, bankroll)

    def test_folds_below_kelly_f_005(self):
        win_odds = win_odds_for_kelly_f(0.02, pot_size=200, cost_to_call=100)
        action, amount = self._decide(win_odds, 200, 100)
        assert action == "fold"
        assert amount == 0

    def test_call_weighted_tier_never_folds(self):
        win_odds = win_odds_for_kelly_f(0.20, pot_size=200, cost_to_call=100)
        actions = {self._decide(win_odds, 200, 100)[0] for _ in range(30)}
        assert "fold" not in actions
        assert actions == {"raise", "call"}

    def test_raise_weighted_tier_never_folds(self):
        win_odds = win_odds_for_kelly_f(0.60, pot_size=200, cost_to_call=100)
        actions = [self._decide(win_odds, 200, 100)[0] for _ in range(30)]
        assert "fold" not in actions
        assert actions.count("raise") > actions.count("call")

    def test_free_check_below_050_always_checks(self):
        action, amount = self._decide(0.30, 200, 0)
        assert action == "check"
        assert amount == 0

    def test_free_check_above_050_never_folds(self):
        actions = {self._decide(0.75, 200, 0)[0] for _ in range(30)}
        assert "fold" not in actions
        assert actions == {"raise", "check"}


# =============================================================================
# Group 6 — Whale decision tree (via FakeEngine)
# Source: Blueprint §5.6 / commit 3242717
# =============================================================================

class TestWhaleThresholds:
    def _decide(self, win_odds, pot_size, cost_to_call, min_raise=10, bankroll=1000):
        whale = Whale(FakeEngine(win_odds))
        whale.score_hand([Card(14, 0), Card(14, 1)], [])
        return whale.decide(pot_size, cost_to_call, min_raise, bankroll)

    def test_folds_below_kelly_f_003(self):
        win_odds = win_odds_for_kelly_f(0.01, pot_size=200, cost_to_call=100)
        action, amount = self._decide(win_odds, 200, 100)
        assert action == "fold"
        assert amount == 0

    def test_call_weighted_tier_never_folds(self):
        win_odds = win_odds_for_kelly_f(0.20, pot_size=200, cost_to_call=100)
        actions = {self._decide(win_odds, 200, 100)[0] for _ in range(30)}
        assert "fold" not in actions
        assert actions == {"raise", "call"}

    def test_raise_weighted_tier_never_folds(self):
        win_odds = win_odds_for_kelly_f(0.60, pot_size=200, cost_to_call=100)
        actions = [self._decide(win_odds, 200, 100)[0] for _ in range(30)]
        assert "fold" not in actions
        assert actions.count("raise") > actions.count("call")

    def test_free_check_sizes_as_pot_relative_overbet(self):
        # Documented Option-B design decision: free-check sizing is
        # pot_size * 1.5 * aggression, NOT bankroll * kelly_f * kelly_alpha
        # (risk.py hardcodes kelly_f=1.0 on this path, which combined with
        # alpha=1.0 would shove the whole stack every time).
        pot_size, bankroll = 200, 1000
        raises = [
            self._decide(0.90, pot_size, 0, bankroll=bankroll)
            for _ in range(30)
        ]
        raise_amounts = [amt for action, amt in raises if action == "raise"]
        assert raise_amounts, "expected at least one raise across 30 trials"
        expected = clamp_to_bankroll(int(pot_size * 1.5 * 1.2), bankroll)
        assert all(amt == expected for amt in raise_amounts)

    def test_folds_strict_subset_of_quantgrid(self):
        # Precise, non-flaky version of the earlier 10/27-vs-15/27 boundary
        # table: pick win_odds landing exactly in the gap between Whale's
        # floor (0.03) and QuantGrid's floor (0.05) -- QuantGrid must fold,
        # Whale must not, on identical inputs.
        pot_size, cost_to_call = 200, 100
        win_odds = win_odds_for_kelly_f(0.04, pot_size, cost_to_call)

        qg = QuantGrid(FakeEngine(win_odds))
        qg.score_hand([Card(7, 0), Card(2, 1)], [])
        qg_action, _ = qg.decide(pot_size, cost_to_call, 10, 1000)

        whale = Whale(FakeEngine(win_odds))
        whale.score_hand([Card(7, 0), Card(2, 1)], [])
        whale_action, _ = whale.decide(pot_size, cost_to_call, 10, 1000)

        assert qg_action == "fold"
        assert whale_action != "fold"


# =============================================================================
# Group 7 — Bankroll clamp (risk.py::clamp_to_bankroll + all four agents)
# Source: commit 9b44ff4 and Whale's stress sweep
# =============================================================================

class TestBankrollClamp:
    def test_clamp_basic_unchanged_when_under_bankroll(self):
        assert clamp_to_bankroll(150, 1000) == 150

    def test_clamp_overflow_case(self):
        assert clamp_to_bankroll(375, 100) == 100

    def test_clamp_min_raise_exceeds_bankroll(self):
        # Exact worked example from the Whale plan.
        assert clamp_to_bankroll(1500, 1000) == 1000

    def test_fish_sizing_respects_bankroll(self):
        fish = Fish()
        fish._cached_score = 25  # >= 20, forces the raise branch
        import random
        random.seed(1)
        action, amount = fish.decide(0, 500, 100, 10, 100)
        assert amount <= 100

    def test_grinder_sizing_respects_bankroll(self):
        grinder = Grinder()
        grinder._cached_score = 12  # >= 10, forces the raise branch
        import random
        random.seed(1)
        action, amount = grinder.decide(0, 500, 100, 10, 100)
        assert amount <= 100

    def test_quantgrid_sizing_respects_bankroll_at_min_raise_overflow(self):
        qg = QuantGrid(FakeEngine(0.85))
        qg.score_hand([Card(14, 0), Card(14, 1)], [])
        action, amount = qg.decide(200, 100, 1500, 1000)
        assert amount <= 1000

    @pytest.mark.parametrize("kelly_f", [0.1, 0.5, 0.9, 1.0])
    @pytest.mark.parametrize("aggression", [1.2, 1.8, 6.075])
    @pytest.mark.parametrize("min_raise", [10, 1500])
    def test_whale_stress_sweep_never_exceeds_bankroll(self, kelly_f, aggression, min_raise):
        bankroll = 1000
        band = 1.6  # ceiling of Whale's random band -- worst case
        raw = bankroll * kelly_f * 1.0 * aggression * band
        sized = clamp_to_bankroll(max(min_raise, int(raw)), bankroll)
        assert sized <= bankroll

    @pytest.mark.parametrize("pot", [50, 500, 5000, 50000])
    @pytest.mark.parametrize("aggression", [1.2, 1.8, 6.075])
    def test_whale_free_check_overbet_never_exceeds_bankroll(self, pot, aggression):
        bankroll = 1000
        raw = pot * 1.5 * aggression
        sized = clamp_to_bankroll(max(10, int(raw)), bankroll)
        assert sized <= bankroll


# =============================================================================
# Group 8 — Regression: clamp fix didn't change existing behavior
# Source: commit 9b44ff4 "Check A"
# =============================================================================

class TestRegressionUnchangedSizing:
    def test_fish_normal_play_unchanged(self):
        import random
        fish = Fish()
        fish._cached_score = 25
        random.seed(1)
        action, amount = fish.decide(0, 200, 100, 10, 1000)
        assert action == "raise"
        assert amount == 150

    def test_grinder_normal_play_unchanged(self):
        import random
        grinder = Grinder()
        grinder._cached_score = 12
        random.seed(1)
        action, amount = grinder.decide(0, 200, 100, 10, 1000)
        assert action == "raise"
        assert amount == 200

    def test_quantgrid_normal_play_sizing(self):
        # Fixed win_odds via FakeEngine -- fully deterministic, unlike the
        # original scratchpad script (which used two separate live Monte
        # Carlo calls and needed a rerun to avoid sampling-noise mismatch).
        # kelly_f here (~0.775) lands in the raise-weighted tier, which is
        # itself probabilistic (80% raise / 20% call) -- retry until the
        # raise branch fires; kelly_raise's VALUE doesn't change between
        # draws, only which action is returned, so this stays deterministic
        # about what's actually being asserted.
        win_odds = 0.85
        qg = QuantGrid(FakeEngine(win_odds))
        qg.score_hand([Card(14, 0), Card(14, 1)], [])
        expected_kf = calculate_kelly_fraction(win_odds, 200, 100)
        expected = clamp_to_bankroll(
            max(10, int(1000 * expected_kf * 0.25 * 1.0)), 1000
        )
        for _ in range(50):
            action, amount = qg.decide(200, 100, 10, 1000)
            if action == "raise":
                assert amount == expected
                return
        pytest.fail("never hit the raise branch in 50 draws")


# =============================================================================
# Group 9 — Agent serialization
# Source: Blueprint §5.1 documented Phase-0 fix
# =============================================================================

class TestAgentSerialization:
    def test_tilt_hands_remaining_round_trips_through_to_dict_from_dict(self):
        # Tested against the base Agent class, not a subclass: Fish/
        # Grinder/Whale override __init__ to take no constructor kwargs
        # (they hardcode name/kelly_alpha internally), so Fish.from_dict()
        # would raise TypeError -- a separate, undocumented subclass/
        # from_dict signature mismatch, flagged in the plan, not fixed
        # here. Agent's own __init__ does accept the kwargs from_dict()
        # passes, matching what the documented Phase-0 fix actually covers.
        agent = Agent(name="TestAgent", kelly_alpha=0.5)
        agent.is_tilted = True
        agent._tilt_hands_remaining = 7
        agent.aggression = 1.5
        restored = Agent.from_dict(agent.to_dict())
        assert restored._tilt_hands_remaining == 7
        assert restored.is_tilted is True
        assert restored.aggression == 1.5
