# ♠️ PokerEngine: Hybrid C/Python Market Sandbox

## Comprehensive Technical Architecture, System PRD & High-Level Specifications

---

## 1. Executive Summary & Project Intent

### 1.1 Objective

The **PokerEngine Market Sandbox** is an ultra-fast, hybrid C/Python execution framework designed to simulate parallel multi-agent game states. The system models how different algorithmic and heuristic agent profiles (Fish, Grinder, Quant Grid, Whale) alter their valuation parameters, risk tolerances, and capital allocation (via fractional Kelly constraints) when subjected to structural market regime shifts, liquidity contractions, and high-variance drawdowns.

### 1.2 Core Problem Solved

Traditional object-oriented game simulators suffer from extreme performance degradation due to Python loop overhead, object instantiation lag (`Card`, `Deck`, `Hand` classes), and memory allocation churn during Monte Carlo iterations.

This engine bypasses those bottlenecks using a **Hybrid Tech Stack**:

* **High-Level Orchestration (Python):** Handles macro state management, tournament blind escalation, portfolio tracking ledgers, and agent decision logic.
* **Low-Level Computation (ISO C99, future):** Executes raw bitmask manipulation, combinatorics evaluation, and in-place feature matrix infill at native C memory speeds.

### 1.3 Key Performance Targets

* **Time-to-Decision:** < 0.01 seconds per simulation batch (10,000+ parallel hand evaluations) — target for post-C-core implementation.
* **Memory Allocations:** Zero structural memory re-allocations inside execution loops via pre-allocated contiguous memory arrays.
* **Hand Evaluation Accuracy:** 100% — deterministic evaluation via `get_hand_key()`, not model-based classification (see §4.4 for why the MLP path was retired).

---

## 2. Technical Stack & System Boundaries

* **Core Languages:** Python 3.11, ISO C99 (planned), PyTorch (legacy/retired for hand eval, see §4.4)
* **Data & Math Libraries:** NumPy, Scikit-Learn, Pandas, Joblib
* **Foreign Function Interface (FFI):** `ctypes` / `cffi` (planned)
* **Target Hardware Architecture:** Apple Silicon (M4 Pro / Unified Memory Architecture)
* **Compilation Toolchain:** `gcc` / `clang` compiling to shared objects (`.so`) via `Makefile` (scaffolded, not implemented)

---

## 3. Project Directory Structure (current, as of Phase 0)

```
src/
  c_core/            — empty, .gitkeep placeholder (Phase VI, not started)
  engine/
    hand.py          — Hand class, get_rank_value(), get_hand_key()
    simulation.py    — PokerEngine orchestration, get_best_hand(), calculate_win_odds()
    cache.py         — empty stub
    risk.py          — calculate_kelly_fraction()
    inference.py     — empty stub (MLP retained for possible future non-hand-eval use)
    agent.py         — Agent base class + Fish, Grinder, QuantGrid, Whale
    preflop.py       — chen_score() (standard Chen formula)
  models/
    train_poker.py       — PokerMLP definition + training loop
    generate_dataset.py  — dataset generation (see §10, known bugs)
  utils/
    card.py
    deck.py
data/
  poker_model.pth
  poker_scaler.pkl
tests/
  test_engine.py     — currently empty; manual verification only (see §10)
Makefile             — placeholder, no real build target yet
```

---

## 4. Architectural Domain Rules & Mathematics

### 4.1 Memory Boundary & FFI Architecture (planned, Phase VI)

Python will allocate all primary game state buffers as **contiguous, C-ordered NumPy arrays**. When passing data across the FFI boundary to the C library, Python transfers only **raw memory pointers**. The C layer mutates data directly *in-place*, avoiding runtime array copying.

```text
[ Python Runtime State ]
       │ (Extract continuous primitive arrays)
       ▼
[ NumPy Matrix Layout (Contiguous Memory) ]
       │ (Pass raw memory pointers via ctypes/cffi)
       ▼
[ C Native Shared Library (.so) ] ──> Executes bitwise logic in-place
```

