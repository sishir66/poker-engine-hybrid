import math


class Ledger:
    """Per-hand profit (in big blinds -- caller converts raw chips to BB
    before recording, keeping this decoupled from Table's blind size) ->
    BB/100 with a confidence interval. A point estimate with no error bars
    was explicitly flagged as untrustworthy (Phase IV design doc §D)."""
    def __init__(self):
        self._profits_bb = {}  # agent_id -> list[float]

    def record_hand(self, agent_id, profit_bb):
        self._profits_bb.setdefault(agent_id, []).append(profit_bb)

    def hands_played(self, agent_id):
        return len(self._profits_bb.get(agent_id, []))

    def bb_per_100(self, agent_id):
        """(mean_bb_per_100, ci95_halfwidth_bb_per_100). Needs >=2 hands --
        a 1-hand "BB/100" is meaningless, not just imprecise, so this raises
        rather than returning a number with an undefined error bar."""
        samples = self._profits_bb.get(agent_id, [])
        n = len(samples)
        if n < 2:
            raise ValueError(f"need at least 2 hands for a confidence interval, got {n}")
        mean = sum(samples) / n
        variance = sum((x - mean) ** 2 for x in samples) / (n - 1)
        se = math.sqrt(variance / n)
        return mean * 100, 1.96 * se * 100
