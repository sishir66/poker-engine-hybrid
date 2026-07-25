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

    def __repr__(self):
        return str(self.cards)
