import itertools
import random
import pytest

from src.engine.agent import Agent, Fish, Grinder
from src.engine.hand import Hand
from src.engine.pot import PotManager
from src.engine.table import Table
from src.engine.dealer import Dealer
from src.engine.showdown import resolve_showdown
from src.engine.hand_runner import run_betting_round, play_hand
from src.utils.card import Card
from tests.test_engine import make_real_engine


# =============================================================================
# Fixtures
# =============================================================================

class ScriptedAgent(Agent):
    """
    Real Agent subclass (inherits the actual check_tilt()) with score_hand()
    a no-op and decide() popping a pre-programmed (action, size) queue.
    `size` is only read for "raise" -- "call"/"check"/"fold" recompute their
    own effective amount from live pot state, so a placeholder there is fine.

    Also records every check_tilt() call as (hand_profit, bankroll) so
    tests can assert on exactly what play_hand() passed in.
    """
    def __init__(self, script):
        super().__init__(name="Scripted", kelly_alpha=0.5)
        self._script = list(script)
        self.tilt_calls = []

    def score_hand(self, hole_cards, community_cards):
        pass

    def decide(self, pot_size, cost_to_call, min_raise, bankroll):
        return self._script.pop(0)

    def check_tilt(self, hand_profit, bankroll):
        self.tilt_calls.append((hand_profit, bankroll))
        super().check_tilt(hand_profit, bankroll)


class OrderTrackingAgent(ScriptedAgent):
    """ScriptedAgent that also appends its tag to a shared log on every
    decide() call, so a test can assert WHO acted in what order."""
    def __init__(self, script, tag, log):
        super().__init__(script)
        self.tag = tag
        self.log = log

    def decide(self, pot_size, cost_to_call, min_raise, bankroll):
        self.log.append(self.tag)
        return super().decide(pot_size, cost_to_call, min_raise, bankroll)


class CountingEngine:
    """Delegates to a real engine's get_best_hand(), counting calls -- used
    to prove an early fold-exit never touches Showdown at all."""
    def __init__(self, real_engine):
        self._real = real_engine
        self.get_best_hand_calls = 0

    def get_best_hand(self, hole_cards, community_cards):
        self.get_best_hand_calls += 1
        return self._real.get_best_hand(hole_cards, community_cards)


def raw_best(hole, board):
    """Independent recompute -- no engine, no cache -- ground truth for
    showdown cache-invariant tests."""
    return max(Hand(list(c)).get_hand_key() for c in itertools.combinations(hole + board, 5))


# =============================================================================
# Group: early exit on fold (requirement 6)
# =============================================================================

class TestEarlyExitOnFold:
    def test_fold_preflop_sole_survivor_takes_pot_no_showdown(self):
        table = Table(["p1", "p2"], small_blind=1, big_blind=2)
        agents = {"p1": ScriptedAgent([("fold", 0)]), "p2": ScriptedAgent([])}
        engine = CountingEngine(make_real_engine())
        result = play_hand(agents, table, engine, dealer=Dealer(rng=random.Random(1)))

        assert result["went_to_showdown"] is False
        assert result["deltas"] == {"p1": -1, "p2": 1}
        assert result["awards"] == {"p2": 3}
        assert engine.get_best_hand_calls == 0


# =============================================================================
# Group: chip conservation across arbitrary real play (requirement 7)
# =============================================================================

class TestChipConservationSweep:
    def test_200_hands_of_real_agents_always_balance(self):
        table = Table(["fish", "grinder"], small_blind=1, big_blind=2)
        agents = {"fish": Fish(), "grinder": Grinder()}
        engine = make_real_engine()
        ledger_rng = random.Random(42)

        for _ in range(200):
            result = play_hand(agents, table, engine, dealer=Dealer(rng=ledger_rng))
            assert sum(result["deltas"].values()) == 0
            assert sum(result["awards"].values()) == result["pot_total"]