### 4.2 Pre-Flop Valuation — Standard Chen Formula (implemented, verified)

Implemented in `src/engine/preflop.py` as `chen_score()`. Used by Grinder and (temporarily) QuantGrid.

1. **High Card Base Score:** A=10, K=8, Q=7, J=6; numerical cards 10 through 2 = Rank / 2.0.
2. **Pairs:** High Card Score × 2.0 (Minimum floor of 5.0).
3. **Suited Bonus:** +2.0 points.
4. **Gap Penalties:** 1-gap = -1, 2-gap = -2, 3-gap = -4, 4+ gap = -5 (capped — no special-casing needed for Ace, since the cap alone prevents any blowup at true rank distance).
5. **Connector Bonus:** +1 if both cards ≤ 10.

**Verified reference values (hand-derived, session-confirmed):**
AA=20, AKs=12, AKo=10, KQs=10, 77=7, JTs=8, A9o=5, A2s=A3s=A4s=A5s=7 (tie — see note below), 95s=4, 72o=0, AQs=11, AJs=10, ATs=8.

**Known limitation (not a bug):** Standard Chen does not distinguish among A2s–A5s — all four tie at 7, since their true rank-distance from Ace all exceed the gap≥4 cap threshold identically. This is a documented property of the formula, not an implementation defect. (Earlier in development, an incorrect "wheel exception" was implemented to try to differentiate these hands and give A2s extra credit for wheel/flush potential — this was removed. Standard Chen genuinely does not reward wheel potential; do not reintroduce ace-low special-casing without a specific cited source for a Chen *variant* that does.)

### 4.3 Legacy Heuristic Scoring — Fish's Brain (implemented, verified)

A pre-existing hand-scoring formula (originally written without formula research, tuned only by eyeballing hand rankings) repurposed intentionally as Fish's scoring, biases included:

```python
def calculate_hands(self):
    summation_odds = 0
    if self.is_pair(): summation_odds += 30
    summation_odds += self.calculate_num()
    if self.calculate_high() > 10:
        summation_odds += 8 + (3 * (self.calculate_high() - 10))
    summation_odds -= self.calculate_difference()
    if self.calculate_suits(): summation_odds += 20
    if (not self.calculate_suits()) and (self.calculate_high() < 9):
        summation_odds -= self.calculate_difference()
    return summation_odds
```

