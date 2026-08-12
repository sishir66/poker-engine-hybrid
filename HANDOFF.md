# PokerEngine Handoff — 2026-08-11

Reference alongside `PokerEngine_Blueprint.md`. Blueprint has design spec and full rationale; this file has current state, open work, blockers, and resume instructions.

A separate design doc — Phase IV scoping (environment execution / BB/100 simulation loop) — exists in this session's plan history but is not yet committed to the repo. It covers: cache/tie bugs (fixed, Stage 0), the narrow C hand evaluator (fixed, Stage 0.5), Stage 1's primitives (fixed, see below), the reset-stacks MVP model, side-pot analysis, and a full build order (Stages 1–3). Not reproduced here; ask for it if resuming this thread without that context.

**Building the C evaluator requires one manual step this doc can't automate:** `cd src/c_core && make`. Without it, `calculate_win_odds()` falls back to pure Python automatically (no crash) — it's just slow, and the new differential tests skip rather than fail.

---

## Repo state

Branch: `main`.
Last commit: `2c630a1` — Add Stage 1 primitives: dealer, pot manager, table, ledger, check_tilt() tests.

```
2c630a1 Add Stage 1 primitives: dealer, pot manager, table, ledger, check_tilt() tests
3888071 Add narrow C hand evaluator for calculate_win_odds()'s inner loop
335db89 Fix calculate_win_odds() cache/tie bugs; unify decide(); add Card.__hash__
77fac5f Fix Agent.from_dict() TypeError on Fish/Grinder/QuantGrid/Whale
3ae4629 Fix PokerEngine.__init__ crash on missing model files
67a212d Mark tilt-compounding bug fixed in Blueprint §10
57087ce Fix tilt-aggression compounding bug via base_aggression field
b316d7a Document Agent.from_dict()/subclass __init__ mismatch in Blueprint §10
f716183 Add proportion-bound ratio tests for QuantGrid/Whale thresholds
3dc95bc Update HANDOFF.md — test suite closed out, tilt wiring next
a33b26a Convert manual verification into tests/test_engine.py (99 tests)
eaec61e Fix stale calculate_win_odds() status in Blueprint §4.5/§8; add missing §10 row
5f5e023 Update HANDOFF.md and Blueprint §5.6/§10 — Whale closed out
3242717 Implement Whale (Blueprint §5.6) — deep-stack maniac, full Kelly
9b44ff4 Add clamp_to_bankroll() and apply to Fish, Grinder, QuantGrid
ad155b5 Update HANDOFF.md and Blueprint §5.5/§10 — QuantGrid Option B closed
6c31c50 Wire QuantGrid.decide() to calculate_win_odds() (Option B)
1fef0a4 Update HANDOFF.md and Blueprint §10 — calculate_win_odds() closed
3b4e339 Fix calculate_win_odds() dead feature_matrix block
7139452 Add HANDOFF.md — session state, blockers, and resume instructions
11f3fe3 Document QuantGrid Kelly/win_odds structural disconnect (audit 2026-08-02)
1599d89 Add QuantGrid placeholder (Chen scoring + Kelly-scaled sizing)
cb02644 Implement Grinder score_hand()/decide()
182add5 Remove unconditional fold bug from Fish.decide()
990f234 Adjust Fish's double-penalty threshold to exclude A9o
17d12f6 Implement Fish.score_hand() using patched legacy heuristic
cd14d2f Implement standard Chen formula (K=8, true-rank gap distance)
c402e4a Implement Chen formula preflop scoring
6839ce3 Fix generate_dataset.py import-time execution bug
3d443be Add get_hand_key(), rewire get_best_hand() and win_odds comparison
186a11d Restructure into src/ layout, scaffold Agent base class
a7e565d Initial commit: Modular architecture layout
```