# =============================================================================
# Group: raise-TO wiring into PotManager (requirement 1)
# =============================================================================

class TestRaiseToWiring:
    def test_raise_size_is_converted_to_a_cumulative_total_not_an_increment(self):
        table = Table(["p1", "p2"], small_blind=1, big_blind=2)
        pot = PotManager()
        pot.set_contribution("p1", 1)
        pot.set_contribution("p2", 2)
        live = {"p1", "p2"}
        hole = {"p1": [], "p2": []}
        agents = {
            "p1": ScriptedAgent([("raise", 20)]),   # new_total = 1 + 20 = 21
            "p2": ScriptedAgent([("call", 0)]),      # call recomputes its own cost
        }
        run_betting_round(agents, hole, pot, table, live, "p1", [], 100_000, 2)

        assert pot.contribution("p1") == 21   # the TOTAL, not the raw script value 20
        assert pot.contribution("p2") == 21
        assert pot.highest_contribution() == 21


# =============================================================================
# Group: all-in clamp before set_contribution (requirement 2)
# =============================================================================

class TestAllInClamp:
    def test_over_raise_clamps_to_exactly_the_stack_no_guard_trip(self):
        table = Table(["p1", "p2"], small_blind=1, big_blind=2)
        pot = PotManager()
        pot.set_contribution("p1", 1)
        pot.set_contribution("p2", 2)
        live = {"p1", "p2"}
        hole = {"p1": [], "p2": []}
        starting_stack = 100
        agents = {
            "p1": ScriptedAgent([("raise", 5000)]),  # far more than stack_left=99
            "p2": ScriptedAgent([("call", 0)]),
        }
        run_betting_round(agents, hole, pot, table, live, "p1", [], starting_stack, 2)

        assert pot.contribution("p1") == starting_stack
        assert pot.contribution("p2") == starting_stack
        # no-side-pot MVP proof: both stacks land exactly equal, never over.


# =============================================================================
# Group: check_tilt() bankroll timing (requirement 4)
# =============================================================================

class TestTiltBankrollTiming:
    def test_start_of_hand_bankroll_avoids_the_post_settlement_mistrigger(self):
        starting_stack = 100
        profit = -40

        correct = Agent(name="A", kelly_alpha=0.5)
        correct.check_tilt(profit, starting_stack)
        assert correct.is_tilted is False  # 40/100 = 0.40, below the 0.5 trigger

        # The trap: feeding the POST-settlement stack (60, not the 100 the
        # player actually had at risk) inflates the ratio and mistriggers
        # on the exact same hand.
        buggy = Agent(name="A", kelly_alpha=0.5)
        post_settlement_stack = starting_stack + profit  # 60
        buggy.check_tilt(profit, post_settlement_stack)
        assert buggy.is_tilted is True  # 40/60 ~= 0.667 -- wrong denominator

    def test_play_hand_calls_check_tilt_once_per_seat_including_the_folder(self):
        table = Table(["p1", "p2"], small_blind=1, big_blind=2)
        agents = {"p1": ScriptedAgent([("fold", 0)]), "p2": ScriptedAgent([])}
        engine = make_real_engine()
        play_hand(agents, table, engine, dealer=Dealer(rng=random.Random(2)))

        starting_stack = 100 * table.big_blind
        assert agents["p1"].tilt_calls == [(-1, starting_stack)]  # folder: -blind posted
        assert agents["p2"].tilt_calls == [(1, starting_stack)]


# =============================================================================
# Group: showdown cache_sig invariant (requirement 5)
# =============================================================================

