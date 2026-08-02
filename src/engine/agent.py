class Agent:
    """
    Base agent. Subclasses implement score_hand() and decide().
    kelly_alpha scales the Kelly fraction: effective_f = kelly_fraction * kelly_alpha.
    """

    def __init__(self, name, kelly_alpha, aggression=1.0, is_tilted=False, _tilt_hands_remaining=0):
        self.name = name
        self.kelly_alpha = kelly_alpha
        self.aggression = aggression
        self.is_tilted = is_tilted
        self._tilt_hands_remaining = _tilt_hands_remaining

    def score_hand(self, hole_cards, community_cards):
        raise NotImplementedError(f"{self.name}.score_hand() not implemented")

    def decide(self, win_odds, pot_size, cost_to_call, min_raise, bankroll):
        raise NotImplementedError(f"{self.name}.decide() not implemented")

    def check_tilt(self, hand_profit, bankroll):
        """
        Tilt state machine stub (not wired into decide() yet).
        Trigger: single-hand loss > 50% of bankroll.
        Effect: is_tilted=True, aggression *= 1.5, lasts 10 hands.
        """
        if bankroll > 0 and (-hand_profit / bankroll) > 0.5:
            self.is_tilted = True
            self._tilt_hands_remaining = 10
            self.aggression *= 1.5
        elif self._tilt_hands_remaining > 0:
            self._tilt_hands_remaining -= 1
            if self._tilt_hands_remaining == 0:
                self.is_tilted = False
                self.aggression /= 1.5

    def to_dict(self):
        return {
            "name": self.name,
            "kelly_alpha": self.kelly_alpha,
            "aggression": self.aggression,
            "is_tilted": self.is_tilted,
            "_tilt_hands_remaining": self._tilt_hands_remaining,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d["name"],
            kelly_alpha=d["kelly_alpha"],
            aggression=d.get("aggression", 1.0),
            is_tilted=d.get("is_tilted", False),
            _tilt_hands_remaining=d.get("_tilt_hands_remaining", 0)
        )


class Fish(Agent):
    """Loose-passive. High alpha = bets aggressively relative to Kelly."""

    def __init__(self):
        super().__init__(name="Fish", kelly_alpha=0.75)

    def score_hand(self, hole_cards, community_cards):
        """
        Legacy heuristic preserved verbatim from the original calculate_hands().
        Intentional quirks:
          - 'high card' check uses the LOW card (ascending sort index 0), so
            the bonus only fires when BOTH cards exceed 10.
          - Gap uses rank % 14, making Ace wrap to 0. AK/AQ/AJ/AT are patched
            to use Ace=14 so they don't take the maximal gap penalty; all other
            Ace hands (A2–A9) keep the wraparound behavior unchanged.
        community_cards is ignored — this is a preflop-only heuristic.
        """
        r1, s1 = hole_cards[0].rank, hole_cards[0].suit
        r2, s2 = hole_cards[1].rank, hole_cards[1].suit

        is_pair = (r1 == r2)
        num     = r1 + r2
        low_card = min(r1, r2)   # original called this "high"; it returns the low card
        suited  = (s1 == s2)

        # Gap: patch Ace + broadway (10-13) to use true rank 14.
        # Every other hand — including A2–A9 — uses rank % 14 as-is.
        if 14 in (r1, r2):
            other = r1 if r2 == 14 else r2
            if 10 <= other <= 13:
                diff = abs(14 - other)          # patched: AK=1, AQ=2, AJ=3, AT=4
            else:
                diff = abs((r1 % 14) - (r2 % 14))  # unpatched: A9→9, A5→5, etc.
        else:
            diff = abs((r1 % 14) - (r2 % 14))

        score = 0
        if is_pair:
            score += 30
        score += num
        if low_card > 10:                       # fires only when both cards > 10
            score += 8
            score += 3 * (low_card - 10)
        score -= diff
        if suited:
            score += 20
        if (not suited) and (low_card < 9):     # double penalty for offsuit low hands
            score -= diff

        return score


class Grinder(Agent):
    """Tight-aggressive. Conservative alpha = small, disciplined sizing."""
    def __init__(self):
        super().__init__(name="Grinder", kelly_alpha=0.25)


class QuantGrid(Agent):
    """
    SPR-bounded Kelly. Alpha is a placeholder (0.25) until SPR
    (Stack-to-Pot Ratio) logic is implemented in risk.py.
    """
    def __init__(self):
        super().__init__(name="QuantGrid", kelly_alpha=0.25)


class Whale(Agent):
    """Deep-stack maniac. Full Kelly — maximum variance, maximum action."""
    def __init__(self):
        super().__init__(name="Whale", kelly_alpha=1.0)