**Intentional, preserved biases (Fish's "personality," not bugs):**
- Flat +30 for any pocket pair regardless of rank — Fish overvalues any made pair, including sometimes above legitimately stronger unpaired hands (e.g. 77=44 > AKo=43 in testing — a real, deliberate emergent quirk).
- `calculate_high()` actually returns the LOW card of the two (ascending sort, index 0) — meaning the ">10 bonus" only fires when BOTH cards exceed 10, systematically undervaluing lone-Ace-plus-low-kicker hands relative to two-broadway hands.
- `calculate_difference()` uses `value % 14` for gap distance, not true rank distance — collapses Ace to 0 for gap purposes.
- Double-penalty condition (offsuit AND low kicker) applies the gap penalty twice — originally threshold `<10`, adjusted to `<9` (see below).

**Patched (one real bug, fixed):** The `% 14` behavior made Ace-plus-adjacent-broadway hands (AK, AQ, AJ, AT) compute the *maximum* possible gap penalty, since the modulo made a bigger companion card produce a bigger apparent gap — backwards from real rank distance. Patched so AK/AQ/AJ/AT use Ace's true rank (14) for gap purposes; A2–A9 retain the original `%14` behavior as an intentional blind spot.

**Adjusted (deliberate tuning, not a bug fix):** The double-penalty threshold was moved from `<10` to `<9` — A9o no longer receives the double penalty (was scoring 5, unrealistically close to genuine trash hands; now scores 14). A8o and below still receive it.

**Verified reference values:** AA=78, AKs=63, AKo=43, A9o=14, A8o=6, A5s=34, 77=44, KQs=58.

### 4.4 Hand Evaluation — Deterministic, Not Model-Based (implemented, verified)

`get_best_hand()` originally used a trained PyTorch MLP (`PokerMLP`, 14→512→256→128→10) to classify hand rank category via `argmax` over 21 combinatorial 5-card hands. **This has been replaced.**

**Why:** Hand ranking is a deterministic, fully-specified function of 5 cards — there is no ambiguity for a model to resolve, and a trained classifier is strictly worse than an exact algorithm for this sub-problem (introduces error rate on rare hands, for zero benefit). Additionally, the MLP's scalar 0–9 output collapsed all within-category information (e.g. two different Two-Pair hands both returned "2"), making kicker comparison structurally impossible downstream — this was a real, previously invisible bug affecting the Monte Carlo win-rate comparator (see §4.5).

**Current approach:** `Hand.get_hand_key()` returns a tuple `(rank_value, *ranks_in_descending_importance)` per hand category, enabling correct kicker resolution via native Python tuple comparison. Full tuple design:

| Category | Tuple shape | Note |
|---|---|---|
| High Card | (0, r5,r4,r3,r2,r1) | all 5 ranks desc |
| Pair | (1, pair_r, k3,k2,k1) | |
| Two Pair | (2, high_pair_r, low_pair_r, kicker_r) | must select TOP two pairs by rank if 3 pairs present in a 7-card hand — tested explicitly (A A K K Q Q J case) |
| Trips | (3, trips_r, k2,k1) | |
| Straight | (4, straight_high) | wheel (A-2-3-4-5) = 5, not 14 |
| Flush | (5, r5,r4,r3,r2,r1) | no wheel exception — suits never involve straight order |
| Full House | (6, trips_r, pair_r) | |
| Quads | (7, quad_r, kicker_r) | |
| Straight Flush | (8, straight_high) | same wheel rule as Straight |
| Royal Flush | (9, 14) | constant — all royals tie |

The MLP (`PokerMLP`, `train_poker.py`) remains in the codebase but is no longer used for hand ranking. Possible future use: as an input to QuantGrid's real scoring (see §5.5, Option B) or retired entirely.

### 4.5 Monte Carlo Win-Rate Comparator (partially fixed, one bug remains)

`calculate_win_odds()` in `simulation.py`:
- Deck sampling (`np.random.choice` over remaining deck, building `sim_cards`) — **correct**.
- Win/tie comparison — **fixed this session**: previously used scalar MLP-classified rank (`torch.argmax`), causing any same-category hands to count as ties regardless of actual kicker strength (e.g. Two Pair with different kickers wrongly scored as a tie). Now uses `get_hand_key()` tuple comparison per simulation.
- **Feature matrix infill — still broken.** `feature_matrix = np.zeros((total_hands, 14))` is allocated but never filled with real card data before being passed downstream. This is dead code now that hand evaluation no longer depends on the MLP path, but the function's Monte Carlo loop still needs to construct real `Hand` objects from `sim_cards` per simulation to actually compute a win probability. **This is the highest-priority remaining bug** — until fixed, `calculate_win_odds()` does not return a trustworthy result.

### 4.6 Post-Flop Multi-Factor Decay Engine (spec only, not implemented)

Post-flop equity valuation intended to map non-linear risk cliffs via exponential decay, modeling kicker domination risk as later streets reveal more cards:

**Final Equity (p) = P(Win) × M_texture × exp(−λ · δ_kicker)**

Where:
* `P(Win)` = baseline probability from `calculate_win_odds()` (once fixed) or a heuristic.
* `M_texture` = Board Texture Multiplier (0.4 wet/connected boards, 1.0 dry boards).
* `δ_kicker` = Board Max Rank − Hand Kicker Rank.
* `λ = 0.3` = decay constant.

**Conceptual note:** This models kicker-domination risk specifically — not a generic "more cards = worse" effect. A strong-kicker hand on a dry board should decay minimally as streets progress; only coordination-vulnerable/weak-kicker hands should decay sharply. Zero code exists for this yet — belongs to QuantGrid (Option A design, §5.5) if pursued.

### 4.7 Capital Allocation Framework — Kelly Criterion (implemented, verified)

**Bounded Fractional Kelly:** `f* = ((b·p − q) / b) × α`

Where `p` = win probability, `q = 1−p`, `b` = effective pot odds (pot / cost-to-call, stack-bounded), `α` = per-agent damping factor.

**Why α exists (worth remembering, not just citing):** Full Kelly is extremely sensitive to errors in the win-probability estimate `p`. Since `p` is never the true probability — it comes from a heuristic or a simulation with sampling error — a small estimation error gets amplified into a much larger bet-sizing error under full Kelly. Fractional Kelly is a hedge against your own probability model being wrong, not a personality trait about "comfort with odds." Where personality legitimately enters is *which* α an agent picks — Whale at 1.0 means "I don't care that my estimate might be garbage" (recklessness), not a different definition of a good price.

**Effective Stack & Reward Capping:**
`b_effective = (Current Pot + min(Hero Stack, Villain Stack)) / Cost to Call`

Extracted as a standalone function `calculate_kelly_fraction()` in `src/engine/risk.py` (originally a bound method on `PokerEngine`, refactored out during Phase 0 restructuring).

---

## 5. Agent Profiles & Behavioral State Machines

### 5.1 Agent Base Class (implemented)

`src/engine/agent.py`:
```python
class Agent:
    def __init__(self, name, kelly_alpha, aggression=1.0, is_tilted=False, _tilt_hands_remaining=0):
        ...
    def score_hand(self, hole_cards, community_cards): raise NotImplementedError
    def decide(self, win_odds, pot_size, cost_to_call, min_raise, bankroll): raise NotImplementedError
    def check_tilt(self, hand_profit, bankroll): ...  # see 5.2
    def to_dict(self): ...
    @classmethod
    def from_dict(cls, d): ...
```

**Fixed bug (Phase 0):** `from_dict()` originally always reset `_tilt_hands_remaining` to 0 regardless of the stored value, breaking serialization round-trips silently (no crash — just data loss). Fixed to correctly restore the passed value.

**Future (documented on base class, applies to all four agents equally):** `decide()` will likely need position (UTG/MP/CO/BTN/blinds) and bet-size-relative-to-pot/stack as additional inputs, to support (1) position-based threshold tightening/loosening across all agents, (2) Fish's bet-size-aware fold path (see 5.3), (3) more realistic multi-street play generally. Not implemented — current `decide()` logic is intentionally position-blind as a clean baseline, to be layered on top of later rather than retrofitted per-agent piecemeal.

### 5.2 The Tilt State Machine (stubbed, not wired into decide())

1. **Trigger:** Single-hand loss > 50% of bankroll → `is_tilted = True`, `aggression *= 1.5`, `_tilt_hands_remaining = 10`.
2. **Cooldown:** Decrements each hand; resets `is_tilted = False` at 0.
3. **Known open issue:** `aggression *= 1.5` never divides back down — if an agent tilts twice, aggression compounds permanently (1.5× → 2.25× → ...). Needs a `base_aggression` field to reset against. Not yet fixed.
4. **User idea, not yet designed or built:** A "shock/realization" third state after tilt ends — instead of snapping straight back to baseline, aggression dips *below* baseline for a recovery window before normalizing (three-state machine: normal → tilted → recovering → normal, rather than the current two-state normal↔tilted). Worth building alongside the aggression-compounding fix, since both touch the same reset mechanism.
5. Not currently called anywhere in any agent's `decide()`.

### 5.3 Fish — Loose-Passive (implemented, verified)

- `score_hand()`: legacy heuristic, see §4.3.
- `decide()`: uses cached score (not `win_odds`) for thresholding — deliberate, since Fish's whole personality is built around its own biased self-assessment, not accurate odds. Loose-passive shape: rarely folds, rarely raises, mostly calls; randomness implemented as genuine dice-roll variance (not deterministic thresholds), matching original design intent.
- **Bug found and fixed:** an unconditional 8% fold chance was initially implemented for all hands scoring ≥20 (including AA) — this contradicted the original design, where fold was only reachable for hands scoring ≤4. Removed; fold is now only reachable below the score floor, matching original spec.
- **Future work (documented in-code at the relevant spot):** a bet-size/pot-relative fold path for strong hands — Fish occasionally folding even a good hand when facing a disproportionately large bet. Not implemented; needs bet-size/stack context not currently in `decide()`'s signature.

### 5.4 Grinder — Tight-Aggressive (implemented, verified)

- `score_hand()`: calls `chen_score()` directly from `preflop.py` — no duplicated logic.
- `decide()` thresholds:

| Situation | Condition | Action |
|---|---|---|
| Bet required | Chen < 7 | Fold — deterministic, no roll |
| Bet required | 7 ≤ Chen ≤ 9 | Raise 30% / Call 70% |
| Bet required | Chen ≥ 10 | Raise 80% / Call 20% |
| No bet | Chen < 7 | Check |
| No bet | 7 ≤ Chen ≤ 9 | Raise 25% / Check 75% |
| No bet | Chen ≥ 10 | Raise 60% / Check 40% |

**Deliberate design note:** Chen's pair floor (5) means 22–66 all fold to any bet under this scheme — a conscious, accepted tight stance, not an artifact to "fix." Randomness is bounded (single draw per decision, score-gated probability) rather than Fish's wide unconditional swings — reflects a disciplined, consistent player. No unconditional/score-independent branches exist (lesson carried over directly from the Fish fold bug).

### 5.5 QuantGrid — Placeholder Only (temporary implementation)

**Current state:** Reuses `chen_score()` — scoring currently *identical* to Grinder's. Bet sizing differs (Kelly-fraction-scaled via `kelly_alpha=0.25`, rather than Grinder's flat raise amounts), but hand evaluation itself is not yet distinct. This is explicitly marked in-code as temporary and should not be read as QuantGrid's real personality.

