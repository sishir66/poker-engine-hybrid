class PotManager:
    """
    contribution() is a CUMULATIVE total for the entire hand, never reset
    per street. amount_to_call() is correct as written specifically
    because a betting round cannot close until every live player's
    contribution already equals highest_contribution() -- so it naturally
    reads 0 at the start of each new street, without needing a reset.
    Do not add a reset-between-streets method in Stage 2; that would
    double-book contributions against this invariant, not preserve it.
    """
    def __init__(self):
        self._contributions = {}  # player_id -> total chips this hand

    def set_contribution(self, player_id, total_amount):
        """total_amount is the player's new running total, not an increment --
        raise-TO semantics. Rejects a decrease loudly rather than silently."""
        if total_amount < self._contributions.get(player_id, 0):
            raise ValueError(
                f"contribution cannot decrease ({player_id}: "
                f"{self._contributions.get(player_id, 0)} -> {total_amount})"
            )
        self._contributions[player_id] = total_amount

    def contribution(self, player_id):
        return self._contributions.get(player_id, 0)

    def total_pot(self):
        return sum(self._contributions.values())

    def highest_contribution(self):
        return max(self._contributions.values(), default=0)

    def amount_to_call(self, player_id):
        return self.highest_contribution() - self.contribution(player_id)

    def split_pot(self, winner_ids, button_seat, seat_order):
        """
        Splits total_pot() evenly among winner_ids (integers only -- chip
        counts, never floats, per the decided chip-representation contract).
        Any remainder goes to the first winner clockwise from button_seat,
        per the decided odd-chip rule -- deterministic under a fixed
        seat_order. winner_ids is supplied by the caller (Showdown owns
        hand comparison); this function only does the chip arithmetic.
        """
        pot = self.total_pot()
        share, remainder = divmod(pot, len(winner_ids))
        shares = {pid: share for pid in winner_ids}
        if remainder:
            start = seat_order.index(button_seat)
            for offset in range(1, len(seat_order) + 1):
                candidate = seat_order[(start + offset) % len(seat_order)]
                if candidate in winner_ids:
                    shares[candidate] += remainder
                    break
        return shares
