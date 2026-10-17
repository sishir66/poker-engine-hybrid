"""Time calculate_win_odds() with the C evaluator vs the pure-Python fallback."""
import random
import statistics
import time

import numpy as np

import src.engine.simulation as sim
from src.engine.c_hand_eval import AVAILABLE, evaluate_seven_py
from src.utils.card import Card

SIMS = 1000
REPEATS = 7


def timed(engine, hole, board):
    engine.cache_cards = None  # defeat the equity cache
    np.random.seed(0)
    t0 = time.perf_counter()
    engine.calculate_win_odds(hole, board, num_opponents=1, simulations=SIMS)
    return time.perf_counter() - t0


def median_call(engine, hole, board):
    timed(engine, hole, board)  # warmup, excluded
    return statistics.median(timed(engine, hole, board) for _ in range(REPEATS))


def main():
    assert AVAILABLE, "build the C evaluator first: make -C src/c_core"
    engine = sim.PokerEngine()
    hole = [Card(14, 0), Card(13, 0)]
    board = [Card(2, 1), Card(7, 2), Card(9, 3)]
    c_evaluate = sim.evaluate_seven
    c_secs = median_call(engine, hole, board)
    sim.evaluate_seven = evaluate_seven_py
    py_secs = median_call(engine, hole, board)
    sim.evaluate_seven = c_evaluate
    print(f"calculate_win_odds, {SIMS} sims, median of {REPEATS} after warmup")
    print(f"  pure Python: {py_secs * 1000:8.1f} ms")
    print(f"  C evaluator: {c_secs * 1000:8.1f} ms")
    print(f"  speedup:     {py_secs / c_secs:8.1f}x")


if __name__ == "__main__":
    main()
