from collections import Counter


class Hand:
    def __init__(self, cards):
        """Expects a list of 5 Card objects."""
        self.cards = cards
        self.cards.sort(key=lambda x: (x.rank, x.suit))
        self.counts = Counter(card.rank for card in self.cards)
        self.dist = sorted(self.counts.values(), reverse=True)

    def is_flush(self):
        return len({card.suit for card in self.cards}) == 1

    def is_straight(self):
        set_cards = {card.rank for card in self.cards}
        if len(set_cards) == 5:
            if (max(set_cards) - min(set_cards) == 4) or (set_cards == {14, 2, 3, 4, 5}):
                return True
        return False

    def get_rank_value(self):
        """Returns an integer 0-9 representing hand strength."""
        if self.is_flush() and self.is_straight():
            if [self.cards[0].rank, self.cards[-1].rank] == [10, 14]:
                return 9  # Royal Flush
            return 8      # Straight Flush
        if self.dist == [4, 1]:    return 7  # Four of a Kind
        if self.dist == [3, 2]:    return 6  # Full House
        if self.is_flush():        return 5  # Flush
        if self.is_straight():     return 4  # Straight
        if self.dist == [3, 1, 1]: return 3  # Three of a Kind
        if self.dist == [2, 2, 1]: return 2  # Two Pair
        if self.dist == [2, 1, 1, 1]: return 1  # Pair
        return 0  # High Card

    def get_hand_key(self):
        """
        Returns a comparison tuple (rank_value, *tiebreak_ranks) for full
        kicker-aware ordering. Python tuple comparison resolves tiebreakers
        left-to-right automatically.

        Pair ranks are always extracted with explicit sorted(..., reverse=True)
        — never via Counter.most_common(), whose tie-ordering is insertion order
        (ascending rank for a sorted hand), which silently picks the wrong pair.

        Straight/straight-flush: wheel (A-2-3-4-5) is represented as high=5,
        not high=14, so it sorts below a 6-high straight.
        """
        ranks = [c.rank for c in self.cards]  # ascending, guaranteed by __init__
        rv = self.get_rank_value()

        if rv == 0:  # High Card
            return (0,) + tuple(sorted(ranks, reverse=True))

        if rv == 1:  # Pair
            pair_r = max(r for r, cnt in self.counts.items() if cnt == 2)
            kickers = sorted((r for r, cnt in self.counts.items() if cnt == 1), reverse=True)
            return (1, pair_r) + tuple(kickers)

        if rv == 2:  # Two Pair — explicit sort required; most_common() gives wrong order
            pair_ranks = sorted((r for r, cnt in self.counts.items() if cnt == 2), reverse=True)
            kicker = max(r for r, cnt in self.counts.items() if cnt == 1)
            return (2, pair_ranks[0], pair_ranks[1], kicker)

        if rv == 3:  # Three of a Kind
            trips_r = max(r for r, cnt in self.counts.items() if cnt == 3)
            kickers = sorted((r for r, cnt in self.counts.items() if cnt == 1), reverse=True)
            return (3, trips_r) + tuple(kickers)

        if rv == 4:  # Straight — wheel = 5-high, not ace-high
            straight_high = 5 if set(ranks) == {14, 2, 3, 4, 5} else max(ranks)
            return (4, straight_high)

        if rv == 5:  # Flush — all five ranks matter
            return (5,) + tuple(sorted(ranks, reverse=True))

        if rv == 6:  # Full House
            trips_r = max(r for r, cnt in self.counts.items() if cnt == 3)
            pair_r  = max(r for r, cnt in self.counts.items() if cnt == 2)
            return (6, trips_r, pair_r)

        if rv == 7:  # Four of a Kind
            quad_r   = max(r for r, cnt in self.counts.items() if cnt == 4)
            kicker_r = max(r for r, cnt in self.counts.items() if cnt == 1)
            return (7, quad_r, kicker_r)

        if rv == 8:  # Straight Flush — same wheel rule as rv==4
            sf_high = 5 if set(ranks) == {14, 2, 3, 4, 5} else max(ranks)
            return (8, sf_high)

        return (9, 14)  # Royal Flush — all equal

    def __repr__(self):
        return str(self.cards)