class TestShowdownCacheInvariant:
    BOARD = [Card(9, 0), Card(9, 1), Card(4, 2), Card(7, 3), Card(2, 0)]
    P1_HOLE = [Card(14, 0), Card(13, 0)]  # pair of 9s
    P2_HOLE = [Card(9, 2), Card(3, 1)]    # trip 9s -- strictly better

    def test_two_contenders_never_collide_via_stale_cache_sig(self):
        engine = make_real_engine()
        expected_p1 = raw_best(self.P1_HOLE, self.BOARD)
        expected_p2 = raw_best(self.P2_HOLE, self.BOARD)
        assert expected_p2 > expected_p1

        pot = PotManager()
        pot.set_contribution("p1", 50)
        pot.set_contribution("p2", 50)
        awards = resolve_showdown(engine, [("p1", self.P1_HOLE), ("p2", self.P2_HOLE)],
                                   self.BOARD, pot, "p1", ["p1", "p2"])
        assert awards == {"p2": 100}
        # re-evaluate p1 AFTER p2 shared the same engine instance -- must
        # not come back as p2's cached key.
        assert engine.get_best_hand(self.P1_HOLE, self.BOARD) == expected_p1

    def test_evaluation_order_does_not_change_the_winner(self):
        engine = make_real_engine()
        pot = PotManager()
        pot.set_contribution("p1", 50)
        pot.set_contribution("p2", 50)
        awards = resolve_showdown(engine, [("p2", self.P2_HOLE), ("p1", self.P1_HOLE)],
                                   self.BOARD, pot, "p1", ["p1", "p2"])
        assert awards == {"p2": 100}


# =============================================================================
# Group: odd-chip showdown split wiring (requirement 3)
# =============================================================================

class TestOddChipSplitWiring:
    def test_forced_chop_remainder_goes_to_first_clockwise_from_button(self):
        # Board plays: a straight using only the board. get_hand_key()'s
        # straight representation is (4, high) with no kickers, so any
        # non-improving hole cards tie exactly.
        board = [Card(10, 0), Card(9, 1), Card(8, 2), Card(7, 3), Card(6, 0)]
        p1_hole = [Card(2, 1), Card(3, 2)]
        p2_hole = [Card(2, 2), Card(3, 3)]
        assert raw_best(p1_hole, board) == raw_best(p2_hole, board)

        engine = make_real_engine()
        pot = PotManager()
        pot.set_contribution("p1", 50)
        pot.set_contribution("p2", 51)  # odd total pot = 101
        awards = resolve_showdown(engine, [("p1", p1_hole), ("p2", p2_hole)],
                                   board, pot, button_seat="p1", seat_order=["p1", "p2"])
        assert awards == {"p1": 50, "p2": 51}  # remainder to p2, first clockwise from p1
        assert sum(awards.values()) == 101


# =============================================================================
# Group: blind posting and action order (heads-up)
# =============================================================================

class TestActionOrder:
    def test_preflop_first_to_act_is_button_postflop_first_to_act_is_bb(self):
        table = Table(["p1", "p2"], small_blind=1, big_blind=2)
        log = []
        agents = {
            "p1": OrderTrackingAgent(
                [("call", 0)] + [("check", 0)] * 3, "p1", log),
            "p2": OrderTrackingAgent(
                [("check", 0)] * 4, "p2", log),
        }
        engine = make_real_engine()
        play_hand(agents, table, engine, dealer=Dealer(rng=random.Random(3)))

        assert log[0] == "p1"   # preflop: button acts first
        assert log[2] == "p2"   # flop: first postflop action is the BB/non-button


# =============================================================================
# Group: betting-round closure predicate (requirement 1 / state machine)
# =============================================================================

