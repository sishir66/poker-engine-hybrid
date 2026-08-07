# PokerEngine Handoff — 2026-08-07

Reference alongside `PokerEngine_Blueprint.md`. Blueprint has design spec and full rationale; this file has current state, open work, blockers, and resume instructions.

---

## Repo state

Branch: `main` — 2 commits ahead of origin (not yet pushed at time of writing).  
Last commit: `3242717` — Implement Whale (Blueprint §5.6) — deep-stack maniac, full Kelly.

```
3242717 Implement Whale (Blueprint §5.6) — deep-stack maniac, full Kelly
9b44ff4 Add clamp_to_bankroll() and apply to Fish, Grinder, QuantGrid
ad155b5 Update HANDOFF.md and Blueprint §5.5/§10 — QuantGrid Option B closed
6c31c50 Wire QuantGrid.decide() to calculate_win_odds() (Option B)
3b4e339 Fix calculate_win_odds() dead feature_matrix block
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

---

## What's complete

| Component | File | Notes |
|---|---|---|
| Chen preflop formula | `src/engine/preflop.py` | K=8, true-rank gap (Ace=14), no wheel exception. AA=20, AKs=12, AKo=10, 77=7, 72o=0. |
| Kelly fraction | `src/engine/risk.py` | `f* = (b*p - q) / b`, clamped at 0. |
| `Agent` base class | `src/engine/agent.py` | `check_tilt()` stub exists but not wired into `decide()`. `to_dict()`/`from_dict()` complete. |
| `Fish` | `src/engine/agent.py` | Legacy heuristic with intentional biases preserved. See Blueprint §4.3. |
| `Grinder` | `src/engine/agent.py` | Chen formula, tight-aggressive thresholds. |
| `QuantGrid` | `src/engine/agent.py` | Option B implemented (commit `6c31c50`, 2026-08-07). Computes `win_odds` internally via `calculate_win_odds()`; decisions gated on `kelly_f` magnitude, not Chen score. See Blueprint §5.5. |
| `Whale` | `src/engine/agent.py` | Implemented (commit `3242717`, 2026-08-07). Same real-`win_odds` signal as QuantGrid; fold floor slightly looser (`kelly_f < 0.03` vs `0.05`), recklessness expressed in sizing (`aggression=1.2` × random band), not continuance. See Blueprint §5.6. |
| Bankroll clamp (`clamp_to_bankroll()`) | `src/engine/risk.py` | Added (commit `9b44ff4`, 2026-08-07). Applied to Fish/Grinder/QuantGrid/Whale — no agent can wager more than its bankroll. |
| Hand evaluator (`get_hand_key()`) | `src/engine/simulation.py` | Tuple-based, kicker-aware, deterministic. MLP retired. |
| Dataset generation import fix | `src/models/generate_dataset.py` | `if __name__ == "__main__":` guard added (commit 6839ce3). |

---

## What's in progress (committed but explicitly temporary or incomplete)

**`check_tilt()` — stub committed, not wired.**  
`src/engine/agent.py` lines 33-47. Logic is correct but `decide()` on all agents ignores `is_tilted` entirely. Not started as a wiring task. Note: the bankroll clamp (commit `9b44ff4`) bounds the *consequence* of the known tilt-compounding bug (unbounded aggression can no longer overflow a bet past bankroll) but does not fix the compounding logic itself — aggression still grows without reset across repeated tilt episodes once wired.

---

## What's not started (intentional, queued)

| Item | Why not started |
|---|---|
| `tests/test_engine.py` | Empty stub. All verification done manually with inline scripts. Needs real pytest assertions. Blueprint §10. **Next task.** |
| Position-aware `decide()` for all agents | Noted in `Agent` base class docstring. Not designed yet. |

---

## Blockers and next steps (in order)

### ~~1. Fix `calculate_win_odds()`~~ — **DONE (2026-08-03, commit `3b4e339`)**

Dead `feature_matrix = np.zeros((total_hands, 14))` block removed. Monte Carlo loop was already correct; function now verified end-to-end:
- AA vs random, heads-up: **85.75%** (ref 85.2%) ✓
- AKs **67.70%** > KQs **62.43%** ✓
- Forced-tie (Broadway board, both sides): **50.00%** exact ✓
- wins+ties+losses == simulations (no silent drops) ✓

`calculate_win_odds()` is now a trustworthy win-probability source for the first time.

### ~~2. Wire QuantGrid to `calculate_win_odds()`~~ — **DONE (2026-08-07, commit `6c31c50`)**

Blueprint §5.5 Option B implemented. `QuantGrid.decide()` computes `win_odds` internally via `calculate_win_odds()` and gates fold/call/raise on `kelly_f` magnitude (real pot odds, not a fixed `win_odds` cutoff): `kelly_f < 0.05` fold, `0.05–0.35` call-weighted, `>0.35` raise-weighted. Free-check path gated on `win_odds ≥ 0.50` since `kelly_f` is hardcoded to `1.0` when `cost_to_call == 0`. Chen score is now vestigial in `QuantGrid.score_hand()` — cached for interface consistency, no longer used by `decide()`. Both thresholds are documented as starting points, to be revisited against Phase IV BB/100 data. Full detail in Blueprint §5.5.

### ~~3. `Whale` implementation~~ — **DONE (2026-08-07, commit `3242717`)**

Blueprint §5.6. Same real `win_odds` signal as QuantGrid (not Chen); fold floor `kelly_f < 0.03` (slightly looser than QuantGrid's `0.05`); recklessness expressed via sizing (`aggression=1.2` × random band `[0.8, 1.6]`), not continuance. Verified: folds a strict subset of QuantGrid's folds (10/27 vs 15/27); 0 bankroll violations under stress.

**Side effect — surfaced and fixed a shared bug (commit `9b44ff4`):** implementing Whale at `kelly_alpha=1.0` exposed that no agent's raise sizing was bounded by bankroll. Fish/Grinder ignored bankroll entirely (sized off `pot_size`); QuantGrid was safe only by luck at `alpha=0.25`. Added `clamp_to_bankroll()` to `risk.py`, applied to all four agents as the outermost operation after `min_raise` flooring. Verified Fish/Grinder/QuantGrid produce identical output to before the fix in normal play — only previously-overflowing edge cases changed.

### 4. Next — order confirmed, unchanged from prior roadmap unless you say otherwise

- `tests/test_engine.py` — convert manual verification scripts into pytest assertions. **Top priority.**
- Wire `check_tilt()` into `decide()` on all agents + fix tilt aggression compounding bug (Blueprint §5.2). Note: the bankroll clamp above bounds this bug's worst *consequence* (bet overflow) but doesn't fix the compounding logic itself — still worth doing.
- `PokerEngine.__init__` crash on missing model files (currently will crash on fresh clone)

No priority change flagged — the clamp fix reduces the *urgency* of the tilt-compounding bug (it can no longer cause a bet to exceed bankroll) but doesn't reduce the *value* of fixing it, since unbounded aggression growth is still a behavioral bug independent of the overflow risk. Order above holds.

---

## Non-obvious constraints — read before touching anything

- **Never add `Co-Authored-By: Claude` to commits.** See `CLAUDE.md`.
- **Fish's biases are intentional, not bugs.** `low_card = min(r1, r2)` returning the low card, and `rank % 14` Ace wrap on A2–A9, are preserved from the original heuristic on purpose. Only AK/AQ/AJ/AT were patched. See Blueprint §4.3.
- **`get_hand_key()` tuple comparison is the canonical hand evaluator.** The MLP (`src/models/`) is dead code retained in the repo but bypassed entirely. Do not re-introduce MLP into the eval path.
- **QuantGrid's Chen score is now vestigial.** `score_hand()` still calls `chen_score()` and caches it, but `decide()` (Option B, implemented) no longer reads it — decisions are gated on `kelly_f` magnitude instead. Don't reintroduce Chen-score gating into `QuantGrid.decide()`.
- **`QuantGrid.decide()` and `Whale.decide()` signatures diverge from the `Agent` base class on purpose.** Both drop the `win_odds` parameter (computed internally now) and both `__init__()`s take an `engine` argument that Fish/Grinder don't. Not a bug — see Blueprint §5.5/§5.6.
- **Whale's recklessness is sizing-only, not continuance.** Its fold floor (`kelly_f < 0.03`) is only slightly looser than QuantGrid's (`0.05`) and its raise-weighted threshold/splits are identical. Don't loosen Whale's continuance logic further to express "maniac" — that personality belongs in `aggression`/random-band sizing, per explicit design decision this session.
- **`clamp_to_bankroll()` (`risk.py`) must be applied OUTERMOST** — after any `max(min_raise, ...)` flooring in a sizing expression, never before. `min_raise` can itself exceed a short stack; clamping before that floor lets `min_raise` punch back through the ceiling.
- **Verification bar is always: real printed output, not a summary.** Every prior implementation was confirmed with actual script output pasted back. Same standard applies going forward.

---

## Known bugs (priority order)

| Issue | Blocks | Priority |
|---|---|---|
| `calculate_win_odds()` feature_matrix never filled — output unverified | QuantGrid Option B, real Kelly sizing, test coverage | **Fixed 2026-08-03** (commit `3b4e339`) |
| QuantGrid `decide()` has no real `win_odds` source | QuantGrid evaluation | **Fixed 2026-08-07** (commit `6c31c50`) |
| `Whale` not implemented | Whale agent | **Fixed 2026-08-07** (commit `3242717`) |
| No agent's raise sizing was bounded by bankroll (Fish/Grinder ignored it; QuantGrid safe by luck) | All agents' sizing correctness | **Fixed 2026-08-07** (commit `9b44ff4`) |
| `tests/test_engine.py` empty — no automated regression coverage | Catching future regressions | **Highest** — next task |
| Tilt aggression compounds permanently across repeated tilt episodes | Tilt wiring | Medium — bankroll clamp bounds the overflow consequence but not the underlying compounding bug |
| `PokerEngine.__init__` crashes on fresh clone if model files absent | Fresh setup | Medium |
| `generate_boats()` indentation bug in dataset generation | Dataset quality | Low — runtime not affected |

Full details in `PokerEngine_Blueprint.md §10`.