**Kelly sizing structure (audited 2026-08-02):** The Chen-score gating path (fold/call/raise thresholds) and the Kelly-sizing path are structurally independent — they share no data. `win_odds` in `decide()` is the raw parameter received from QuantGrid's caller; QuantGrid computes nothing internally to produce it. No `chen_score → win_odds` conversion exists anywhere in the code, and none is planned — the real fix is wiring Kelly sizing directly to `calculate_win_odds()` output once that function is fixed (Option B). Any test output that looked realistic (e.g. AA sizing to 203) reflected `win_odds` values hardcoded by a human who knew real poker equities (0.85 for AA), not values produced by QuantGrid. If wired today to the broken `calculate_win_odds()`, QuantGrid would size bets off garbage input.

**Long-term design — two options, not yet decided which to build:**

**Option A — 13×13 Preflop Range Grid + Postflop Decay** (original Blueprint spec): full 169-hand preflop grid with position-aware equity percentages, post-flop exponential decay per §4.6, SPR-bounded Kelly sizing.

**Option B — Direct Monte Carlo (currently favored):** Bypass hand-tuned heuristics entirely once `calculate_win_odds()` is fixed and trustworthy — QuantGrid's real edge would come from *using the actual simulation engine* rather than any static chart, which is thematically fitting: Fish and Grinder are heuristic-driven by design (that's their character), QuantGrid's identity is being the mathematically rigorous agent, so wiring it directly into real simulation output is the natural fit once that output can be trusted.

