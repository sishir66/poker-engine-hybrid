"""Grinder vs Fish over seeded hands (default 20,000), once per seed. Prints BB/100 with a 95% CI."""
import argparse
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
    means, cis = [], []
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
        cis.append(ci)
        print(f"{seed:<5} {mean:13.2f} {ci:8.2f} {mean - ci:7.2f} {mean + ci:7.2f}  {str(mean - ci > 0):<9} {secs:5.2f}")
    excluded = sum(1 for m, c in zip(means, cis) if m - c > 0)
    print(f"CI excludes zero in {excluded}/{len(means)} seeds")
    print(f"mean of {len(means)} seed means: {sum(means) / len(means):.2f} BB/100 "
          f"(min {min(means):.2f}, max {max(means):.2f})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hands", type=int, default=HANDS, help="hands per seed (default %(default)s)")
    main(hands=parser.parse_args().hands)
