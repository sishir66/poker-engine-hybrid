import pandas as pd
import random
from src.utils.card import Card
from src.engine.hand import Hand
from src.utils.deck import Deck
from collections import Counter
import numpy as np
import os


def generate_hand(temp_deck):
    x = temp_deck.cards
    random.shuffle(x)
    return x[:5]


def convert_card_to_data(card_list_of_lists, return_numpy=False):
    big_list = []
    for hand_cards in card_list_of_lists:
        hand_cards = sorted(hand_cards, key=lambda x: x.rank)

        ranks = [card.rank for card in hand_cards]
        suits = [card.suit for card in hand_cards]

        r_counts = Counter(ranks)
        max_r = r_counts.most_common(1)[0][1] if r_counts else 1

        s_counts = Counter(suits)
        max_s = s_counts.most_common(1)[0][1] if s_counts else 1

        unique_count = len(set(ranks))

        unique_ranks_sorted = sorted(list(set(ranks)))
        is_st = 0
        if len(unique_ranks_sorted) == 5:
            if (unique_ranks_sorted[4] - unique_ranks_sorted[0] == 4) or (unique_ranks_sorted == [2, 3, 4, 5, 14]):
                is_st = 1

        row = []
        for card in hand_cards:
            row.extend([card.rank, card.suit])

        row.extend([max_r, max_s, is_st, unique_count])

        if not return_numpy:
            my_hand = Hand(hand_cards)
            row.append(my_hand.get_rank_value())

        big_list.append(row)

    if return_numpy:
        return np.array(big_list, dtype=np.float32)
    return big_list


def generate_two_pair(n):
    temp_deck = Deck()
    list_to_return = []
    for _ in range(n):
        ranks = random.sample(range(13), 3)
        p1_rank, p2_rank, kicker_rank = ranks[0], ranks[1], ranks[2]
        p1_pool = [temp_deck.cards[k] for k in range(p1_rank, 52, 13)]
        p1_cards = random.sample(p1_pool, 2)
        p2_pool = [temp_deck.cards[k] for k in range(p2_rank, 52, 13)]
        p2_cards = random.sample(p2_pool, 2)
        k_pool = [temp_deck.cards[k] for k in range(kicker_rank, 52, 13)]
        kicker_card = [random.choice(k_pool)]
        list_to_return.append(p1_cards + p2_cards + kicker_card)
    return list_to_return


def generate_trips(n):
    list_to_return = []
    for i in range(n):
        for j in range(12):
            temp_deck = Deck()
            possible_counts = [temp_deck.cards[k] for k in range(j, 52, 13)]
            trips = random.sample(possible_counts, 3)
            kickers = random.sample(temp_deck.cards, 2)
            list_to_return.append(trips + kickers)
    return list_to_return


def generate_straights(n):
    temp_deck = Deck()
    list_to_return = []
    for i in range(n):
        for i in range(9):
            x = []
            for j in range(5):
                x.append(temp_deck.cards[i + random.choice([j, j + 13, j + 26, j + 39])])
            list_to_return.append(x)
        temp_ace_list = [temp_deck.cards[i + random.choice([13, 26, 39])] for i in range(1, 5)]
        list_to_return.append([temp_deck.cards[12]] + temp_ace_list)
    return list_to_return


def generate_flush(n):
    temp_deck = Deck()
    list_to_return = []
    for i in range(n):
        for i in range(4):
            all_cards_in_suit = temp_deck.cards[i * 13: (i * 13) + 13]
            flush_chosen = random.sample(all_cards_in_suit, 5)
            list_to_return.append(flush_chosen)
    return list_to_return


def generate_boats(n):
    temp_deck = Deck()
    list_to_return = []
    for x in range(n):
        for i in range(13):
            for j in range(1, 14):
                if i != j:
                    trips_list = [temp_deck.cards[l] for l in range(i, 52, 13)]
                    trips_chosen = random.sample(trips_list, 3)
                    pairs_possible = [temp_deck.cards[l] for l in range(j, 52, 13)]
                    pair_chosen = random.sample(pairs_possible, 2)
                list_to_return.append(trips_chosen + pair_chosen)
    return list_to_return


def generate_quads(n):
    temp_deck = Deck()
    list_to_return = []
    for x in range(n):
        for i in range(13):
            for j in range(13):
                if i != j:
                    quads = [temp_deck.cards[i] for i in range(i, 52, 13)]
                    kicker = [temp_deck.cards[random.choice([j, j + 13, j + 26, j + 39])]]
                    list_to_return.append(quads + kicker)
    return list_to_return


def generate_straight_flush(n):
    temp_deck = Deck()
    list_to_return = []
    counter = 9
    prev = 0
    for y in range(n):
        for i in range(4):
            for x in range(prev, counter):
                sf = [temp_deck.cards[l + (x % 13)] for l in range(5)]
                list_to_return.append(sf)
            temp_ace_list = temp_deck.cards[i * 13:(i * 13) + 4]
            ace_str = [temp_deck.cards[12 + (13 * i)]] + temp_ace_list
            list_to_return.append(ace_str)
            prev += 13
            counter += 13
    return list_to_return


def generate_poker_samples(n):
    big_outer_list = []
    for i in range(n):
        y = Deck()
        draw5 = generate_hand(y)
        big_outer_list.append(draw5)
    return big_outer_list


def generate_pairs(n):
    temp_deck = Deck()
    list_to_return = []
    samples_per_rank = n // 13
    for rank_val in range(13):
        for _ in range(samples_per_rank):
            rank_pool = [temp_deck.cards[rank_val + (i * 13)] for i in range(4)]
            pair_cards = random.sample(rank_pool, 2)
            remaining_pool = [c for c in temp_deck.cards if c.rank != rank_val + 2]
            kickers = random.sample(remaining_pool, 3)
            hand_cards = pair_cards + kickers
            hand_cards.sort(key=lambda x: x.rank)
            list_to_return.append(hand_cards)
    return list_to_return


# NOTE: module-level execution intentionally left unfixed — runs on import
all_hands_raw = []
all_hands_raw.extend([generate_hand(Deck()) for _ in range(100000)])
all_hands_raw.extend(generate_pairs(50000))
all_hands_raw.extend(generate_two_pair(25000))
all_hands_raw.extend(generate_poker_samples(100000))
all_hands_raw.extend(generate_trips(3000))
all_hands_raw.extend(generate_straights(4000))
all_hands_raw.extend(generate_flush(10000))
all_hands_raw.extend(generate_boats(250))
all_hands_raw.extend(generate_quads(250))
all_hands_raw.extend(generate_straight_flush(1500))
all_hands_raw.extend(generate_pairs(50000))
all_hands_raw.extend(generate_poker_samples(100000))
all_hands_raw.extend(generate_pairs(50000))

final_data = convert_card_to_data(all_hands_raw)

column_names = [
    'C1_R', 'C1_S', 'C2_R', 'C2_S', 'C3_R', 'C3_S', 'C4_R', 'C4_S', 'C5_R', 'C5_S',
    'Max_R_Freq', 'Max_S_Freq', 'Straight_Pot', 'Unique_Count', 'Label'
]

df = pd.DataFrame(final_data, columns=column_names)

if not os.path.exists("data"):
    os.makedirs("data")

df.to_csv("data/poker_training_daa_v1.csv", index=False)

print("--- DATA GENERATION COMPLETE ---")
print(f"Total Rows: {len(df)}")
print(f"Features: {df.shape[1] - 1}")
print(df["Label"].value_counts())