class TestClosurePredicate:
    def test_checked_around_street_closes(self):
        table = Table(["p1", "p2"], small_blind=1, big_blind=2)
        pot = PotManager()
        pot.set_contribution("p1", 2)
        pot.set_contribution("p2", 2)
        live = {"p1", "p2"}
        hole = {"p1": [], "p2": []}
        agents = {"p1": ScriptedAgent([("check", 0)]), "p2": ScriptedAgent([("check", 0)])}
        run_betting_round(agents, hole, pot, table, live, "p2", [], 100_000, 2)
        assert pot.contribution("p1") == 2
        assert pot.contribution("p2") == 2

    def test_raise_reopens_action_for_the_other_seat(self):
        table = Table(["p1", "p2"], small_blind=1, big_blind=2)
        pot = PotManager()
        pot.set_contribution("p1", 2)
        pot.set_contribution("p2", 2)
        live = {"p1", "p2"}
        hole = {"p1": [], "p2": []}
        agents = {"p1": ScriptedAgent([("check", 0), ("call", 0)]),
                  "p2": ScriptedAgent([("raise", 10)])}
        run_betting_round(agents, hole, pot, table, live, "p1", [], 100_000, 2)
        # p1 checks, p2 raises to 12, p1 must be re-polled and call
        assert pot.contribution("p1") == 12
        assert pot.contribution("p2") == 12

    def test_undershoot_raise_does_not_close_or_reopen_but_the_round_still_converges(self):
        """
        An agent's raise formula can legitimately return an increment
        smaller than the actual cost_to_call it's facing (e.g. Fish's
        pot_size*0.75 against a large cost_to_call). The approved contract
        (size = increment, new_total = contribution + size) doesn't floor
        this at the call amount -- the closure predicate's own
        amount_to_call==0 check is what keeps this safe: it can't close
        while the undershooting seat still owes money, so that seat just
        gets re-polled on its next turn with a smaller, updated
        cost_to_call, converging in a bounded number of laps. Not a bug --
        verified here so it isn't mistaken for one later.
        """
        table = Table(["p1", "p2"], small_blind=1, big_blind=2)
        pot = PotManager()
        pot.set_contribution("p1", 2)
        pot.set_contribution("p2", 2)
        live = {"p1", "p2"}
        hole = {"p1": [], "p2": []}
        agents = {
            # p2 bets big first, p1 undershoots twice, then finally calls
            "p1": ScriptedAgent([("check", 0), ("raise", 5), ("call", 0)]),
            "p2": ScriptedAgent([("raise", 50), ("check", 0), ("check", 0)]),
        }
        run_betting_round(agents, hole, pot, table, live, "p1", [], 100_000, 2)
        # p1: check(2) -> p2: raise to 52 -> p1: raise(undershoot) 2+5=7,
        # still owes 45 -> p2: check (cost_to_call=0 for p2) -> p1: call 45
        # -> both land at 52
        assert pot.contribution("p1") == 52
        assert pot.contribution("p2") == 52

    def test_zero_size_raise_floors_to_one_chip_and_still_converges(self):
        """
        A ("raise", 0) return while not all-in would otherwise be a
        complete no-op -- contribution unchanged, amount_to_call
        unchanged -- which could repeat forever with zero progress and
        hang the while loop. _act()'s max(1, min(size, stack_left)) floor
        guarantees at least 1 chip of progress per raise action, so the
        seat still gets re-polled with a smaller cost_to_call and the
        round still converges in a bounded number of laps, same shape as
        the size>0 undershoot case above.
        """
        table = Table(["p1", "p2"], small_blind=1, big_blind=2)
        pot = PotManager()
        pot.set_contribution("p1", 2)
        pot.set_contribution("p2", 2)
        live = {"p1", "p2"}
        hole = {"p1": [], "p2": []}
        agents = {
            "p1": ScriptedAgent([("check", 0), ("raise", 0), ("call", 0)]),
            "p2": ScriptedAgent([("raise", 50), ("check", 0)]),
        }
        run_betting_round(agents, hole, pot, table, live, "p1", [], 100_000, 2)
        # p1: check(2) -> p2: raise to 52 -> p1: raise(0) floors to 1,
        # contribution 2+1=3, still owes 49 -> p2: check (no-op) ->
        # p1: call 49 -> both land at 52
        assert pot.contribution("p1") == 52
        assert pot.contribution("p2") == 52
