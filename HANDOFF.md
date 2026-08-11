# PokerEngine Handoff — 2026-08-11

Reference alongside `PokerEngine_Blueprint.md`. Blueprint has design spec and full rationale; this file has current state, open work, blockers, and resume instructions.

A separate design doc — Phase IV scoping (environment execution / BB/100 simulation loop) — exists in this session's plan history but is not yet committed to the repo. It covers: cache/tie bugs (fixed, Stage 0), the narrow C hand evaluator (fixed, Stage 0.5, see below), the reset-stacks MVP model, side-pot analysis, and a full build order (Stages 1–3). Not reproduced here; ask for it if resuming this thread without that context.

**Building the C evaluator requires one manual step this doc can't automate:** `cd src/c_core && make`. Without it, `calculate_win_odds()` falls back to pure Python automatically (no crash) — it's just slow, and the new differential tests skip rather than fail.

---

## Repo state

Branch: `main`.
Last commit: `3888071` — Add narrow C hand evaluator for calculate_win_odds()'s inner loop.

```
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

The original three-item priority list from several sessions ago — `calculate_win_odds()` fix, QuantGrid Option B, Whale, test suite, tilt-compounding fix, `PokerEngine.__init__`, `Agent.from_dict()` — is fully closed. This session's commit (`335db89`) is **Phase IV Stage 0**: the first implementation stage of the new environment-execution work (see the Phase IV scoping note above), not a continuation of that original list. It fixes two bugs found *while scoping* Phase IV rather than while running the existing test suite — both were latent (no caller currently varies `num_opponents` or triggers a 3+-way tie), which is exactly why they'd gone unnoticed.

---

## What's complete

| Component | File | Notes |
|---|---|---|
| Chen preflop formula | `src/engine/preflop.py` | K=8, true-rank gap (Ace=14), no wheel exception. AA=20, AKs=12, AKo=10, 77=7, 72o=0. |
| Kelly fraction | `src/engine/risk.py` | `f* = (b*p - q) / b`, clamped at 0. |
| `Agent` base class | `src/engine/agent.py` | `check_tilt()` implemented, compounding bug fixed (`base_aggression` field, commit `57087ce`) — still not wired into any `decide()` (see below). `to_dict()`/`from_dict()` now work on all four subclasses too (`_restore_state()` helper, commit `77fac5f`) — `QuantGrid.from_dict(d, engine)`/`Whale.from_dict(d, engine)` require an explicit `engine` arg. `decide()` unified to `decide(pot_size, cost_to_call, min_raise, bankroll)` across all four agents (commit `335db89`) — the dead `win_odds` param Fish/Grinder never read is gone. |
| `Fish` | `src/engine/agent.py` | Legacy heuristic with intentional biases preserved. See Blueprint §4.3. `decide()` signature updated, commit `335db89` — behavior unchanged. |
| `Grinder` | `src/engine/agent.py` | Chen formula, tight-aggressive thresholds. `decide()` signature updated, commit `335db89` — behavior unchanged. |
| `QuantGrid` | `src/engine/agent.py` | Option B implemented (commit `6c31c50`, 2026-08-07). Computes `win_odds` internally via `calculate_win_odds()`; decisions gated on `kelly_f` magnitude, not Chen score. See Blueprint §5.5. |
| `Whale` | `src/engine/agent.py` | Implemented (commit `3242717`, 2026-08-07). Same real-`win_odds` signal as QuantGrid; fold floor slightly looser (`kelly_f < 0.03` vs `0.05`), recklessness expressed in sizing (`aggression=1.2` × random band), not continuance. See Blueprint §5.6. |
| Bankroll clamp (`clamp_to_bankroll()`) | `src/engine/risk.py` | Added (commit `9b44ff4`, 2026-08-07). Applied to Fish/Grinder/QuantGrid/Whale — no agent can wager more than its bankroll. |
| Hand evaluator (`get_hand_key()`) | `src/engine/simulation.py` | Tuple-based, kicker-aware, deterministic. MLP retired from the eval path. |
| `PokerEngine.__init__` no longer crashes on missing model files | `src/engine/simulation.py` | Fixed (commit `3ae4629`, 2026-08-09). Load wrapped in try/except (FileNotFoundError, OSError); `self.model`/`self.scaler` set to `None` on failure. Confirmed unused elsewhere in the repo. Fresh-clone crash simulated and verified fixed; win_odds benchmarks re-verified with no regression. |
| Dataset generation import fix | `src/models/generate_dataset.py` | `if __name__ == "__main__":` guard added (commit 6839ce3). |
| Test suite | `tests/test_engine.py` | 139 tests, all passing (commit `3ae4629` added `TestPokerEngineConstruction`; `77fac5f` added 5 `from_dict()` round-trip tests; `335db89` added 12 more; `3888071` added 16 more — a 20,000-hand C-evaluator differential sample, wheel/three-pair/royal-flush edge cases, one hand per rank_value category, a forced-fallback benchmark check). Covers Kelly fraction, Chen formula, Fish heuristic, hand evaluator, real `calculate_win_odds()` benchmarks (multiway, cache correctness, C-vs-Python differential), QuantGrid/Whale decision-tree thresholds (including proportion-bound ratio checks, commit `f716183`), bankroll clamp, agent serialization (base + all four subclasses), real `PokerEngine()` construction without model files, and `Card` hashability. `check_tilt()` trigger logic still explicitly excluded — see below. |
| `calculate_win_odds()` cache-key and tie-split fixes | `src/engine/simulation.py` | Fixed (commit `335db89`, 2026-08-10). Cache identity now includes `num_opponents`/`simulations` (was stale on either changing). Tie handling extracted into `_showdown_credit(our_key, opp_keys)`, crediting `1/k` for the actual number of players sharing the winning hand in that simulation — not a blanket `num_opponents+1` divisor, which is wrong for a partial tie. Found during Phase IV scoping, not by the existing test suite (both were latent). |
| `Card.__hash__` | `src/utils/card.py` | Added (commit `335db89`) — `Card` had `__eq__` but was unhashable, blocking any set/dict-key use. Needed by Phase IV's dealer (dealt-card tracking), not used anywhere yet. |
| C hand evaluator | `src/c_core/hand_eval.c`, `src/engine/c_hand_eval.py` | Added (commit `3888071`, 2026-08-11). `evaluate_seven()` replaces `calculate_win_odds()`'s Python `Hand`/`get_hand_key()` evaluation only — nothing else touched, `get_best_hand()` still uses `Hand` directly. Pure-Python fallback (`evaluate_seven_py`) when the gitignored `.so` isn't built (`make` in `src/c_core/` builds it). Verified: 20,000-hand differential test against `get_hand_key()`, 0 mismatches. Measured 12.6x speedup per hand, ~2.62 hrs projected for 100k heads-up hands (excluding a one-time warmup call from the measurement — see Blueprint §10 for the raw numbers). |

---

## What's in progress (committed but explicitly temporary or incomplete)

**`check_tilt()` — compounding bug fixed, but still not wired into `decide()`, and still has NO test coverage.**
`src/engine/agent.py`. Trigger logic (>50% single-hand loss, `aggression = base_aggression * 1.5`, 10-hand cooldown) is correct and no longer compounds across repeated tilt episodes (commit `57087ce`), but no agent's `decide()` reads `is_tilted`/`aggression` from a tilt-adjusted state, because no hand-resolution orchestration loop exists anywhere in the codebase yet (confirmed via exhaustive repo search) — that's Phase IV, Blueprint §6/§8, not started. Wiring is blocked on that loop existing, not unprioritized. A `TODO` comment at the top of `tests/test_engine.py` still flags `check_tilt()` as untested — write the wiring first, generate real reference output, *then* add tests.

---

## What's not started (intentional, queued)

| Item | Why not started |
|---|---|
| Position-aware `decide()` for all agents | Noted in `Agent` base class docstring. Not designed yet. |
| Hand-resolution orchestration loop (Phase IV) | Needed before `check_tilt()` can be wired into any `decide()`. Not started. |

---

## Blockers and next steps (in order)

### ~~1. Fix `calculate_win_odds()`~~ — **DONE (2026-08-03, commit `3b4e339`)**

### ~~2. Wire QuantGrid to `calculate_win_odds()`~~ — **DONE (2026-08-07, commit `6c31c50`)**

### ~~3. `Whale` implementation~~ — **DONE (2026-08-07, commit `3242717`)**

### ~~4. `tests/test_engine.py` conversion~~ — **DONE (2026-08-07, commit `a33b26a`; proportion-bound tests added `f716183`)**

### ~~5. Fix tilt-aggression compounding bug~~ — **DONE (2026-08-08, commit `57087ce`)**

`base_aggression` field added to `Agent`; `check_tilt()` now resets to exactly `base_aggression` on cooldown instead of compounding. Wiring into `decide()` remains blocked on the Phase IV orchestration loop (see above) — not part of this fix's scope.

### ~~6. `PokerEngine.__init__` crash on missing model files~~ — **DONE (2026-08-09, commit `3ae4629`)**

Constructor no longer crashes when `data/poker_model.pth`/`data/poker_scaler.pkl` are absent (both gitignored). Neither attribute is read anywhere else in the codebase.

### ~~7. `Agent.from_dict()` TypeError on all four subclasses~~ — **DONE (2026-08-09, commit `77fac5f`)**

Added `Agent._restore_state(d)`; each subclass's new `from_dict()` constructs itself normally, then calls it. `QuantGrid.from_dict(d, engine)`/`Whale.from_dict(d, engine)` require an explicit `engine` arg — same signature divergence already accepted for `decide()`.

### ~~8. Phase IV Stage 0 — cache/tie/hash/decide() correctness fixes~~ — **DONE (2026-08-10, commit `335db89`)**

First implementation stage of Phase IV (environment execution / BB/100 loop). Fixed `calculate_win_odds()`'s stale-cache bug and heads-up-only tie split, added `Card.__hash__`, unified `decide()` to 4-arg across all agents. See the Phase IV scoping note at the top of this file and Blueprint §10 for detail. Independent of everything else in Phase IV — pure correctness work on existing code, no new components built.

### ~~9. Phase IV Stage 0.5 — narrow C hand evaluator~~ — **DONE (2026-08-11, commit `3888071`)**

`evaluate_seven()` (`src/c_core/hand_eval.c` + `src/engine/c_hand_eval.py`) replaces `calculate_win_odds()`'s Python hand evaluation only. Measured 12.6x speedup per hand, ~2.62 hrs projected for 100k heads-up hands (within the original 1.3–2.8 hr estimate). One new finding, not acted on: ctypes marshaling is now the dominant remaining cost (~47% of total per-call time, mostly array construction) — a candidate for a future follow-up if runtime still proves insufficient once Stage 1's loop exists to measure real call volume against, not a blocker now.

### 10. Next — Phase IV Stage 1 (dealer, pot manager, table/rotation, ledger, standalone `check_tilt()` unit test)

Per the Phase IV scoping doc, Stage 1's five primitives are all independently testable and none depend on each other — any order works. The standalone `check_tilt()` unit test matters most to build early: it establishes the tilt state machine is correct *before* anything wires it into a hand-resolution loop, so a later failure in Stage 2 can only mean the loop is feeding it bad inputs, not that `check_tilt()` itself is wrong. Not started.

Separately, still open:
- `check_tilt()` wiring into `decide()` — blocked on Phase IV's hand-resolution loop, which is Stage 2, past Stage 1.
- `generate_boats()` indentation bug (Low priority, dataset-gen only).

---

## Non-obvious constraints — read before touching anything

- **Never add `Co-Authored-By: Claude` to commits.** See `CLAUDE.md`.
- **Fish's biases are intentional, not bugs.** `low_card = min(r1, r2)` returning the low card, and `rank % 14` Ace wrap on A2–A9, are preserved from the original heuristic on purpose. Only AK/AQ/AJ/AT were patched. See Blueprint §4.3.
- **`get_hand_key()` tuple comparison is the canonical hand evaluator everywhere except `calculate_win_odds()`'s inner loop, which uses `evaluate_seven()` (`src/engine/c_hand_eval.py`) instead.** `evaluate_seven()` returns a FIXED, zero-padded 6-tuple — safe to compare against other `evaluate_seven()` output, **not safe to compare against `get_hand_key()`'s raw variable-length output without truncating first** (Python tuple equality requires matching length; two equivalent hands can compare unequal purely from padding). `get_best_hand()` still uses `Hand`/`get_hand_key()` directly and was deliberately not touched. The MLP (`src/models/`) is dead code retained in the repo but bypassed entirely in the eval path — `PokerEngine.__init__` still loads it opportunistically (now non-fatally) but nothing reads `self.model`/`self.scaler` afterward.
- **The C evaluator's `.so` isn't committed — `cd src/c_core && make` once to get the speed benefit.** Without it, `calculate_win_odds()` falls back to `evaluate_seven_py()` automatically (no crash, just slow) — same pattern as the `PokerEngine.__init__` model-file fallback. The differential tests (`TestCEvaluatorDifferential`) skip, not fail, when the library isn't built.
- **ctypes marshaling, not the C call itself, is now `evaluate_seven_c()`'s dominant cost (~59% of its own time is array construction).** Measured, not fixed — flagged as a candidate follow-up if Stage 1's real hand-volume ever shows this mattering. Don't assume "it's C, so it's fast" without checking; the marshaling boundary is real overhead.
- **QuantGrid's Chen score is now vestigial.** `score_hand()` still calls `chen_score()` and caches it, but `decide()` (Option B) no longer reads it — decisions are gated on `kelly_f` magnitude instead.
- **All four agents now share one `decide(pot_size, cost_to_call, min_raise, bankroll)` signature** (commit `335db89`) — `win_odds` is gone everywhere, not just from QuantGrid/Whale. The remaining, still-real divergence: `QuantGrid.__init__(self, engine)`/`Whale.__init__(self, engine)` take a `PokerEngine` instance that Fish/Grinder don't.
- **Whale's recklessness is sizing-only, not continuance.** Fold floor (`kelly_f < 0.03`) is only slightly looser than QuantGrid's (`0.05`); don't loosen continuance logic further to express "maniac" — that belongs in `aggression`/random-band sizing.
- **`clamp_to_bankroll()` (`risk.py`) must be applied OUTERMOST** — after any `max(min_raise, ...)` flooring in a sizing expression, never before.
- **`check_tilt()`'s compounding bug is fixed, but it's still not wired into any `decide()`.** Don't add tilt-adjusted behavior tests against `decide()` until the Phase IV orchestration loop exists and wiring happens.
- **`QuantGrid.from_dict()`/`Whale.from_dict()` require an explicit `engine` argument** (`from_dict(d, engine)`) — diverges from the base `Agent.from_dict(d)` signature on purpose, same as their `__init__(self, engine)` divergence. `engine` is a live runtime dependency, not serialized state; it can't be recovered from the dict alone.
- **`calculate_win_odds()`'s cache key includes `num_opponents` and `simulations` now, not just the hole/board cards.** If you ever add a new parameter that changes the result (e.g. a rule variant), it needs to go in the cache key too — omitting one is exactly how the cache-staleness bug happened the first time.
- **Multiway tie credit is `_showdown_credit()`, not a manual divisor.** Don't reintroduce a `1/(num_opponents+1)`-style blanket split anywhere in the equity path — it's wrong for a partial tie (verified: it would give `1/3` on a case where the correct answer is `1/2`). Route any new multiway-equity code through `_showdown_credit()`.
- **`_showdown_credit()` returns a probability fraction, not a chip split.** Don't reuse it for pot-award logic when the betting loop is built — that needs its own function using the odd-chip-to-first-clockwise rule from the Phase IV design doc. A probability fraction (`1/3`) and an integer chip split (`33/33/34`) are different problems.
- **`seaborn` is imported in `simulation.py` but not installed anywhere in the venv, and not listed in any requirements file (none exists).** `tests/test_engine.py` works around this with a test-only `sys.modules` shim — source code is untouched.
- **`PokerEngine.__init__` no longer crashes without model files, but the model/scaler are genuinely unused elsewhere.** If the MLP path is ever reactivated (Blueprint §5.5 mentions it as a possible future QuantGrid input, never built), that code must check `if self.model is not None` before use.
- **Verification bar is always: real printed output, not a summary.** Every prior implementation was confirmed with actual script output pasted back. Same standard applies going forward.

---

## Known bugs (priority order)

| Issue | Blocks | Priority |
|---|---|---|
| `calculate_win_odds()` feature_matrix never filled — output unverified | QuantGrid Option B, real Kelly sizing, test coverage | **Fixed 2026-08-03** (commit `3b4e339`) |
| QuantGrid `decide()` has no real `win_odds` source | QuantGrid evaluation | **Fixed 2026-08-07** (commit `6c31c50`) |
| `Whale` not implemented | Whale agent | **Fixed 2026-08-07** (commit `3242717`) |
| No agent's raise sizing was bounded by bankroll | All agents' sizing correctness | **Fixed 2026-08-07** (commit `9b44ff4`) |
| `tests/test_engine.py` empty — no automated regression coverage | Catching future regressions | **Fixed 2026-08-07** (commit `a33b26a`, expanded `f716183`) |
| Blueprint §4.5/§8 said the feature-matrix bug was still open, contradicting §10's "Fixed" row | Documentation accuracy | **Fixed 2026-08-07** (commit `eaec61e`) |
| Tilt aggression compounded permanently across repeated tilt episodes | Tilt correctness | **Fixed 2026-08-08** (commit `57087ce`) |
| `PokerEngine.__init__` crashed on fresh clone if model files absent | Fresh setup, running engine code without the constructor-bypass trick | **Fixed 2026-08-09** (commit `3ae4629`) |
| `Agent.from_dict()` raised `TypeError` on every subclass — `Fish`/`Grinder`/`QuantGrid`/`Whale` override `__init__()` with a signature that rejects the base classmethod's kwargs | Any future save/load or checkpoint functionality (Phase IV, §6) | **Fixed 2026-08-09** (commit `77fac5f`) |
| `calculate_win_odds()`'s cache key omitted `num_opponents`/`simulations` — silently returned stale results when either changed | Phase IV equity service correctness | **Fixed 2026-08-10** (commit `335db89`) |
| `calculate_win_odds()` too slow for a trustworthy BB/100 (~31–34 hrs projected for 100k heads-up hands, nearly all in Python hand evaluation) | Phase IV — any real simulation run | **Fixed (narrow slice) 2026-08-11** (commit `3888071`) — see Blueprint §10 for measured numbers |
| `calculate_win_odds()`'s tie handling was hardcoded heads-up (`ties/2`) — wrong for any multiway tie | Phase IV multiway hands (N≥3) | **Fixed 2026-08-10** (commit `335db89`) |
| `Card` had `__eq__` but no `__hash__` — unhashable | Phase IV dealer (dealt-card tracking via sets) | **Fixed 2026-08-10** (commit `335db89`) |
| `Fish.decide()`/`Grinder.decide()` took an unused `win_odds` parameter | Betting-loop dispatch simplicity (Phase IV) | **Fixed 2026-08-10** (commit `335db89`) |
| `check_tilt()` trigger logic has no test coverage (design never exercised with confirmed printed output before wiring) | Tilt wiring test coverage | Open — Phase IV design doc specifies a standalone unit test in Stage 1, before the post-hand hook wires it in |
| `check_tilt()` not wired into any `decide()` | Tilt behavior actually affecting play | Open — blocked on Phase IV's hand-resolution loop (Stage 2), which doesn't exist yet |
| `generate_boats()` indentation bug in dataset generation | Dataset quality | Low — runtime not affected |
| `record_action()` / `plot_session_results()` called in old `__main__` block but never defined | Dead code cleanup | Low — confirm still referenced before fixing |

Full details in `PokerEngine_Blueprint.md §10`.
