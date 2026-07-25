class Card:
    RANK_MAP = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8',
                9: '9', 10: '10', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
    SUIT_MAP = {0: '♠', 1: '♥', 2: '♦', 3: '♣'}

    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    def __repr__(self):
        return f"{self.RANK_MAP[self.rank]}{self.SUIT_MAP[self.suit]}"

    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit
