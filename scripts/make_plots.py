"""Regenerate docs/img/*.png: Grinder's running BB/100 over hands, and evaluator time per hand."""
import re
import statistics
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from scripts.bb100_sweep import HANDS, SEEDS
from src.engine.agent import Fish, Grinder
from src.engine.ledger import Ledger
from src.engine.session import run_session
from src.engine.simulation import PokerEngine
from src.engine.table import Table

REPO = Path(__file__).resolve().parent.parent
EVAL_RUNS = 5
OUT = Path(__file__).resolve().parent.parent / "docs" / "img"
START = 2000  # first hand shown on the running-BB/100 chart
INK, MUTED, GRID = "#1f2933", "#6b7785", "#e4e7eb"
BLUE, GRAY = "#2b6cb0", "#a0a8b3"


def style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def grinder_profits(seed):
    table = Table(["grinder", "fish"], small_blind=1, big_blind=2)
    ledger = Ledger()
    run_session({"grinder": Grinder(), "fish": Fish()}, table, PokerEngine(),
                num_hands=HANDS, seed=seed, ledger=ledger)
    return np.array(ledger.profits_bb("grinder"))  # per-hand profit in big blinds


def running_bb100(profits, every=100):
    n = np.arange(1, len(profits) + 1)
    mean = np.cumsum(profits) / n
    var = (np.cumsum(profits ** 2) - n * mean ** 2) / np.maximum(n - 1, 1)
    ci = 1.96 * np.sqrt(np.maximum(var, 0) / n)
    keep = n >= START  # the interval is very wide over the first few hundred hands
    return n[keep][::every], mean[keep][::every] * 100, ci[keep][::every] * 100


def plot_edge():
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    style(ax)
    for seed in SEEDS:
        n, mean, ci = running_bb100(grinder_profits(seed))
        ax.fill_between(n, mean - ci, mean + ci, color=BLUE, alpha=0.06, linewidth=0)
        ax.plot(n, mean, color=BLUE, linewidth=1.2, alpha=0.8)
    ax.axhline(0, color=INK, linewidth=1)
    ax.text(HANDS - 100, -4, "zero", color=INK, ha="right", va="top", fontsize=9)
    ax.set_xlim(START, HANDS)
    ax.set_ylim(-40, 100)
    ax.set_xlabel("hands played (x-axis starts at 2,000)", color=MUTED, fontsize=9)
    ax.set_ylabel("Grinder BB/100", color=MUTED, fontsize=9)
    ax.set_title(f"Grinder vs Fish: running BB/100, {len(SEEDS)} seeds, 95% CI band",
                 loc="left", color=INK, fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "grinder_vs_fish.png")


def eval_runs():
    """Run scripts.bench_raw_evaluator in EVAL_RUNS fresh processes; return (python_us, c_us) lists."""
    py, c = [], []
    for _ in range(EVAL_RUNS):
        out = subprocess.run([sys.executable, "-m", "scripts.bench_raw_evaluator"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout
        py.append(float(re.search(r"pure Python:\s+([\d.]+)", out).group(1)))
        c.append(float(re.search(r"C evaluator:\s+([\d.]+)", out).group(1)))
    return py, c


def plot_eval_time():
    py_runs, c_runs = eval_runs()
    for p, c in zip(py_runs, c_runs):
        print(f"  run: python {p:.1f} us, C {c:.1f} us, speedup {p / c:.1f}x")
    py_us, c_us = statistics.median(py_runs), statistics.median(c_runs)
    speedup = statistics.median(p / c for p, c in zip(py_runs, c_runs))
    print(f"median: python {py_us:.1f} us, C {c_us:.1f} us, speedup {speedup:.1f}x")
    fig, ax = plt.subplots(figsize=(5.5, 3.6), dpi=150)
    style(ax)
    bars = ax.bar(["Pure Python", "C evaluator"], [py_us, c_us], color=[GRAY, BLUE], width=0.5)
    for bar, value in zip(bars, (py_us, c_us)):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.1f} µs", ha="center",
                va="bottom", color=INK, fontsize=10)
    ax.set_ylabel("µs per 7-card hand", color=MUTED, fontsize=9)
    ax.set_ylim(0, py_us * 1.15)
    ax.set_title(f"Hand evaluation time: {speedup:.0f}x faster in C", loc="left",
                 color=INK, fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "evaluator_time.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    plot_edge()
    plot_eval_time()
    print(f"wrote {OUT}/grinder_vs_fish.png and evaluator_time.png")
