import random

from src.engine.preflop import chen_score
from src.engine.risk import calculate_kelly_fraction


class Agent:
    """
    Base agent. Subclasses implement score_hand() and decide().
    kelly_alpha scales the Kelly fraction: effective_f = kelly_fraction * kelly_alpha.

    Future: decide() signature will likely need position (UTG/MP/CO/BTN/blinds)
    and bet-size-relative-to-pot/stack as additional inputs, to support:
    (1) position-based threshold tightening/loosening across all agents,
    (2) bet-size-aware fold paths (see Fish.decide() for specifics),
    (3) more realistic multi-street play generally. Not implemented yet —
    current decide() logic is intentionally position-blind as a clean baseline.
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

        self._cached_score = score
        return score

    def decide(self, win_odds, pot_size, cost_to_call, min_raise, bankroll):
        """
        Loose-passive: calls too much, folds too rarely, raises infrequently.
        Uses self._cached_score (set by score_hand()) rather than win_odds —
        Fish's decisions are driven by its own biased heuristic, not probability.

        Thresholds:
          score >= 20  = "decent" hand for Fish — call/raise only, never fold
          score <  20  = weak — 25% fold, 75% loose call

        No bet: mostly check, rare raise on strong hands.
        Bet required, decent hand: 25% raise / 75% call  (no fold path).
        Bet required, weak hand:   25% fold  / 75% call  (loose — rare fold).
        """
        score = getattr(self, "_cached_score", 0)
        r = random.random()

        if cost_to_call == 0:
            if score > 35 and r < 0.20:
                raise_size = max(min_raise, int(pot_size * 0.75 * self.aggression))
                return "raise", raise_size
            return "check", 0

        if score >= 20:
            # Future: consider a bet-size/pot-relative fold path for strong hands —
            # e.g. Fish occasionally folds even a good hand when facing a bet size
            # disproportionate to pot/stack. Not implemented yet; needs bet_size and
            # stack context that isn't currently modeled in decide()'s inputs.
            if r < 0.25:
                raise_size = max(min_raise, int(pot_size * 0.75 * self.aggression))
                return "raise", raise_size
            return "call", cost_to_call
        else:
            if r < 0.25:
                return "fold", 0
            return "call", cost_to_call


class Grinder(Agent):
    """Tight-aggressive. Conservative alpha = small, disciplined sizing."""

    def __init__(self):
        super().__init__(name="Grinder", kelly_alpha=0.25)

    def score_hand(self, hole_cards, community_cards):
        """Standard Chen formula. community_cards unused — preflop scoring only."""
        score = chen_score(hole_cards[0], hole_cards[1])
        self._cached_score = score
        return score

    def decide(self, win_odds, pot_size, cost_to_call, min_raise, bankroll):
        """
        Tight-aggressive: folds marginal hands readily, raises rather than calls
        when it does play. Uses _cached_score set by score_hand() — same pattern
        as Fish. Decisions are fully score-gated; no fold/raise paths fire
        independent of hand strength.

        Chen thresholds (K=8, true-rank gap):
          score <  7              → fold (bet) / check (free) — trash, small pairs
          7 <= score <= 9         → raise 30% / call 70% (bet); raise 25% / check 75% (free)
          score >= 10             → raise 80% / call 20% (bet); raise 60% / check 40% (free)
        """
        score = getattr(self, "_cached_score", 0)
        r = random.random()

        if cost_to_call == 0:
            if score >= 10 and r < 0.60:
                return "raise", max(min_raise, int(pot_size * self.aggression))
            if 7 <= score < 10 and r < 0.25:
                return "raise", max(min_raise, int(pot_size * 0.75 * self.aggression))
            return "check", 0

        if score < 7:
            return "fold", 0
        if score <= 9:
            if r < 0.30:
                return "raise", max(min_raise, int(pot_size * 0.75 * self.aggression))
            return "call", cost_to_call
        # score >= 10
        if r < 0.80:
            return "raise", max(min_raise, int(pot_size * self.aggression))
        return "call", cost_to_call



class QuantGrid(Agent):
    """
    Monte Carlo Kelly agent (Option B). Computes win probability via real
    simulation rather than static heuristics — QuantGrid's identity is being
    the mathematically rigorous agent, in contrast to Fish (loose heuristic)
    and Grinder (tight Chen formula).

    Requires a PokerEngine instance at construction time for calculate_win_odds().
    See PokerEngine_Blueprint.md §5.5 for full design rationale.
    """

    def __init__(self, engine):
        super().__init__(name="QuantGrid", kelly_alpha=0.25)
        self._engine = engine

    def score_hand(self, hole_cards, community_cards):
        """
        Caches hole_cards and community_cards for use by decide(), which calls
        calculate_win_odds() internally. Also computes and caches the Chen score
        (returned for interface compatibility) but decide() does not use it —
        Chen no longer gates QuantGrid's decision tree under Option B.

        Phase V (empirical hand memory, Blueprint §5.5): when built, the blend
        of empirical win rate and simulation output will both be on [0,1] — no
        unit-conversion needed. This implementation is compatible with Phase V
        as-is.
        """
        self._hole_cards = hole_cards
        self._community_cards = community_cards
        score = chen_score(hole_cards[0], hole_cards[1])
        self._cached_score = score
        return score

    def decide(self, pot_size, cost_to_call, min_raise, bankroll):
        """
        Option B: win_odds computed internally via Monte Carlo simulation.
        Signature differs from base Agent.decide() — win_odds parameter is
        removed; callers must not pass it positionally.

        score_hand() must be called before decide() to cache hole/community
        cards (same call-order contract as Fish and Grinder, which cache
        _cached_score before decide() reads it).

        Decision tree — gated on kelly_f = calculate_kelly_fraction(win_odds, pot, cost):

          cost_to_call == 0 (free):
            win_odds < 0.50  → check
            win_odds >= 0.50 → raise 60% / check 40%
            (kelly_f = 1.0 when cost=0 per risk.py, so win_odds used directly)

          cost_to_call > 0:
            kelly_f < 0.05   → fold
            0.05 ≤ kf ≤ 0.35 → raise 30% / call 70%
            kelly_f > 0.35   → raise 80% / call 20%

        Threshold rationale: both floors (0.05 fold, 0.35 raise) add a safety
        margin above their mathematical breakpoints (0.0 = exact Kelly breakeven;
        0.30 = original derivation). This is personality tuning — same category
        as Fish's A9o double-penalty threshold (Blueprint §4.3) — not a formula
        correction. Both values are starting points to be re-evaluated against
        Phase IV simulation data (BB/100 results across agents).
        """
        win_odds = self._engine.calculate_win_odds(
            getattr(self, '_hole_cards', []),
            getattr(self, '_community_cards', []),
        )

        kelly_f = calculate_kelly_fraction(win_odds, pot_size, cost_to_call)
        kelly_raise = max(
            min_raise,
            int(bankroll * kelly_f * self.kelly_alpha * self.aggression)
        )
        r = random.random()

        if cost_to_call == 0:
            if win_odds >= 0.50 and r < 0.60:
                return "raise", kelly_raise
            return "check", 0

        if kelly_f < 0.05:
            return "fold", 0
        if kelly_f <= 0.35:
            if r < 0.30:
                return "raise", kelly_raise
            return "call", cost_to_call
        # kelly_f > 0.35
        if r < 0.80:
            return "raise", kelly_raise
        return "call", cost_to_call


class Whale(Agent):
    """Deep-stack maniac. Full Kelly — maximum variance, maximum action."""
    def __init__(self):
        super().__init__(name="Whale", kelly_alpha=1.0)
