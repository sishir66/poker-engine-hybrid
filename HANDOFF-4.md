# PokerEngine — Session Handoff #4

Supersedes `HANDOFF-3.md` for anything they disagree on (same convention
`HANDOFF-3.md` used against `HANDOFF-2.md`). Attach alongside
`HANDOFF-3.md`, `HANDOFF-2.md`, `PokerEngine_Blueprint.md`, and `CLAUDE.md`.

`HANDOFF-3.md`'s content on Stages 0 through 2 (cache/tie-bug fixes, the
narrow C evaluator, the four Stage 1 primitives, the betting loop/hand
state machine/Showdown, the size==0 raise-floor fix) is **unchanged and
still authoritative.** This document covers Stage 3: implemented this
session, plus one correction to a specific number `HANDOFF-3.md` got
wrong.

---

## 1. Current state

| Component | State |
|---|---|
| Everything through `HANDOFF-3.md` §1's table | Unchanged, still true |
| Phase IV Stage 3 (multi-hand session loop) | **Done.** `src/engine/session.py`. See §2. |
| Test suite | **187 tests**, all passing (`tests/test_engine.py`, `tests/test_dealer.py`, `tests/test_hand_runner.py`, `tests/test_session.py`) |
| Equity-cache decision (`HANDOFF-3.md` §3, deferred to Stage 3 verification) | **Closed.** No cache needed — see §2. |

---

## 2. Stage 3 — multi-hand session loop

`src/engine/session.py`, `run_session(agents, table, engine, num_hands,
seed=None, ledger=None, return_hand_details=False)`. Heads-up only,
matching `play_hand()`'s own scope — same exclusions as
`HANDOFF-3.md` §4 (no min-raise escalation, no N>2, no side pots).
`play_hand()`/`Table`/`Dealer`/`Ledger` needed zero changes.

**Global RNG seeding — the fix `HANDOFF-3.md` §3 scoped, now built and
re-demonstrated.** All four agents' `decide()` dice rolls read global
`random`; `calculate_win_odds()`'s Monte Carlo reads global `np.random`.
Seeding only the injected `Dealer` rng does not make a session
reproducible. Re-demonstrated live this session (not just cited from
last session's throwaway script): two same-seed runs with Dealer-only
seeding matched hole/community cards for hands 0-1, then diverged
starting hand 2 — offset by exactly one hand's worth of dealing from
there on, because how many streets a hand goes to (and therefore how
many cards get burnt/dealt) depends on agent decisions, and those
decisions read global random state that wasn't reset between runs.

Fixed by `random.seed(seed)` / `np.random.seed(seed)` at the top of
`run_session()`. One deliberate deviation from `HANDOFF-3.md`'s literal
wording: the `Dealer`'s own rng is `random.Random(random.getrandbits(64))`
drawn from the now-seeded global, not `random.Random(seed)` directly.
The literal reading would start the deck shuffle from the identical
MT19937 state the global generator starts from — correlating the cards
dealt with the first decisions made on them, in a project whose entire
output is a measured statistical edge. Drawing the dealer seed from the
freshly-seeded global keeps full reproducibility (same `seed` → same
`getrandbits(64)` → same deck) while decorrelating the two streams.
Re-verified with real `Grinder`/`Whale` (exercising both global sources):
cards and deltas identical across every hand at a fixed seed
(`tests/test_session.py::TestReproducibility::test_same_seed_reproduces_cards_and_outcomes`).

**`return_hand_details` parameter, not a fixed return shape.** Default
`False` → `{"totals": {...}, "num_hands": N}`, O(1) memory regardless of
hand count — this is what a 100k-hand production run uses. `True` also
returns `"hands"`: a list of `play_hand()`'s own result dicts, unmodified,
plus that hand's button seat (read before `rotate_button()`, since
`play_hand()` itself never rotates). No change to `play_hand()`'s
contract — `run_session()` only chooses what to retain from what it
already returns. `ledger` is strictly optional side-channel
instrumentation: passed straight through to `play_hand()`'s existing
`if ledger is not None` guard, never constructed internally, never
queried via `bb_per_100()` from inside `run_session()`. `totals` is
summed from `deltas` directly, independent of whether a `Ledger` exists.

**Behavioral-test redesign, carried over from `HANDOFF-3.md` §3
unchanged in substance:** a symmetric self-play test (e.g. `Fish` vs
itself) has no power — a fold/raise inversion applied identically to
both sides still averages ~0. Replaced with a directional-edge test:
`Grinder` vs `Fish`, asserting `Grinder`'s `bb_per_100` mean is positive
with a 95% CI excluding zero, `Fish`'s is negative.

**A specific number in `HANDOFF-3.md` §3 did not replicate — this is the
correction this document exists to make.** `HANDOFF-3.md` claimed 5000
was "the smallest of `{500, 2000, 5000, 20000}` tried where the correct
implementation's CI first excludes zero." Re-derived this session via a
10-seed sweep rather than trusted: at `n=5000`, the *mean* was positive
in 10/10 seeds (the directional edge itself is real and was never in
question) but the CI excluded zero in only 3/10. `n=10000` was still
only 5/10. `n=20000` was 10/10. The 5000 figure was one seed's outcome
from a prior throwaway script, not a property of the sample size — a
different seed at n=5000 would have failed this session's own test on
first run (and did, before the fix: `seed=2026` → `11.82 ± 24.52`, CI
does not exclude zero).

**The full 10-seed table at `n=20000`** — 10/10 excludes zero, but not
uniformly comfortable:

