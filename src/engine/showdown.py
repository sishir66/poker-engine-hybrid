def resolve_showdown(engine, contenders, community_cards, pot, button_seat, seat_order):
    """
    contenders: [(seat_id, hole_cards)] for players who reached showdown.
    Returns {seat_id: chips_awarded}.

    Hand keys come from engine.get_best_hand() -- get_hand_key() tuples,
    VARIABLE length. Safe to compare against each other (same category =>
    same length; different category => element 0 decides). NEVER compare
    these against evaluate_seven()'s zero-padded 6-tuples: (4,9) and
    (4,9,0,0,0,0) are unequal and the unpadded one sorts LOWER, so a
    straight would silently lose to itself. evaluate_seven() stays inside
    calculate_win_odds(); it does not belong here.

    get_best_hand() caches on self.cache_sig, keyed on sorted(hole +
    community) -- hole cards are part of the key, so two contenders in the
    same showdown always produce different sigs and never collide, even
    though they share one engine instance and one community_cards list.

    Chip arithmetic is delegated to PotManager.split_pot() -- this
    function only decides WHO won, never how the chips divide.
    """
    keys = {seat: engine.get_best_hand(hole, community_cards) for seat, hole in contenders}
    best = max(keys.values())
    winners = [seat for seat, key in keys.items() if key == best]
    return pot.split_pot(winners, button_seat, seat_order)