**Prerequisites for Option B specifically:** fix `calculate_win_odds()` feature-matrix bug (§4.5); validate Monte Carlo output against known equity tables; profile simulation speed (1000 sims/decision may be too slow for real-time play without the C core, §8).

**Phase V — QuantGrid Empirical Hand Memory (future, documented, not built):**
QuantGrid maintains a persistent `hand_type -> observed_win_rate` table, accumulating across sessions (keyed by hand type, not by opponent). Its `decide()` blends this empirical data with whatever static score it's using (Chen, Option A grid, or Option B simulation output), weighted toward empirical data as sample size grows and toward the static score when data is thin. Framing note: this isn't "two independent sources of truth" — the heuristic is a cheap approximation, and accumulated empirical data is a more accurate replacement for it as evidence builds, similar to how real solvers/serious players say "theory says X, but in practice Y wins more." Depends on Chen/decide() baseline logic existing first (satisfied) and ideally on Option B being resolved (not yet).

### 5.6 Whale — Not Yet Implemented

Per original spec: deep-stack maniac, uniform random noise, maximum variance, unbounded Kelly (α = 1.0). No `score_hand()` or `decide()` written yet.

### 5.7 Within-Session Opponent Adaptation (future, all agents, not built)

Distinct from Phase V (which is QuantGrid-only, cross-session, hand-type-keyed). This is a proposed addition to the `Agent` base class: an `observe(opponent_name, action, amount)` method updating a per-opponent running-average stats dict (e.g. VPIP — voluntarily-put-money-in-pot rate, raise frequency) as hands are played within a single session. All four agents would maintain this, reflecting that even unsophisticated players semi-consciously notice patterns like "this player folds a lot." Not wired into any `decide()` yet — infrastructure only, when built.