The original three-item priority list from several sessions ago — `calculate_win_odds()` fix, QuantGrid Option B, Whale, test suite, tilt-compounding fix, `PokerEngine.__init__`, `Agent.from_dict()` — is fully closed. Everything from commit `335db89` onward is **Phase IV** (environment execution / BB/100 simulation): Stage 0 (correctness prerequisites), Stage 0.5 (narrow C hand evaluator), and now Stage 1 (dealer/pot/table/ledger/`check_tilt()`-test primitives) — not a continuation of the original list.

---

## What's complete

| Component | File | Notes |
|---|---|---|
| Chen preflop formula | `src/engine/preflop.py` | K=8, true-rank gap (Ace=14), no wheel exception. AA=20, AKs=12, AKo=10, 77=7, 72o=0. |
| Kelly fraction | `src/engine/risk.py` | `f* = (b*p - q) / b`, clamped at 0. |
| `Agent` base class | `src/engine/agent.py` | `check_tilt()` implemented, compounding bug fixed (`base_aggression` field, commit `57087ce`), now with standalone unit test coverage (commit `2c630a1`) — still not wired into any `decide()` (see below). `to_dict()`/`from_dict()` now work on all four subclasses too (`_restore_state()` helper, commit `77fac5f`) — `QuantGrid.from_dict(d, engine)`/`Whale.from_dict(d, engine)` require an explicit `engine` arg. `decide()` unified to `decide(pot_size, cost_to_call, min_raise, bankroll)` across all four agents (commit `335db89`) — the dead `win_odds` param Fish/Grinder never read is gone. |
| `Fish` | `src/engine/agent.py` | Legacy heuristic with intentional biases preserved. See Blueprint §4.3. `decide()` signature updated, commit `335db89` — behavior unchanged. |
| `Grinder` | `src/engine/agent.py` | Chen formula, tight-aggressive thresholds. `decide()` signature updated, commit `335db89` — behavior unchanged. |
| `QuantGrid` | `src/engine/agent.py` | Option B implemented (commit `6c31c50`, 2026-08-07). Computes `win_odds` internally via `calculate_win_odds()`; decisions gated on `kelly_f` magnitude, not Chen score. See Blueprint §5.5. |
| `Whale` | `src/engine/agent.py` | Implemented (commit `3242717`, 2026-08-07). Same real-`win_odds` signal as QuantGrid; fold floor slightly looser (`kelly_f < 0.03` vs `0.05`), recklessness expressed in sizing (`aggression=1.2` × random band), not continuance. See Blueprint §5.6. |
| Bankroll clamp (`clamp_to_bankroll()`) | `src/engine/risk.py` | Added (commit `9b44ff4`, 2026-08-07). Applied to Fish/Grinder/QuantGrid/Whale — no agent can wager more than its bankroll. |
| Hand evaluator (`get_hand_key()`) | `src/engine/simulation.py` | Tuple-based, kicker-aware, deterministic. MLP retired from the eval path. |
| `PokerEngine.__init__` no longer crashes on missing model files | `src/engine/simulation.py` | Fixed (commit `3ae4629`, 2026-08-09). Load wrapped in try/except (FileNotFoundError, OSError); `self.model`/`self.scaler` set to `None` on failure. Confirmed unused elsewhere in the repo. |
| Dataset generation import fix | `src/models/generate_dataset.py` | `if __name__ == "__main__":` guard added (commit 6839ce3). |
| `calculate_win_odds()` cache-key and tie-split fixes | `src/engine/simulation.py` | Fixed (commit `335db89`, 2026-08-10). Cache identity now includes `num_opponents`/`simulations`. Tie handling extracted into `_showdown_credit(our_key, opp_keys)`, crediting `1/k` for the actual number of players sharing the winning hand — not a blanket `num_opponents+1` divisor, which is wrong for a partial tie. |
| `Card.__hash__` | `src/utils/card.py` | Added (commit `335db89`) — needed by the dealer's dealt-card tracking; now actually used, see `tests/test_dealer.py`'s uniqueness checks. |
| C hand evaluator | `src/c_core/hand_eval.c`, `src/engine/c_hand_eval.py` | Added (commit `3888071`, 2026-08-11). `evaluate_seven()` replaces `calculate_win_odds()`'s Python `Hand`/`get_hand_key()` evaluation only — nothing else touched, `get_best_hand()` still uses `Hand` directly. Pure-Python fallback (`evaluate_seven_py`) when the gitignored `.so` isn't built (`make` in `src/c_core/` builds it). Measured 12.6x speedup per hand, ~2.62 hrs projected for 100k heads-up hands. |
| `Dealer` | `src/engine/dealer.py` | Added (commit `2c630a1`, Phase IV Stage 1). No-replacement shuffled-deck service — `deal()`, `deal_hole_cards()`, `burn_and_deal()`, `cards_remaining()`. Injectable `rng`, defaults to an unseeded `random.Random()`. Verified: zero duplicate cards across a full N=6 hand including burns; over-dealing raises `ValueError`. |
| `PotManager` | `src/engine/pot.py` | Added (commit `2c630a1`, Phase IV Stage 1). Cumulative per-player contribution tracking (raise-TO semantics — `set_contribution()` takes a new running total, not an increment; decreasing raises `ValueError`). `amount_to_call()`/`total_pot()`/`highest_contribution()`. `split_pot()` implements the odd-chip-to-first-clockwise rule as pure arithmetic — does NOT do hand comparison (that's Stage 2's Showdown component). Verified: full betting-sequence trace, odd 3-way split with the remainder landing correctly even when the button seat itself isn't a winner, chip conservation. |
| `Table` | `src/engine/table.py` | Added (commit `2c630a1`, Phase IV Stage 1). N-ready seat rotation — `seat_after()`, `blind_seats()` (heads-up special-cased: button posts small blind directly; 3+ seats: two seats clockwise from button), `rotate_button()`. Verified for 2/4/6 seats plus full rotation cycles. |
| `Ledger` | `src/engine/ledger.py` | Added (commit `2c630a1`, Phase IV Stage 1). Per-agent BB/100 with a 95% CI (`bb_per_100()`); raises below 2 recorded hands (a 1-hand estimate has no defined error bar). Verified: CI narrows from a 10-hand to a 1000-hand identical-distribution synthetic sequence. |
| `check_tilt()` test coverage | `tests/test_engine.py` | Added (commit `2c630a1`, Phase IV Stage 1). All 8 hand-derived cases (no-loss, exact-boundary-exclusive, trigger, cooldown countdown/completion, re-tilt-mid-cooldown non-compounding, `bankroll==0`, winning-while-tilted) now covered against base `Agent`, discharging the long-standing file-level `TODO`. Still not wired into any `decide()` — see below. |
| Test suite | `tests/test_engine.py`, `tests/test_dealer.py` | 166 tests, all passing. `tests/test_dealer.py` is new (Phase IV Stage 1) — the dealer has no natural home in `test_engine.py`'s existing hand-evaluation/agent-logic groups. |

