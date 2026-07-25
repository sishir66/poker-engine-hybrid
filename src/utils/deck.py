from src.utils.card import Card


class Deck:
    def __init__(self):
        self.cards = []
        for suit in range(4):
            for rank in range(2, 15):
                self.cards.append(Card(rank, suit))