---

## 6. Simulation Scenarios & Environments (spec only, not implemented)

### 6.1 Environment Alpha: Cash Sandbox (Infinite Pool Liquidity)
* **Blind Structure:** Static (1 BB / 2 BB).
* **Capital Rules:** Automatic re-buy execution to 100 BB when stack hits 0.
* **Metric:** Asymptotic EV (BB/100 hands) across static market regimes.

### 6.2 Environment Beta: Tournament Sandbox (Liquidity Contraction)
* **Blind Structure:** Doubles every 50 simulated hands.
* **Capital Rules:** Zero re-buys. 0 BB = permanent elimination.
* **Metric:** Survival rates under ICM constraints and escalating scarcity.

**Note — Side Pots (future, Tournament-mode specific):** Unequal-stack all-ins require side-pot resolution — a main pot capped at the shortest stack's contribution, plus separate side pot(s) among remaining players. This is distinct from a genuine tie (which correctly splits evenly via `get_hand_key()`). Not relevant to Cash Sandbox (stacks normalize via rebuy) — specifically a Tournament-mode dependency, to be built once multi-way pots with unequal stacks are reachable in the simulation loop. Do not build before multi-way hand comparison itself is fully reliable.

---

## 7. Migration Map & Legacy Pseudocode (superseded by real implementation where noted)

### 7.1 Hand Evaluation — superseded, see §4.4 for actual implementation (deterministic `get_hand_key()`, not a C bitmask evaluator — C core not yet built, see §8).

### 7.2 Monte Carlo Simulation Pipeline — partially superseded, see §4.5 for actual state (deck sampling + comparison logic real; feature infill still stubbed).

### 7.3 Decision Engine Pipeline — superseded, see §5 for actual per-agent implementations. Original pseudocode's single unified `make_agent_decision()` function was replaced by per-agent `decide()` methods on the `Agent` hierarchy, which better supports agent-specific personality logic (Fish's cached-score thresholding vs. Grinder's Chen-based thresholding are structurally different, not just parameter variations of one function).

---

## 8. Development Roadmap & Implementation Milestones

* **Phase 0 — Foundational Correctness (COMPLETE, this session):**
  * Repo/git safety: source extracted from gitignored `.venv/`, restructured into `src/` layout, committed and pushed.
  * `Agent` base class scaffolded; tilt round-trip bug fixed.
  * `get_hand_key()` implemented — kicker-aware comparison replacing MLP classification for hand ranking.
  * `get_best_hand()` rewired to deterministic evaluation.
  * `calculate_win_odds()` comparator fixed (still has feature-infill bug, see §4.5).
  * Standard Chen formula implemented and hand-verified (including correcting two wrong turns: a false reference value and an incorrectly-invented wheel exception).
  * Fish and Grinder fully implemented (`score_hand()` + `decide()`), verified.

