"""Grinder vs Fish over 20,000 seeded hands, once per seed. Prints BB/100 with a 95% CI."""
import sys
import time

from src.engine.agent import Fish, Grinder
from src.engine.ledger import Ledger
from src.engine.session import run_session
from src.engine.simulation import PokerEngine
from src.engine.table import Table

SEEDS = [1, 2, 3, 42, 99, 123, 555, 777, 1000, 2026]
HANDS = 20000


def main(seeds=SEEDS, hands=HANDS):
    engine = PokerEngine()
    means = []
    print("seed  grinder_bb100  +/-ci95   lower   upper  excludes0  secs")
    for seed in seeds:
        table = Table(["grinder", "fish"], small_blind=1, big_blind=2)
        agents = {"grinder": Grinder(), "fish": Fish()}
        ledger = Ledger()
        t0 = time.perf_counter()
        run_session(agents, table, engine, num_hands=hands, seed=seed, ledger=ledger)
        secs = time.perf_counter() - t0
        mean, ci = ledger.bb_per_100("grinder")
        means.append(mean)
        print(f"{seed:<5} {mean:13.2f} {ci:8.2f} {mean - ci:7.2f} {mean + ci:7.2f}  {str(mean - ci > 0):<9} {secs:5.2f}")
    print(f"mean of {len(means)} seed means: {sum(means) / len(means):.2f} BB/100 "
          f"(min {min(means):.2f}, max {max(means):.2f})")


if __name__ == "__main__":
    main()