| seed | mean | ±CI | lower | upper | excludes 0 | secs |
|---|---|---|---|---|---|---|
| 1 | 23.07 | 12.26 | 10.82 | 35.33 | True | 1.84 |
| 2 | 12.02 | 11.74 | **0.28** | 23.75 | True | 1.84 |
| 3 | 24.92 | 12.55 | 12.37 | 37.47 | True | 1.85 |
| 42 | 27.81 | 12.56 | 15.26 | 40.37 | True | 1.86 |
| 99 | 25.67 | 12.32 | 13.35 | 37.99 | True | 1.86 |
| 123 | 17.16 | 11.75 | 5.41 | 28.91 | True | 1.86 |
| 555 | 37.74 | 12.67 | 25.07 | 50.41 | True | 1.87 |
| 777 | 28.55 | 12.71 | 15.84 | 41.26 | True | 1.89 |
| 1000 | 21.63 | 11.88 | 9.76 | 33.51 | True | 1.88 |
| 2026 | 17.99 | 11.93 | 6.06 | 29.92 | True | 1.88 |

Mean-of-means across the 10 seeds: **23.66 BB/100** (per-seed means
range 12.02–37.74). Seed 2's lower bound (0.28) sits essentially at the
zero boundary, not comfortably clear like the other 9 — "10/10 excludes
zero" is true but should not be read as uniformly robust. **Runtime:
measured at ~1.84–1.89s per 20000-hand run**, not "well under a
second" — that estimate was for the superseded n=5000 design and does
not carry forward; Fish/Grinder still never call
`calculate_win_odds()`, so the ~4x runtime increase from n=5000 is
purely from 4x more hands, not a new cost source.

**Test uses `n=20000`, `seed=555`.** 555 is pinned purely for
reproducibility — same convention as `tests/test_hand_runner.py`'s
200-hand chip-conservation sweep pinning `seed=42` — **not** because
it's representative: 555's 37.74 sits well above the 23.66 mean-of-means,
among the strongest of the 10 seeds tested. The resume-facing headline
number (`resume_additions.md`) cites the 10-seed aggregate (23.7 BB/100,
range 12.0–37.7), not seed 555's individual result, for exactly this
reason.

Re-proved the test's power at the pinned seed, live, not carried
forward from `HANDOFF-3.md`'s (now-superseded) numbers — this
demonstrates discriminating power, not the headline edge size:
```
CORRECT Grinder vs Fish, n=20000, seed=555:   grinder =   37.74 +/-  12.67   CI excludes 0: True
INVERTED Grinder vs Fish, n=20000, seed=555:  grinder = -257.95 +/-  61.05   CI excludes 0: True   sign flipped: True
```

**Equity-cache decision, closed by measurement (`HANDOFF-3.md` §3
explicitly deferred this to Stage 3's verification).** Real
`QuantGrid`-vs-`Whale` session, 200 hands, both agents calling
`calculate_win_odds()` on every decision: measured **61.3 ms/hand**,
under Stage 0.5's ~94 ms/hand ceiling. Projects **~1.70 hr for 100k
hands** vs. the ~2.62 hr ceiling. No preflop equity cache needed —
measured, not estimated.

---

## 3. Test suite

**187 tests**, all passing — 180 from `HANDOFF-3.md` plus 7 new in
`tests/test_session.py`:
- `TestReproducibility` (2): same-seed reproduces cards+outcomes;
  different seed diverges (guards the first from passing vacuously).
- `TestButtonRotation` (1): button alternates every hand, both agents
  scripted to fold.
- `TestTotals` (1): `totals` equals an independent recompute of summed
  per-hand deltas, and is zero-sum.
- `TestDefaultReturnShape` (1): default return is exactly
  `{"totals", "num_hands"}` — pins the O(1)-memory contract.
- `TestLedgerOptional` (1): `ledger=None` and a real `Ledger` produce
  identical `totals`.
- `TestBehavioralEdge` (1): `test_grinder_beats_fish_over_20000_hands`.

Full suite: 187 passed, 6.57s.

---

## 4. Explicitly deferred — unchanged from `HANDOFF-3.md` §4

Full no-limit min-raise escalation, N>2 seats, side-pot logic. Still no
stage number attached to any of these.

---

## 5. How we work — carry this into the new chat

Everything in `HANDOFF-3.md` §5 still applies, unchanged, including the
"paste the actual terminal output, never a summary" rule and
independent verification of every claimed value. This session is itself
an example of why that rule exists: `HANDOFF-3.md`'s 5000-hand claim
looked plausible, was previously demonstrated once, and still didn't
hold up under a fresh 10-seed re-derivation. Treat any number in a prior
handoff — including this one's own claimed values, e.g. the ms/hand
figures — as a hypothesis to re-verify before load-bearing use, not
carried-forward fact.

---

## 6. First message for the new chat

> Continuing PokerEngine. Attached: HANDOFF-4.md, HANDOFF-3.md,
> HANDOFF-2.md, PokerEngine_Blueprint.md, CLAUDE.md. Phase IV Stage 3
> (multi-hand session loop) is done — `src/engine/session.py`, global RNG
> seeding fix, Grinder-vs-Fish directional-edge behavioral test at
> n=20000 (not HANDOFF-3.md's originally-scoped 5000, which didn't
> replicate — see HANDOFF-4.md §2), equity-cache decision closed by
> measurement (no cache needed). 187 tests passing. Read HANDOFF-4.md
> first for what changed, then HANDOFF-3.md/HANDOFF-2.md for everything
> still authoritative. No stage is currently scoped past Stage 3 — the
> deferred list (min-raise escalation, N>2, side pots) needs its own
> `/plan` round if picked up.