* **Phase I: C Core & Shared Library Compilation** (not started)
  * Native bitmask hand evaluation algorithm in C99.
  * `Makefile` targeting Apple Silicon, `.so` output.

* **Phase II: FFI Interface & Vectorized Memory Layouts** (not started)
  * `ctypes`/`cffi` bridging, zero-copy array mutation.

* **Phase III: Signature Caching** (not started — `cache.py` is an empty stub)
  * Intercept redundant board-state computations.

* **Phase IV: Environment Execution & Performance Analytics** (not started)
  * Cash/Tournament multi-agent loops, BB/100 and ICM survival tracking.

* **Phase V: QuantGrid Real Scoring** — see §5.5 for full detail (design undecided: Option A vs B; empirical memory sub-feature documented).

* **Phase VI: Whale Implementation** — not started, see §5.6.

* **Phase VII: `tests/test_engine.py`** — currently empty. All verification this session was manual (inline scripts, printed output reviewed by hand). Converting these into permanent pytest assertions is outstanding — needed so regressions are caught automatically rather than requiring re-verification by hand each time.

---

## 9. Development Protocol & Cognitive Audit Rules

1. **Memory Binding Validation:** All `ctypes` argument declarations and array shapes must be manually verified to prevent segmentation faults (applies once Phase I/II begin).
2. **Pointer Debugging Rule:** If a segmentation fault occurs in C, isolate the memory boundary failure line using print statements or `lldb` before making code adjustments — trace it yourself; don't let an agent fix a segfault you haven't personally localized.
3. **Tensor Dimension Verification:** Manual shape verification required for all tensor transformations if/when the MLP is reintroduced for any purpose.
4. **No unconditional/score-independent branches in any `decide()` implementation** — added this session, following the Fish unconditional-fold bug. Every decision branch must be gated on some game-state signal (score, win_odds, etc.), never a bare random roll with no relationship to hand or context.
5. **Verify claimed edge-case coverage explicitly** — e.g. three-pair-in-seven-cards for `get_hand_key()`'s Two Pair selection; AK/AQ/AJ/AT for any Ace-gap logic. A formula that "looks right" on typical hands can still be wrong on a specific edge case; test the edge case, don't infer it from the general logic.
6. **Don't trust a human-supplied reference value without independent derivation** — this session caught one wrong Chen reference value (77) via hand-derivation; treat any provided "expected" test value as a hypothesis to verify, not ground truth by default.

---

## 10. Known Bugs & Outstanding Issues (as of session end)

| Issue | Status | Priority |
|---|---|---|
| `calculate_win_odds()` feature_matrix all-zero infill | Open | **Highest** — blocks trustworthy win-probability output entirely |
| QuantGrid `decide()` has no `win_odds` source — Kelly-sizing formula is correct, but `win_odds` is externally supplied with no real caller yet; any current output reflects the caller's input, not a QuantGrid computation | Open | **High** — blocks any real evaluation of QuantGrid sizing until wired to a trustworthy `win_odds` source |
| `generate_dataset.py` module-level execution on import | Fixed (commit 6839ce3) | — |
| Tilt aggression compounds permanently across repeated tilt episodes (no reset to base) | Open | Medium |
| `generate_boats()` indentation bug (pre-existing, causes duplicate row corruption in dataset generation) | Open, not yet addressed this session | Low (dataset-gen only, not runtime-critical) |
| `record_action()` / `plot_session_results()` called in old `__main__` block but never defined | Open, likely dead code post-restructure — confirm still referenced anywhere before fixing | Low |
| `tests/test_engine.py` empty — no automated regression coverage | Open | Medium — increasingly important as more agents get built |

---

*Last updated: end of session covering Phase 0 (repo safety + correctness foundation), Fish and Grinder full implementation, QuantGrid placeholder, Chen formula verification.*