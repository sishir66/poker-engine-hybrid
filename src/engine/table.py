class Table:
    def __init__(self, seat_ids, small_blind=1, big_blind=2):
        if len(seat_ids) < 2:
            raise ValueError("need at least 2 seats")
        self._seats = list(seat_ids)  # clockwise order
        self._button_idx = 0
        self.small_blind = small_blind
        self.big_blind = big_blind

    @property
    def seats(self):
        return list(self._seats)

    @property
    def button_seat(self):
        return self._seats[self._button_idx]

    def seat_after(self, seat_id, offset=1):
        idx = self._seats.index(seat_id)
        return self._seats[(idx + offset) % len(self._seats)]

    def blind_seats(self):
        """(small_blind_seat, big_blind_seat). Heads-up is a real-poker
        special case, not a bug: with exactly 2 seats the button POSTS the
        small blind directly (standard convention); with 3+, the blinds are
        the two seats clockwise from the button."""
        if len(self._seats) == 2:
            return self.button_seat, self.seat_after(self.button_seat)
        sb = self.seat_after(self.button_seat)
        bb = self.seat_after(self.button_seat, offset=2)
        return sb, bb

    def rotate_button(self):
        self._button_idx = (self._button_idx + 1) % len(self._seats)
