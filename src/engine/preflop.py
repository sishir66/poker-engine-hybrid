_BASE = {14: 10.0, 13: 8.0, 12: 7.0, 11: 6.0}
_GAP_PENALTY = [0, -1, -2, -4]  # index = gap; gap >= 4 → -5


def _base_score(rank):
    return _BASE.get(rank, rank / 2.0)


def chen_score(card1, card2):
    """
    Standard Bill Chen preflop formula.

    Base: A=10, K=8, Q=7, J=6, numeric = rank/2.
    Pair: base × 2, floor 5.
    Suited: +2.
    Gap: true rank distance (Ace=14, no exceptions), capped at -5 for gap >= 4.
    Connector bonus: +1 if both cards rank <= 10.
    """
    r1, r2 = card1.rank, card2.rank
    suited = card1.suit == card2.suit
    high = max(r1, r2)
    low  = min(r1, r2)

    score = _base_score(high)

    if r1 == r2:
        score = max(score * 2, 5.0)
    else:
        if suited:
            score += 2
        gap = high - low - 1
        score += _GAP_PENALTY[gap] if gap <= 3 else -5
        if high <= 10:
            score += 1

    return round(score)