---

## What's in progress (committed but explicitly temporary or incomplete)

**`check_tilt()` — compounding bug fixed, now unit-tested, but still not wired into `decide()`.**
`src/engine/agent.py`. Trigger logic (>50% single-hand loss, `aggression = base_aggression * 1.5`, 10-hand cooldown) is correct, no longer compounds across repeated tilt episodes (commit `57087ce`), and now has standalone test coverage (commit `2c630a1`). But no agent's `decide()` reads `is_tilted`/`aggression` from a tilt-adjusted state, because no hand-resolution orchestration loop exists yet — that's Phase IV Stage 2, not started (see below). Wiring is blocked on that loop existing, not unprioritized.

**Phase IV Stage 1's four primitives (`Dealer`/`PotManager`/`Table`/`Ledger`) are independently correct but not integrated with each other or with `Agent`.** No betting loop calls any of them yet. That integration is Stage 2's job.

---

## What's not started (intentional, queued)

| Item | Why not started |
|---|---|
| Position-aware `decide()` for all agents | Noted in `Agent` base class docstring. Not designed yet. |
| Phase IV Stage 2 — betting loop / hand state machine | First stage requiring integration between Stage 1's primitives. Also where `check_tilt()` gets its first real call site and where Showdown (hand comparison + pot award) gets built. Not started. |

