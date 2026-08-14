# PokerEngine — Project Summary & Resume-Ready Contributions

A multi-agent poker (No-Limit Hold'em) simulation engine built in Python with
a C-accelerated hand evaluator, four behaviorally distinct AI agents, and a
from-scratch betting engine — built for measuring long-run edge (BB/100)
across different decision-making strategies under real game rules.

---

## 1. What this project is

- **Four agent personalities**, each a genuinely different decision-theoretic
  approach, not parameter variations of one algorithm:
  - `Fish` — loose-passive, driven by a legacy heuristic scorer with
    intentionally preserved quirks (a real personality, not a bug-riddled one).
  - `Grinder` — tight-aggressive, driven by the standard Chen formula.
  - `QuantGrid` / `Whale` — real-time Monte Carlo win-probability estimation
    feeding a Kelly Criterion capital-allocation model, with distinct
    risk/aggression profiles (fractional vs. full Kelly, sizing variance).
- **A from-scratch No-Limit Hold'em rules engine**: shuffled dealing, pot
  management with correct raise semantics and the odd-chip-split rule, seat
  rotation and blind assignment, a betting-round state machine, and showdown
  hand comparison.
- **A C-accelerated evaluator** for the Monte Carlo hot path, integrated via
  ctypes FFI with an automatic pure-Python fallback.
- **A statistics layer** (BB/100 with 95% confidence intervals) for turning
  raw simulation output into a trustworthy performance claim.
- **A 180-test regression suite**, every assertion traceable to an
  independently-verified reference value or a live-derived case, not an
  invented "expected" number.

---

## 2. Resume-level contributions

Framed as standalone, quantified bullets — pick and adapt per role/target.

**Systems design & engineering**
- Designed and built a multi-agent decision-making simulation engine in
  Python from the ground up, including a rules engine, four independent
  agent strategies, and a statistical evaluation layer.
- Architected core game-state primitives (dealer, pot manager, seat
  rotation, ledger) as independently unit-testable components *before*
  integrating them, isolating correctness of each piece from correctness
  of the whole.
- Designed an N-general betting-round state machine using a closure
  predicate over live/actionable participants, rather than hardcoding
  two-player alternation — the same code path is provably correct for
  more than two participants without modification.
- Built a formal, hand-derived proof (not just tests) that a chip-tracking
  invariant held under the system's stated constraints, closing off an
  entire class of bugs (unequal all-in settlement) as structurally
  unreachable rather than merely untested.

**Performance engineering**
- Identified that a Monte Carlo simulation loop spent >96% of its runtime
  in a single hot-path function, then designed and shipped a narrow C
  extension (via ctypes FFI, with an automatic pure-Python fallback) that
  measured a **12.6x speedup** — cutting a 100,000-hand simulation
  projection from an estimated 31–34 hours to a measured ~2.62 hours.
- Diagnosed a secondary, non-obvious performance cost (FFI marshaling
  overhead dominating the accelerated function's own remaining runtime)
  through targeted micro-benchmarking, distinguishing it from the
  underlying computation cost.

**Testing, verification, and quality rigor**
- Grew a test suite from a single placeholder file to 187 passing tests,
  each assertion independently re-derived from first principles rather
  than trusted from a supplied "expected" value — this practice caught
  multiple incorrect reference values before they became silent bugs.
- Designed a statistically-powered behavioral regression test and
  **proved its discriminating power empirically**: deliberately injected
  a realistic logic-inversion bug into an agent, confirmed the correct
  implementation cleared a statistically significant edge while the
  broken one collapsed to a large negative result under the identical
  seed and hand count — rather than shipping a test that would pass
  against either version. The test is committed and runs on every suite
  invocation (`test_grinder_beats_fish_over_20000_hands`), not as a
  one-time check.
- Produced the project's first statistically validated head-to-head
  performance result from the simulation engine: a tight-aggressive
  agent strategy outperformed a loose-passive one by an average of 23.7
  BB/100 across 10 independently seeded 20,000-hand simulations
  (per-seed means ranged 12.0–37.7; every seed's own 95% CI excluded
  zero, though the weakest seed's lower bound cleared it by only 0.3
  BB/100) — isolated to decision policy alone, since both agents played
  through the identical rules engine.
- Found and fixed a silent infinite-loop risk in a betting-round state
  machine *before* it could affect an unattended, multi-thousand-hand
  automated simulation run — the class of bug that is cheap to fix in
  isolation and extremely expensive to diagnose mid-run.
- Diagnosed a subtle randomness-reproducibility bug in a simulation
  harness (state leaking from an unseeded global RNG, distinct from a
  correctly-seeded local one) through direct empirical demonstration,
  then fixed it across every randomness source in the pipeline and
  locked the fix behind a committed regression test that fails if
  reproducibility ever breaks
  (`test_same_seed_reproduces_cards_and_outcomes`).

**Debugging & root-cause analysis**
- Traced a multi-step state-machine edge case (an intentionally
  malformed agent action) through live instrumentation to produce an
  exact, reproducible execution trace, distinguishing a benign
  convergent edge case from a genuine unbounded-loop risk that shared
  surface-level symptoms.
- Found a latent bug where mathematically correct logic (a capital
  allocation formula) was silently fed an input with no real data
  source behind it — output that "looked plausible" was in fact
  disconnected from any real computation.

**Technical documentation & engineering process**
- Maintained a living technical specification and a running "known
  bugs" ledger across a multi-session project, ensuring every fix was
  traceable to a specific commit and a specific piece of verified
  evidence.
- Authored structured session-handoff documentation enabling clean
  continuation of a complex, multi-stage engineering effort across
  separate work sessions with no loss of context or rationale.

---

## 3. Suggested one-liner (for a resume's project list)

> Built a multi-agent poker simulation engine (Python + C/FFI) with four
> distinct AI decision strategies, a from-scratch rules engine, and a
> statistically-verified performance layer; profiled and accelerated the
> Monte Carlo evaluation hot path 12.6x via a custom C extension.
