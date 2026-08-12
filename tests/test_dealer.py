import random
import pytest

from src.engine.dealer import Dealer


class TestDealerUniqueness:
    def _deal_full_hand(self, num_players, seed=1):
        dealer = Dealer(rng=random.Random(seed))
        holes = dealer.deal_hole_cards(num_players)
        flop = dealer.burn_and_deal(3)
        turn = dealer.burn_and_deal(1)
        river = dealer.burn_and_deal(1)
        return dealer, holes, flop, turn, river

    def test_two_player_hand_has_no_duplicate_cards_including_burns(self):
        dealer, holes, flop, turn, river = self._deal_full_hand(num_players=2)
        all_touched = [c for hole in holes for c in hole] + flop + turn + river
        # dealer._cards[:dealer._pos] includes burns; all_touched above does not.
        # Compare against the full consumed slice to also cover burn cards.
        consumed = dealer._cards[:dealer._pos]
        assert len(consumed) == len(set((c.rank, c.suit) for c in consumed))
        assert len(all_touched) == len(set((c.rank, c.suit) for c in all_touched))

    def test_six_player_hand_has_no_duplicate_cards_including_burns(self):
        dealer, holes, flop, turn, river = self._deal_full_hand(num_players=6)
        consumed = dealer._cards[:dealer._pos]
        assert len(consumed) == len(set((c.rank, c.suit) for c in consumed))

    def test_dealing_past_remaining_cards_raises(self):
        dealer = Dealer(rng=random.Random(2))
        dealer.deal(50)
        assert dealer.cards_remaining() == 2
        with pytest.raises(ValueError):
            dealer.deal(3)

    def test_cards_remaining_tracks_consumption_exactly(self):
        dealer = Dealer(rng=random.Random(3))
        assert dealer.cards_remaining() == 52
        dealer.deal_hole_cards(2)  # 4 cards
        assert dealer.cards_remaining() == 48
        dealer.burn_and_deal(3)  # 1 burn + 3 flop
        assert dealer.cards_remaining() == 44
        dealer.burn_and_deal(1)  # turn
        assert dealer.cards_remaining() == 42
        dealer.burn_and_deal(1)  # river
        assert dealer.cards_remaining() == 40