---

## Blockers and next steps (in order)

### ~~1. Fix `calculate_win_odds()`~~ — **DONE (2026-08-03, commit `3b4e339`)**

### ~~2. Wire QuantGrid to `calculate_win_odds()`~~ — **DONE (2026-08-07, commit `6c31c50`)**

### ~~3. `Whale` implementation~~ — **DONE (2026-08-07, commit `3242717`)**

### ~~4. `tests/test_engine.py` conversion~~ — **DONE (2026-08-07, commit `a33b26a`; proportion-bound tests added `f716183`)**

### ~~5. Fix tilt-aggression compounding bug~~ — **DONE (2026-08-08, commit `57087ce`)**

### ~~6. `PokerEngine.__init__` crash on missing model files~~ — **DONE (2026-08-09, commit `3ae4629`)**

### ~~7. `Agent.from_dict()` TypeError on all four subclasses~~ — **DONE (2026-08-09, commit `77fac5f`)**

### ~~8. Phase IV Stage 0 — cache/tie/hash/decide() correctness fixes~~ — **DONE (2026-08-10, commit `335db89`)**

### ~~9. Phase IV Stage 0.5 — narrow C hand evaluator~~ — **DONE (2026-08-11, commit `3888071`)**

### ~~10. Phase IV Stage 1 — dealer, pot manager, table/rotation, ledger, standalone check_tilt() unit test~~ — **DONE (2026-08-11, commit `2c630a1`)**

Four independently-testable primitives, no integration between them: `Dealer` (`src/engine/dealer.py`), `PotManager` (`src/engine/pot.py`), `Table` (`src/engine/table.py`), `Ledger` (`src/engine/ledger.py`), plus standalone `check_tilt()` test coverage in `tests/test_engine.py` (new `tests/test_dealer.py` for the dealer). All verified with real printed output (betting-sequence traces, odd-split arithmetic, blind-seat assignment, CI narrowing, before/after tilt state) in addition to the 166-test suite passing. See Blueprint §8/§10 for full detail.

### 11. Next — Phase IV Stage 2 (betting loop / hand state machine)

First stage requiring integration between Stage 1's primitives. Wires `Dealer`/`PotManager`/`Table` together into an actual hand, builds Showdown (hand comparison + pot award using `PotManager.split_pot()`), and gives `check_tilt()` its first real call site (once per agent, after a hand resolves). Not started.

Separately, still open:
- `generate_boats()` indentation bug (Low priority, dataset-gen only).

---

## Non-obvious constraints — read before touching anything

