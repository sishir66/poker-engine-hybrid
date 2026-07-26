import torch
import joblib
import itertools
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from src.utils.card import Card
from src.utils.deck import Deck
from src.engine.hand import Hand
from src.models.train_poker import PokerMLP
from src.models.generate_dataset import convert_card_to_data
from src.engine.risk import calculate_kelly_fraction


class PokerEngine:
    def __init__(self, model_path='data/poker_model.pth', scaler_path='data/poker_scaler.pkl'):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = PokerMLP().to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()
        self.scaler = joblib.load(scaler_path)

        self.session_history = []

        # --- CACHE / STATE MANAGEMENT ---
        self.cache_odds = None
        self.cache_cards = None
        self.current_best_hand = None

    def get_best_hand(self, hole_cards, community_cards):
        """
        Deterministic best-hand evaluation over all C(n,5) combinations.
        Returns a get_hand_key() tuple — not an MLP scalar — so kicker
        tiebreaking is preserved. MLP is no longer used here; it remains
        available for the (still broken) calculate_win_odds() batch path.
        """
        current_sig = tuple(sorted([(c.rank, c.suit) for c in (hole_cards + community_cards)]))

        if hasattr(self, 'cache_sig') and self.cache_sig == current_sig:
            return self.current_best_hand

        all_cards = hole_cards + community_cards
        if len(all_cards) < 5:
            return (0,)

        best_key = max(
            Hand(list(combo)).get_hand_key()
            for combo in itertools.combinations(all_cards, 5)
        )

        self.current_best_hand = best_key
        self.cache_sig = current_sig
        return best_key

    def calculate_win_odds(self, hole_cards, community_cards, num_opponents=1, simulations=1000):
        """Vectorized Monte Carlo Simulation."""
        current_state = hole_cards + community_cards
        if self.cache_cards == current_state and self.cache_odds is not None:
            return self.cache_odds

        full_deck = Deck().cards
        seen = [(c.rank, c.suit) for c in current_state]
        remaining = [c for c in full_deck if (c.rank, c.suit) not in seen]
        deck_arr = np.array([[c.rank, c.suit] for c in remaining])

        cards_needed_board = 5 - len(community_cards)
        total_needed = cards_needed_board + (num_opponents * 2)

        indices = np.array([np.random.choice(len(deck_arr), total_needed, replace=False) for _ in range(simulations)])
        sim_cards = deck_arr[indices]

        # NOTE: feature_matrix infill not yet implemented — returns garbage (all zeros)
        total_hands = simulations * (1 + num_opponents)
        feature_matrix = np.zeros((total_hands, 14))

        # [Broadcasting/Infilling logic for feature_matrix goes here]

        # --- MLP path (feature_matrix above is still all-zeros / broken) ---
        # Kept as a stub for future vectorized inference once infill is fixed.
        # The comparison below bypasses it and uses deterministic Hand evaluation.

        # --- Comparison: get_hand_key() tuples, kicker-aware ---
        wins = 0
        ties = 0
        for sim_idx in range(simulations):
            drawn = sim_cards[sim_idx]  # shape (total_needed, 2): [rank, suit]
            board_drawn = [
                Card(int(drawn[i, 0]), int(drawn[i, 1]))
                for i in range(cards_needed_board)
            ]
            full_board = community_cards + board_drawn

            our_seven = hole_cards + full_board
            our_key = max(
                Hand(list(c)).get_hand_key()
                for c in itertools.combinations(our_seven, 5)
            )

            opp_offset = cards_needed_board
            opp_keys = []
            for opp in range(num_opponents):
                i0 = opp_offset + opp * 2
                opp_hole = [
                    Card(int(drawn[i0, 0]),     int(drawn[i0, 1])),
                    Card(int(drawn[i0 + 1, 0]), int(drawn[i0 + 1, 1])),
                ]
                opp_seven = opp_hole + full_board
                opp_key = max(
                    Hand(list(c)).get_hand_key()
                    for c in itertools.combinations(opp_seven, 5)
                )
                opp_keys.append(opp_key)

            best_opp = max(opp_keys)
            if our_key > best_opp:
                wins += 1
            elif our_key == best_opp:
                ties += 1

        final_odds = (wins + ties / 2) / simulations

        self.cache_odds = final_odds
        self.cache_cards = current_state
        return final_odds

    def make_decision(self, win_odds, pot_size, cost_to_call, min_raise, bankroll, is_dealer=False, is_button=False):
        kelly_f = calculate_kelly_fraction(win_odds, pot_size, cost_to_call)

        pos_mult = 1.2 if is_dealer else (1.1 if is_button else 1.0)
        suggested_bet = bankroll * (kelly_f * 0.25 * pos_mult)

        if kelly_f <= 0:
            bluff_chance = 0.08 if is_dealer else 0.04
            if win_odds > 0.15 and random.random() < bluff_chance:
                return "Positional Bluff", min_raise
            return "Fold", 0

        if win_odds > 0.80:
            return "Value Raise", max(suggested_bet, min_raise * 2)

        if suggested_bet >= cost_to_call:
            return "Call", cost_to_call

        return "Check/Fold", 0


if __name__ == "__main__":
    engine = PokerEngine()

    my_hand = [Card(14, 0), Card(14, 1)]
    current_board = [Card(10, 3), Card(11, 3), Card(2, 2)]
    num_opponents = 2
    sim_iterations = 500

    print(f"\n--- Testing Scenario ---")
    print(f"Your Hand: {my_hand}")
    print(f"The Board: {current_board}")
    print(f"Simulating against {num_opponents} opponents over {sim_iterations} runs...")

    win_probability = engine.calculate_win_odds(
        my_hand,
        current_board,
        num_opponents=num_opponents,
        simulations=sim_iterations
    )

    print(f"\n--- Result ---")
    print(f"Calculated Win Probability: {win_probability * 100:.2f}%")

    # NOTE: record_action() and plot_session_results() not yet implemented
