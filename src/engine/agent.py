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