- **Never add `Co-Authored-By: Claude` to commits.** See `CLAUDE.md`.
- **Fish's biases are intentional, not bugs.** `low_card = min(r1, r2)` returning the low card, and `rank % 14` Ace wrap on A2–A9, are preserved from the original heuristic on purpose. Only AK/AQ/AJ/AT were patched. See Blueprint §4.3.
- **`get_hand_key()` tuple comparison is the canonical hand evaluator everywhere except `calculate_win_odds()`'s inner loop, which uses `evaluate_seven()` (`src/engine/c_hand_eval.py`) instead.** `evaluate_seven()` returns a FIXED, zero-padded 6-tuple — safe to compare against other `evaluate_seven()` output, **not safe to compare against `get_hand_key()`'s raw variable-length output without truncating first** (Python tuple equality requires matching length). `get_best_hand()` still uses `Hand`/`get_hand_key()` directly and was deliberately not touched.
- **The C evaluator's `.so` isn't committed — `cd src/c_core && make` once to get the speed benefit.** Without it, `calculate_win_odds()` falls back to `evaluate_seven_py()` automatically (no crash, just slow). The differential tests (`TestCEvaluatorDifferential`) skip, not fail, when the library isn't built.
- **ctypes marshaling, not the C call itself, is `evaluate_seven_c()`'s dominant cost (~59% of its own time is array construction).** Measured, not fixed — flagged as a candidate follow-up if Stage 2's real hand-volume ever shows this mattering.
- **QuantGrid's Chen score is now vestigial.** `score_hand()` still calls `chen_score()` and caches it, but `decide()` (Option B) no longer reads it — decisions are gated on `kelly_f` magnitude instead.
- **All four agents now share one `decide(pot_size, cost_to_call, min_raise, bankroll)` signature** (commit `335db89`). The remaining, still-real divergence: `QuantGrid.__init__(self, engine)`/`Whale.__init__(self, engine)` take a `PokerEngine` instance that Fish/Grinder don't.
- **Whale's recklessness is sizing-only, not continuance.** Fold floor (`kelly_f < 0.03`) is only slightly looser than QuantGrid's (`0.05`); don't loosen continuance logic further to express "maniac" — that belongs in `aggression`/random-band sizing.
- **`clamp_to_bankroll()` (`risk.py`) must be applied OUTERMOST** — after any `max(min_raise, ...)` flooring in a sizing expression, never before.
- **`check_tilt()` is unit-tested now but still not wired into any `decide()`.** Don't add tilt-adjusted behavior tests against `decide()` until Stage 2's orchestration loop exists and wiring happens.
- **`QuantGrid.from_dict()`/`Whale.from_dict()` require an explicit `engine` argument** (`from_dict(d, engine)`) — `engine` is a live runtime dependency, not serialized state; it can't be recovered from the dict alone.
- **`calculate_win_odds()`'s cache key includes `num_opponents` and `simulations` now, not just the hole/board cards.** Any new parameter that changes the result needs to go in the cache key too.
- **Multiway tie credit is `_showdown_credit()`, not a manual divisor.** Don't reintroduce a `1/(num_opponents+1)`-style blanket split anywhere in the equity path — it's wrong for a partial tie.
- **`_showdown_credit()` returns a probability fraction, not a chip split.** Don't reuse it for `PotManager`'s pot-award logic — those are different problems (a probability fraction like `1/3` vs. an integer chip split like `33/33/34`).
- **`PotManager.contribution()` is a CUMULATIVE total for the entire hand, never reset per street.** `amount_to_call()` is correct as written specifically because a betting round can't close until every live player's contribution already equals `highest_contribution()` — it naturally reads 0 at the start of each new street. **Do not add a reset-between-streets method in Stage 2** — that would double-book contributions against this invariant, not preserve it.
- **`PotManager.split_pot()` does chip arithmetic only — it does NOT compare hands.** Stage 2's Showdown component determines `winner_ids`; `split_pot()` just divides `total_pot()` among them using the odd-chip-to-first-clockwise rule. Don't fold hand-comparison logic into `pot.py`.
- **`Dealer.deal_hole_cards()` deals 2 cards to player 1, then player 2, etc. — not alternating single cards around the table.** Statistically equivalent for a properly shuffled deck; don't "fix" this to alternate, it isn't broken.
- **`Table.blind_seats()` heads-up is a real-poker special case, not a bug.** With exactly 2 seats, the button IS the small blind (posts directly); with 3+, blinds are the two seats clockwise from the button. Both branches are intentional, not a simplification to later generalize away.
- **`seaborn` is imported in `simulation.py` but not installed anywhere in the venv, and not listed in any requirements file (none exists).** `tests/test_engine.py` works around this with a test-only `sys.modules` shim — source code is untouched.
- **`PokerEngine.__init__` no longer crashes without model files, but the model/scaler are genuinely unused elsewhere.**
- **Verification bar is always: real printed output, not a summary.** Every prior implementation was confirmed with actual script output pasted back. Same standard applies going forward.

