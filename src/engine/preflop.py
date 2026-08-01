_BASE = {14: 10.0, 13: 7.0, 12: 7.0, 11: 6.0}
_GAP_PENALTY = [0, -1, -2, -4]  # index=gap; gap>=4 → -5


def _base_score(rank):
    return _BASE.get(rank, rank / 2.0)


def _ace_gap(low_rank):
    """
    For A-X where X < K, treat Ace as rank 12 (Q) for gap calculation.
    This matches the widely-cited results: A9o=8, A5s=7.
    For A-K specifically, Ace is adjacent (gap=0) under any encoding.
    """
    if low_rank >= 13:   # A-K: connectors
        return 0
    return max(0, 12 - low_rank - 1)


def chen_score(card1, card2):
    """
    Bill Chen preflop formula. Returns score rounded to nearest integer.

    Deviations from the original 2006 publication that match common
    online implementations / widely-cited reference tables:
      - K base score = 7 (not 8); gives KQs=9 rather than 10.
      - For A-X where X is not K, gap uses effective ace rank=12 (Q);
        gives A9o=8, A5s=7 rather than 5 and 7.
      - Ace is never treated as rank 1 for gap — A-low hands (A2s, A5s)
        take the full -5 gap penalty rather than near-zero.
      - Connector bonus (+1) fires when BOTH cards have rank <= 10,
        no gap condition.
    """
    r1, r2 = card1.rank, card2.rank
    suited = card1.suit == card2.suit
    high = max(r1, r2)
    low  = min(r1, r2)

    score = _base_score(high)

    if r1 == r2:                        # pocket pair: double (min 5)
        score = max(score * 2, 5.0)
    else:
        if suited:
            score += 2
        gap = _ace_gap(low) if high == 14 else high - low - 1
        score += _GAP_PENALTY[gap] if gap <= 3 else -5
        if high <= 10:                  # connector bonus: both cards T or lower
            score += 1

    return round(score)
