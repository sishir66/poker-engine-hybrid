import random
from src.utils.deck import Deck


class Dealer:
    """
    Owns one shuffled deck for one hand. Dealing is deck.pop-from-front,
    without replacement -- duplicate cards are structurally impossible,
    not just checked for (same principle as side pots being made
    unreachable by the reset-stacks model, Phase IV design doc §C).
    """
    def __init__(self, rng=None):
        self._rng = rng if rng is not None else random.Random()
        self._cards = Deck().cards[:]
        self._rng.shuffle(self._cards)
        self._pos = 0

    def deal(self, n):
        if self._pos + n > len(self._cards):
            raise ValueError("not enough cards left in the deck")
        dealt = self._cards[self._pos:self._pos + n]
        self._pos += n
        return dealt

    def deal_hole_cards(self, num_players):
        """One 2-card hand per player. Dealing order (2 cards to player 1,
        then player 2, ...) rather than alternating single cards around the
        table is statistically equivalent for a properly shuffled deck --
        no player sees another's cards, so any consistent assignment of the
        deck's first 2N cards is an equally valid random deal."""
        return [self.deal(2) for _ in range(num_players)]

    def burn_and_deal(self, n):
        """Burns one card, then deals n community cards (flop=3, turn/river=1)."""
        self.deal(1)
        return self.deal(n)

    def cards_remaining(self):
        return len(self._cards) - self._pos
