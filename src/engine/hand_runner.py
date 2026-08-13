from src.engine.dealer import Dealer
from src.engine.pot import PotManager
from src.engine.showdown import resolve_showdown


STREETS = (("preflop", 0), ("flop", 3), ("turn", 1), ("river", 1))


def run_betting_round(agents, hole, pot, table, live, first_to_act, community, starting_stack, min_raise):
    """
    One street's betting action, mutating `pot` and `live` in place.
    N-general: iterates seats via table.seat_after(), closing the round
    via a closure predicate (`acted`) over live/actionable seats -- not a
    hardcoded 2-player alternation, even though only 2 seats run today.
    """
    acted = set()
    seat = first_to_act

    while True:
        if len(live) == 1:
            return  # everyone else folded -- caller treats this as hand over

        actionable = [s for s in table.seats
                      if s in live and starting_stack - pot.contribution(s) > 0]
        if not actionable:
            return  # every live seat is all-in -- nothing left to decide this street

        if acted.issuperset(actionable) and all(pot.amount_to_call(s) == 0 for s in actionable):
            return  # every actionable seat has acted since the last raise and matched

        if seat in actionable:
            _act(seat, agents[seat], hole, pot, community, starting_stack, min_raise, live, acted)

        seat = table.seat_after(seat)


def _act(seat, agent, hole, pot, community, starting_stack, min_raise, live, acted):
    """
    Resolves one seat's decision. Every non-fold branch adds to `acted` --
    this is the entire mechanism run_betting_round's closure predicate
    rests on. A folded seat gets no acted.add(): it leaves `live` (and
    therefore `actionable`) on its own, so it can never block closure.
    """
    stack_left = starting_stack - pot.contribution(seat)
    cost = min(pot.amount_to_call(seat), stack_left)
    highest_before = pot.highest_contribution()

    # Required for all four agents, not just the engine-backed ones: Fish
    # and Grinder read getattr(self, "_cached_score", 0) for their own
    # thresholding (Blueprint SS5.3/5.4) -- skipping this silently defaults
    # them to score 0 (Fish's weak branch, Grinder's fold-everything floor)
    # rather than crashing. QuantGrid/Whale cache hole/community here too.
    agent.score_hand(hole[seat], community)
    action, size = agent.decide(pot.total_pot(), cost, min_raise, stack_left)

    if action == "fold":
        live.discard(seat)
    elif action == "check":
        assert cost == 0, "check with a live bet would make closure unsatisfiable"
        acted.add(seat)
    elif action == "call":
        pot.set_contribution(seat, pot.contribution(seat) + cost)
        acted.add(seat)
    elif action == "raise":
        # decide()'s raise size is an INCREMENT (locked contract, Stage 2
        # plan) -- converted to a raise-TO total before it reaches the pot
        # manager. min(size, stack_left) means an all-in can never exceed
        # the stack or trip PotManager's monotonic-decrease guard.
        new_total = pot.contribution(seat) + min(size, stack_left)
        pot.set_contribution(seat, new_total)
        if new_total > highest_before:
            acted.clear()  # real aggression reopens the round for everyone else
        acted.add(seat)
    else:
        raise ValueError(f"unknown action {action!r} from {agent.name}")


def play_hand(agents, table, engine, dealer=None, ledger=None):
    """
    Plays exactly one hand to completion: posts blinds, runs betting on
    each street, resolves showdown (or an early fold-exit), applies
    check_tilt() to every seated agent, and records to `ledger` if given.

    Heads-up only (len(table.seats) == 2) -- the reset-every-hand equal
    stack model this relies on for "no side pots needed" only holds for
    exactly 2 players; N>2 needs side-pot logic, not built (Stage 3+).

    Does NOT rotate the button between hands -- that's the caller's job
    across a multi-hand session, out of scope for a single play_hand() call.
    """
    assert len(table.seats) == 2, "Stage 2 is heads-up only -- N>2 needs side-pot logic"

    if dealer is None:
        dealer = Dealer()

    starting_stack = 100 * table.big_blind
    pot = PotManager()
    live = set(table.seats)
    hole = dict(zip(table.seats, dealer.deal_hole_cards(len(table.seats))))
    community = []

    sb_seat, bb_seat = table.blind_seats()
    pot.set_contribution(sb_seat, table.small_blind)
    pot.set_contribution(bb_seat, table.big_blind)

    for street, n_cards in STREETS:
        if n_cards:
            community.extend(dealer.burn_and_deal(n_cards))
        first_to_act = (table.seat_after(bb_seat) if street == "preflop"
                        else table.seat_after(table.button_seat))
        run_betting_round(agents, hole, pot, table, live, first_to_act,
                           community, starting_stack, table.big_blind)
        if len(live) == 1:
            break

    went_to_showdown = len(live) > 1
    if went_to_showdown:
        awards = resolve_showdown(engine, [(s, hole[s]) for s in live],
                                   community, pot, table.button_seat, table.seats)
    else:
        awards = {next(iter(live)): pot.total_pot()}

    deltas = {s: awards.get(s, 0) - pot.contribution(s) for s in table.seats}

    assert sum(awards.values()) == pot.total_pot(), "pot award mismatch"
    assert sum(deltas.values()) == 0, "chip conservation violated"

    for seat in table.seats:
        # bankroll = starting_stack (this hand's START), never the
        # post-settlement stack -- see Stage 2 plan's tilt-mistrigger note.
        agents[seat].check_tilt(deltas[seat], starting_stack)
        if ledger is not None:
            ledger.record_hand(seat, deltas[seat] / table.big_blind)

    return {
        "deltas": deltas,
        "awards": awards,
        "community": community,
        "hole": hole,
        "live": live,
        "pot_total": pot.total_pot(),
        "went_to_showdown": went_to_showdown,
    }
