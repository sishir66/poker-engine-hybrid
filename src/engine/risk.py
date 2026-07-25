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
