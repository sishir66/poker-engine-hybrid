# PokerEngine Handoff — 2026-08-12

Reference alongside `PokerEngine_Blueprint.md`. Blueprint has design spec and full rationale; this file has current state, open work, blockers, and resume instructions.

A separate design doc — Phase IV scoping (environment execution / BB/100 simulation loop) — exists in this session's plan history but is not yet committed to the repo. It covers: cache/tie bugs (fixed, Stage 0), the narrow C hand evaluator (fixed, Stage 0.5), Stage 1's primitives (fixed), Stage 2's betting loop/Showdown (fixed, see below), the reset-stacks MVP model, side-pot analysis, and a full build order (Stages 1–3+). Not reproduced here; ask for it if resuming this thread without that context.

**Building the C evaluator requires one manual step this doc can't automate:** `cd src/c_core && make`. Without it, `calculate_win_odds()` falls back to pure Python automatically (no crash) — it's just slow, and the differential tests skip rather than fail.

---

## Repo state

Branch: `main`.
Last commit: `8faa683` — Add Stage 2: betting loop, hand state machine, and Showdown.

```
8faa683 Add Stage 2: betting loop, hand state machine, and Showdown
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

Everything from commit `335db89` onward is **Phase IV** (environment execution / BB/100 simulation): Stage 0 (correctness prerequisites), Stage 0.5 (narrow C hand evaluator), Stage 1 (dealer/pot/table/ledger/`check_tilt()`-test primitives), and now **Stage 2** (betting loop, hand state machine, Showdown) — the first stage that actually plays a hand.

---

## What's complete

| Component | File | Notes |
|---|---|---|
| Chen preflop formula | `src/engine/preflop.py` | K=8, true-rank gap (Ace=14), no wheel exception. AA=20, AKs=12, AKo=10, 77=7, 72o=0. |
| Kelly fraction | `src/engine/risk.py` | `f* = (b*p - q) / b`, clamped at 0. |
| `Agent` base class | `src/engine/agent.py` | `check_tilt()` implemented, compounding bug fixed (`base_aggression` field, commit `57087ce`), unit-tested (commit `2c630a1`), and **now wired in** (commit `8faa683`, see below). `to_dict()`/`from_dict()` work on all four subclasses (`_restore_state()` helper, commit `77fac5f`). `decide()` unified to `decide(pot_size, cost_to_call, min_raise, bankroll)` across all four agents (commit `335db89`). |
| `Fish` | `src/engine/agent.py` | Legacy heuristic with intentional biases preserved. See Blueprint §4.3. |
| `Grinder` | `src/engine/agent.py` | Chen formula, tight-aggressive thresholds. |
| `QuantGrid` | `src/engine/agent.py` | Option B implemented (commit `6c31c50`). Computes `win_odds` internally via `calculate_win_odds()`; decisions gated on `kelly_f` magnitude, not Chen score. See Blueprint §5.5. |
| `Whale` | `src/engine/agent.py` | Implemented (commit `3242717`). Same real-`win_odds` signal as QuantGrid; fold floor slightly looser, recklessness expressed in sizing. See Blueprint §5.6. |
| Bankroll clamp (`clamp_to_bankroll()`) | `src/engine/risk.py` | Applied to all four agents — no agent can wager more than its bankroll (commit `9b44ff4`, `3242717`). |
| Hand evaluator (`get_hand_key()`) | `src/engine/simulation.py` | Tuple-based, kicker-aware, deterministic. |
| `PokerEngine.__init__` no longer crashes on missing model files | `src/engine/simulation.py` | Fixed (commit `3ae4629`). |
| `calculate_win_odds()` cache-key and tie-split fixes | `src/engine/simulation.py` | Fixed (commit `335db89`). Cache identity includes `num_opponents`/`simulations`. Tie handling via `_showdown_credit(our_key, opp_keys)`, crediting `1/k` for the actual number of players sharing the winning hand. |
| `Card.__hash__` | `src/utils/card.py` | Added (commit `335db89`) — used by `Dealer`'s uniqueness checks. |
| C hand evaluator | `src/c_core/hand_eval.c`, `src/engine/c_hand_eval.py` | Added (commit `3888071`). `evaluate_seven()` replaces `calculate_win_odds()`'s Python hand evaluation only — `get_best_hand()` still uses `Hand` directly, and **Showdown (Stage 2) also uses `get_best_hand()` exclusively, never `evaluate_seven()`** — their outputs are cross-incomparable (a straight's `(4,9)` vs. `evaluate_seven()`'s zero-padded `(4,9,0,0,0,0)` compare unequal, and the unpadded one sorts lower). Pure-Python fallback (`evaluate_seven_py`) when the gitignored `.so` isn't built. Measured 12.6x speedup per hand. |
| `Dealer` | `src/engine/dealer.py` | Added (commit `2c630a1`). No-replacement shuffled-deck service — `deal()`, `deal_hole_cards()`, `burn_and_deal()`, `cards_remaining()`. Injectable `rng`. |
| `PotManager` | `src/engine/pot.py` | Added (commit `2c630a1`). Cumulative per-player contribution tracking (raise-TO semantics). `split_pot()` implements the odd-chip-to-first-clockwise rule — chip arithmetic only, no hand comparison. |
| `Table` | `src/engine/table.py` | Added (commit `2c630a1`). N-ready seat rotation — `seat_after()`, `blind_seats()`, `rotate_button()`. |
| `Ledger` | `src/engine/ledger.py` | Added (commit `2c630a1`). Per-agent BB/100 with a 95% CI (`bb_per_100()`); raises below 2 recorded hands. |
| `check_tilt()` test coverage | `tests/test_engine.py` | Added (commit `2c630a1`). All 8 hand-derived cases covered against base `Agent`. |
| **`Showdown` — `resolve_showdown()`** | `src/engine/showdown.py` | **New (commit `8faa683`, Phase IV Stage 2).** Determines the winner(s) at showdown via `engine.get_best_hand()` per contender, delegates chip arithmetic to `PotManager.split_pot()`. Verified: `get_best_hand()`'s `cache_sig` includes hole cards, so two contenders in one showdown sharing an engine instance never collide — proven, not assumed (independent recompute matches, and re-evaluating the first player after the second still returns the first player's own key). |
| **Betting loop / hand state machine — `run_betting_round()`, `play_hand()`** | `src/engine/hand_runner.py` | **New (commit `8faa683`, Phase IV Stage 2).** First code in the repo that plays an actual hand: posts blinds, sequences preflop/flop/turn/river, resolves showdown or an early fold-exit, calls `check_tilt()` on every seated agent, records to `Ledger`. Heads-up only (`assert len(table.seats) == 2`). See "Non-obvious constraints" below for the raise-increment contract and the tilt-bankroll-timing rule. |
| Test suite | `tests/test_engine.py`, `tests/test_dealer.py`, `tests/test_hand_runner.py` | 179 tests, all passing. |

---

## What's not started (intentional, queued)

| Item | Why not started |
|---|---|
| Position-aware `decide()` for all agents | Noted in `Agent` base class docstring. Not designed yet. |
| Phase IV Stage 3 — multi-hand session loop | Button rotation between hands (`play_hand()` deliberately does not rotate the button itself — that's the caller's job across a session), proper no-limit `min_raise` escalation (Stage 2 uses a flat `table.big_blind` floor as a documented simplification, not an oversight), N>2 seats (needs side-pot logic — structurally unreachable at N=2 under reset-stacks, mandatory at N≥3 with unequal stacks), explicit RNG seeding for reproducible full runs. Not started. |

---

## Blockers and next steps (in order)

### ~~1–9~~ — see `PokerEngine_Blueprint.md §10` for the full closed list through Stage 0.5 (commit `3888071`).

### ~~10. Phase IV Stage 1 — dealer, pot manager, table/rotation, ledger, standalone check_tilt() unit test~~ — **DONE (2026-08-11, commit `2c630a1`)**

Four independently-testable primitives, no integration between them.

### ~~11. Phase IV Stage 2 — betting loop, hand state machine, Showdown~~ — **DONE (2026-08-12, commit `8faa683`)**

First integration stage. `src/engine/hand_runner.py` (`run_betting_round()`, `play_hand()`) and `src/engine/showdown.py` (`resolve_showdown()`) wire `Dealer`/`PotManager`/`Table`/`Ledger` plus `Agent.decide()`/`check_tilt()` into an actual heads-up hand. Betting-round closure uses a closure predicate over live/actionable seats (`acted.issuperset(actionable) and all amount_to_call == 0`), not a hardcoded 2-player alternation — verified this correctly closes a checked-around street, reopens on a real raise, and does NOT mistakenly close or hang when an agent's raise formula undershoots the actual call amount (it just gets re-polled with an updated, smaller `cost_to_call` on its next turn — a proven, not assumed, convergence property, see `tests/test_hand_runner.py::TestClosurePredicate`). Chip conservation (`sum(deltas) == 0`, `sum(awards) == total_pot`) is asserted inside `play_hand()` on every hand, not only in tests — verified across a real seeded 200-hand Fish-vs-Grinder sweep with zero violations. See Blueprint §5.2 point 7 and §8's Stage 2 entry for full detail.

### 12. Next — Phase IV Stage 3 (multi-hand session loop)

Wraps `play_hand()` in a loop across many hands: rotates the button, seeds RNG explicitly for reproducibility, and is the first point where a real BB/100 measurement across agent personalities becomes possible. Not started.

Separately, still open:
- `generate_boats()` indentation bug (Low priority, dataset-gen only).
- ctypes marshaling dominance in `evaluate_seven_c()` (~59% of its own time) — measured, not acted on, candidate follow-up if Stage 3's real hand-volume shows it mattering.

---

## Non-obvious constraints — read before touching anything

- **Never add `Co-Authored-By: Claude` to commits.** See `CLAUDE.md`.
- **Fish's biases are intentional, not bugs.** `low_card = min(r1, r2)` returning the low card, and `rank % 14` Ace wrap on A2–A9, are preserved on purpose. Only AK/AQ/AJ/AT were patched. See Blueprint §4.3.
- **`get_hand_key()` tuple comparison is the canonical hand evaluator everywhere except `calculate_win_odds()`'s inner loop.** `evaluate_seven()` returns a FIXED, zero-padded 6-tuple — safe to compare against other `evaluate_seven()` output, **not safe to compare against `get_hand_key()`'s raw variable-length output without truncating first**. `get_best_hand()` and Showdown (`resolve_showdown()`) both use `Hand`/`get_hand_key()` exclusively.
- **The C evaluator's `.so` isn't committed — `cd src/c_core && make` once to get the speed benefit.** Without it, `calculate_win_odds()` falls back to `evaluate_seven_py()` automatically (no crash, just slow). The differential tests skip, not fail, when the library isn't built.
- **`decide()`'s returned raise `size` is an INCREMENT, not a total, and not a raise-by-on-top-of-the-call either.** The betting loop computes `new_total = pot.contribution(seat) + min(size, stack_left)` and passes that TOTAL to `PotManager.set_contribution()` — this is the locked Stage 2 contract. `size` can legitimately be smaller than the actual `cost_to_call` an agent is facing (e.g. Fish's `pot_size*0.75` against a large bet) — this does NOT reopen or incorrectly close the round; the closure predicate's own `amount_to_call == 0` check blocks closure until the shortfall is made up on a later turn. Proven convergent, not just hoped to be — see `TestClosurePredicate::test_undershoot_raise_does_not_close_or_reopen_but_the_round_still_converges`.
- **An undershoot raise (`decide()` returns `("raise", size)` with `size < cost_to_call`, not all-in) is left as a genuine under-call — `_act()`'s raise branch (`src/engine/hand_runner.py`) never floors `size` at `cost_to_call`.** `cost` (the actual `amount_to_call`) is only ever read for the `call` branch and for what's passed to `decide()` as `cost_to_call`; the `raise` branch computes `new_total` purely from `size`, so an undershoot leaves `pot.amount_to_call(seat) > 0` after the action — nothing clamps it up to a call, nothing folds it, no error. That seat IS still added to `acted` (every non-fold branch adds unconditionally, undershoot or not) — closure does NOT rest on `acted` membership alone. `run_betting_round()`'s predicate is a conjunction (`acted.issuperset(actionable) AND all(amount_to_call(s) == 0 ...)`); `acted` being full is necessary but not sufficient, and it's specifically the second half that blocks closure here. Traced live (`p1` raises facing `cost_to_call=50` with `size=5`): `p1` contribution goes 2→7 (still owes 45, `acted={'p1','p2'}` already full, round still correctly blocked), `p2` checks (no-op, `cost_to_call=0` for `p2`), `p1` gets re-polled with the now-smaller `cost_to_call=45` and calls, landing both at 52 — closing only at the step where every actionable seat's `amount_to_call` actually reads 0, never earlier. Re-verified end-to-end through a full 4-street `play_hand()` with this exact pattern (not just the isolated `run_betting_round()` test): `went_to_showdown=True`, `awards={'p2': 104}`, `deltas={'p1': -52, 'p2': 52}`, `sum(deltas)==0`, `awards==pot_total==104` — `play_hand()`'s own internal conservation `assert`s did not fire. Isolated-case coverage: `TestClosurePredicate::test_undershoot_raise_does_not_close_or_reopen_but_the_round_still_converges` (`tests/test_hand_runner.py`).
- **`check_tilt()`'s `bankroll` argument in `play_hand()` is the hand's START-of-hand stack, never the post-settlement stack.** Feeding the reduced post-loss stack inflates the loss ratio and can mistrigger a tilt that shouldn't have fired (losing 40 of 100 is ratio 0.40, no tilt; the same `-40` against a post-settlement stack of 60 reads 0.67 and wrongly triggers). Don't "simplify" this to use the current/live stack in Stage 3.
- **`play_hand()` does NOT rotate the button between hands.** That's the caller's job across a multi-hand session (Stage 3, not built). Calling `play_hand()` in a loop with the same `table` plays every hand with the same button/blinds.
- **`PotManager.contribution()` is a CUMULATIVE total for the entire hand, never reset per street.** Do not add a reset-between-streets method — `amount_to_call()` is correct as written specifically because a betting round can't close until every live player's contribution already equals `highest_contribution()`.
- **`PotManager.split_pot()` does chip arithmetic only — it does NOT compare hands.** `resolve_showdown()` determines `winner_ids`; `split_pot()` just divides the pot among them using the odd-chip-to-first-clockwise rule.
- **`Table.blind_seats()` heads-up is a real-poker special case, not a bug.** With exactly 2 seats, the button IS the small blind; with 3+, blinds are the two seats clockwise from the button. `hand_runner.py`'s preflop/postflop first-to-act formulas (`seat_after(bb_seat)` / `seat_after(button_seat)`) work correctly for both without a branch, because this is already absorbed into `blind_seats()`.
- **No side pots / all-in-for-less exist in this MVP, and it's proven, not assumed.** Under heads-up + reset-equal-stacks-every-hand + `hand_runner.py`'s per-action `clamp_to_bankroll`, no seat's contribution can ever exceed its own starting stack, so a call is always fully affordable — an all-in call always lands both players at exactly equal contributions. This breaks the moment N>2 or stacks aren't reset equal; don't extend Stage 2's code to either without adding side-pot logic first.
- **QuantGrid's Chen score is vestigial.** `score_hand()` still calls `chen_score()` and caches it, but `decide()` (Option B) doesn't read it.
- **All four agents share one `decide(pot_size, cost_to_call, min_raise, bankroll)` signature.** `QuantGrid.__init__(self, engine)`/`Whale.__init__(self, engine)` still take a `PokerEngine` that Fish/Grinder don't.
- **`clamp_to_bankroll()` must be applied OUTERMOST** — after any `max(min_raise, ...)` flooring, never before.
- **`QuantGrid.from_dict()`/`Whale.from_dict()` require an explicit `engine` argument** (`from_dict(d, engine)`).
- **`calculate_win_odds()`'s cache key includes `num_opponents` and `simulations` now, not just the hole/board cards.**
- **Multiway tie credit is `_showdown_credit()`, not a manual divisor** — it's a probability fraction, not a chip split. Don't reuse it for pot-award logic.
- **`score_hand()` must be called immediately before `decide()` for ALL FOUR agents, not just QuantGrid/Whale.** Fish and Grinder read `getattr(self, "_cached_score", 0)` — skipping `score_hand()` silently defaults them to score 0 (Fish's weak branch, Grinder's fold-everything floor) rather than crashing. `hand_runner.py`'s `_act()` does this correctly; any future direct caller of `decide()` must too.
- **`seaborn` is imported in `simulation.py` but not installed/listed anywhere.** Tests work around this with a test-only `sys.modules` shim.
- **Verification bar is always: real printed output, not a summary.**

---

## Known bugs (priority order)

| Issue | Blocks | Priority |
|---|---|---|
| See `PokerEngine_Blueprint.md §10` for the full history through Stage 0.5. | — | — |
| `check_tilt()` trigger logic had no test coverage | Tilt wiring test coverage | **Fixed 2026-08-11** (commit `2c630a1`) |
| No dealer/pot/table/ledger primitives existed for Phase IV's betting loop | Phase IV Stage 2 | **Fixed 2026-08-11** (commit `2c630a1`) |
| No code path in the repo could play a hand — `check_tilt()` had no call site, no component called `Dealer`/`PotManager`/`Table`/`Ledger`, Showdown didn't exist | Any real BB/100 measurement | **Fixed 2026-08-12** (commit `8faa683`) — `src/engine/hand_runner.py`, `src/engine/showdown.py` |
| `generate_boats()` indentation bug in dataset generation | Dataset quality | Low — runtime not affected |
| `record_action()` / `plot_session_results()` called in old `__main__` block but never defined | Dead code cleanup | Low — confirm still referenced before fixing |

Full details in `PokerEngine_Blueprint.md §10`.
