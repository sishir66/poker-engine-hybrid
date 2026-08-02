# PokerEngine Handoff — 2026-08-02

Reference alongside `PokerEngine_Blueprint.md`. Blueprint has design spec and full rationale; this file has current state, open work, blockers, and resume instructions.

---

## Repo state

Branch: `main` — fully pushed, clean working tree.  
Last commit: `11f3fe3` — Blueprint/docstring update documenting QuantGrid audit.

```
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
| Hand evaluator (`get_hand_key()`) | `src/engine/simulation.py` | Tuple-based, kicker-aware, deterministic. MLP retired. |
| Dataset generation import fix | `src/models/generate_dataset.py` | `if __name__ == "__main__":` guard added (commit 6839ce3). |

---

## What's in progress (committed but explicitly temporary or incomplete)

**QuantGrid — placeholder committed, real implementation not started.**  
`src/engine/agent.py`. Both `score_hand()` and `decide()` are marked PLACEHOLDER in docstrings. Current behavior: Chen scoring (identical to Grinder), Kelly-scaled raise sizing. Not QuantGrid's real personality — do not treat as final or refine without explicit direction.

The specific gap audited this session: Kelly sizing (`decide()` lines 249-253) receives `win_odds` raw from its caller and computes nothing internally. No `chen_score → win_odds` mapping exists. Test output that looked correct (AA → raise 203) used `win_odds=0.85` hardcoded by a human, not produced by QuantGrid. **Blocked by `calculate_win_odds()` fix below before this can be wired to anything real.**

**`check_tilt()` — stub committed, not wired.**  
`src/engine/agent.py` lines 33-47. Logic is correct but `decide()` on all agents ignores `is_tilted` entirely. Not started as a wiring task.

---

## What's not started (intentional, queued)

| Item | Why not started |
|---|---|
| `Whale.score_hand()` / `Whale.decide()` | Both raise `NotImplementedError`. Intentionally deferred — Blueprint §5.6. |
| `tests/test_engine.py` | Empty stub. All verification done manually with inline scripts. Needs real pytest assertions. Blueprint §10. |
| QuantGrid Option B (wire to `calculate_win_odds()`) | Blocked — see below. |
| Position-aware `decide()` for all agents | Noted in `Agent` base class docstring. Not designed yet. |

---

## Blockers and next steps (in order)

### 1. Fix `calculate_win_odds()` — **do this first, nothing else**

**File:** `src/engine/simulation.py`  
**What's broken:** `feature_matrix = np.zeros((total_hands, 14))` is allocated but never filled. It's dead code — the Monte Carlo loop below constructs real `Hand` objects and compares `get_hand_key()` tuples directly — but the function's output has never been validated against known equity benchmarks. It may work or may have a subtle bug; we don't know yet.  
**Why it's blocking:** Every downstream item that involves real win probability — QuantGrid Option B, any meaningful Kelly sizing, eventual test coverage of Monte Carlo — is blocked until this produces verified output.

**Verification bar (actual printed output required, not a description):**
1. AA vs random opponent → win rate ≈ 85%
2. AKs equity > KQs equity
3. A forced-tie case → confirm `(wins + ties/2) / simulations` path fires correctly

### 2. Wire QuantGrid to `calculate_win_odds()` — **only after step 1 is verified**

Blueprint §5.5 Option B. Pass real Monte Carlo output as `win_odds` into `QuantGrid.decide()`. At that point, Kelly sizing becomes meaningful. Remove the PLACEHOLDER labels from docstrings when this lands.

### 3. Then (order TBD by user)

- `Whale` implementation (Blueprint §5.6)
- `tests/test_engine.py` — convert manual verification scripts into pytest assertions
- Wire `check_tilt()` into `decide()` on all agents + fix tilt aggression compounding bug (Blueprint §5.2)
- `PokerEngine.__init__` crash on missing model files (currently will crash on fresh clone)

---

## Non-obvious constraints — read before touching anything

- **Never add `Co-Authored-By: Claude` to commits.** See `CLAUDE.md`.
- **Fish's biases are intentional, not bugs.** `low_card = min(r1, r2)` returning the low card, and `rank % 14` Ace wrap on A2–A9, are preserved from the original heuristic on purpose. Only AK/AQ/AJ/AT were patched. See Blueprint §4.3.
- **`get_hand_key()` tuple comparison is the canonical hand evaluator.** The MLP (`src/models/`) is dead code retained in the repo but bypassed entirely. Do not re-introduce MLP into the eval path.
- **QuantGrid scoring docstrings say PLACEHOLDER explicitly.** Do not refine QuantGrid's Chen thresholds or introduce a `chen_score → win_odds` mapping — the real fix is wiring to `calculate_win_odds()` (Option B), not papering over the gap with a conversion formula.
- **Verification bar is always: real printed output, not a summary.** Every prior implementation was confirmed with actual script output pasted back. Same standard applies going forward.

---

## Known bugs (priority order)

| Issue | Blocks | Priority |
|---|---|---|
| `calculate_win_odds()` feature_matrix never filled — output unverified | QuantGrid Option B, real Kelly sizing, test coverage | **Highest** |
| QuantGrid `decide()` has no real `win_odds` source | QuantGrid evaluation | **High** — blocked by above |
| Tilt aggression compounds permanently across repeated tilt episodes | Tilt wiring | Medium |
| `tests/test_engine.py` empty — no automated regression coverage | Catching future regressions | Medium |
| `PokerEngine.__init__` crashes on fresh clone if model files absent | Fresh setup | Medium |
| `Whale` not implemented | Whale agent | Low — not started by design |
| `generate_boats()` indentation bug in dataset generation | Dataset quality | Low — runtime not affected |

Full details in `PokerEngine_Blueprint.md §10`.
