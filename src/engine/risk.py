def calculate_kelly_fraction(win_odds, pot_size, cost_to_call):
    """
    Standard Kelly Criterion: f* = (b*p - q) / b
    Bounded at 0 (never negative). Per-agent alpha scaling applied in make_decision.
    """
    if cost_to_call <= 0:
        return 1.0
    b = pot_size / cost_to_call
    p = win_odds
    q = 1 - p
    return max(0, (b * p - q) / b)


def clamp_to_bankroll(raise_size, bankroll):
    """
    Hard ceiling: no agent may ever wager more than it holds — no tabs.

    Must be applied OUTERMOST, after any max(min_raise, ...) flooring in a
    caller's sizing expression: min_raise can itself exceed a short stack,
    so clamping before that floor is applied would let min_raise punch back
    through the ceiling.
    """
    return max(0, min(int(raise_size), int(bankroll)))
