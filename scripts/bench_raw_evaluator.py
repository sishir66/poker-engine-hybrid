"""Time evaluate_seven() alone, C vs pure Python, on 2,000 random 7-card hands."""
import random
import statistics
import time

from src.engine.c_hand_eval import AVAILABLE, evaluate_seven_c, evaluate_seven_py
from src.utils.deck import Deck

HANDS = 2000
REPEATS = 5


def per_hand_us(evaluate, hands):
    runs = []
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        for h in hands:
            evaluate(h)
        runs.append(time.perf_counter() - t0)
    return statistics.median(runs) / len(hands) * 1e6


def main():
    assert AVAILABLE, "build the C evaluator first: make -C src/c_core"
    random.seed(1)
    hands = [random.sample(Deck().cards, 7) for _ in range(HANDS)]
    evaluate_seven_c(hands[0])  # warmup, excluded
    evaluate_seven_py(hands[0])
    py_us = per_hand_us(evaluate_seven_py, hands)
    c_us = per_hand_us(evaluate_seven_c, hands)
    print(f"evaluate_seven, {HANDS} random hands, median of {REPEATS} passes after warmup")
    print(f"  pure Python: {py_us:6.1f} us/hand")
    print(f"  C evaluator: {c_us:6.1f} us/hand")
    print(f"  speedup:     {py_us / c_us:6.1f}x")


if __name__ == "__main__":
    main()