---

## Known bugs (priority order)

| Issue | Blocks | Priority |
|---|---|---|
| `calculate_win_odds()` feature_matrix never filled — output unverified | QuantGrid Option B, real Kelly sizing, test coverage | **Fixed 2026-08-03** (commit `3b4e339`) |
| QuantGrid `decide()` has no real `win_odds` source | QuantGrid evaluation | **Fixed 2026-08-07** (commit `6c31c50`) |
| `Whale` not implemented | Whale agent | **Fixed 2026-08-07** (commit `3242717`) |
| No agent's raise sizing was bounded by bankroll | All agents' sizing correctness | **Fixed 2026-08-07** (commit `9b44ff4`) |
| `tests/test_engine.py` empty — no automated regression coverage | Catching future regressions | **Fixed 2026-08-07** (commit `a33b26a`, expanded `f716183`, now 166 tests as of `2c630a1`) |
| Blueprint §4.5/§8 said the feature-matrix bug was still open, contradicting §10's "Fixed" row | Documentation accuracy | **Fixed 2026-08-07** (commit `eaec61e`) |
| Tilt aggression compounded permanently across repeated tilt episodes | Tilt correctness | **Fixed 2026-08-08** (commit `57087ce`) |
| `PokerEngine.__init__` crashed on fresh clone if model files absent | Fresh setup, running engine code without the constructor-bypass trick | **Fixed 2026-08-09** (commit `3ae4629`) |
| `Agent.from_dict()` raised `TypeError` on every subclass | Any future save/load or checkpoint functionality (Phase IV) | **Fixed 2026-08-09** (commit `77fac5f`) |
| `calculate_win_odds()`'s cache key omitted `num_opponents`/`simulations` — silently returned stale results | Phase IV equity service correctness | **Fixed 2026-08-10** (commit `335db89`) |
| `calculate_win_odds()` too slow for a trustworthy BB/100 (~31–34 hrs projected for 100k heads-up hands) | Phase IV — any real simulation run | **Fixed (narrow slice) 2026-08-11** (commit `3888071`) |
| `calculate_win_odds()`'s tie handling was hardcoded heads-up (`ties/2`) — wrong for any multiway tie | Phase IV multiway hands (N≥3) | **Fixed 2026-08-10** (commit `335db89`) |
| `Card` had `__eq__` but no `__hash__` — unhashable | Phase IV dealer (dealt-card tracking via sets) | **Fixed 2026-08-10** (commit `335db89`) |
| `Fish.decide()`/`Grinder.decide()` took an unused `win_odds` parameter | Betting-loop dispatch simplicity (Phase IV) | **Fixed 2026-08-10** (commit `335db89`) |
| `check_tilt()` trigger logic has no test coverage | Tilt wiring test coverage | **Fixed 2026-08-11** (commit `2c630a1`) — standalone unit test, still not wired |
| No dealer/pot/table/ledger primitives existed for Phase IV's betting loop | Phase IV Stage 2 (betting loop) | **Fixed 2026-08-11** (commit `2c630a1`) — Stage 1 primitives, not yet integrated |
| `check_tilt()` not wired into any `decide()` | Tilt behavior actually affecting play | Open — blocked on Phase IV Stage 2's hand-resolution loop, which doesn't exist yet |
| `generate_boats()` indentation bug in dataset generation | Dataset quality | Low — runtime not affected |
| `record_action()` / `plot_session_results()` called in old `__main__` block but never defined | Dead code cleanup | Low — confirm still referenced before fixing |

Full details in `PokerEngine_Blueprint.md §10`.
