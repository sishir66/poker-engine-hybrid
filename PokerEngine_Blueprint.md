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

### 4.5 Monte Carlo Win-Rate Comparator (fixed, verified — commit `3b4e339`, 2026-08-03)

`calculate_win_odds()` in `simulation.py`:
- Deck sampling (`np.random.choice` over remaining deck, building `sim_cards`) — **correct**.
- Win/tie comparison — **fixed**: previously used scalar MLP-classified rank (`torch.argmax`), causing any same-category hands to count as ties regardless of actual kicker strength (e.g. Two Pair with different kickers wrongly scored as a tie). Now uses `get_hand_key()` tuple comparison per simulation.
- **Feature matrix infill — fixed.** The dead `feature_matrix = np.zeros((total_hands, 14))` allocation (never filled, never read — a leftover from the retired MLP path) was removed entirely in commit `3b4e339`. The Monte Carlo loop already constructed real `Hand` objects from `sim_cards` per simulation and compared `get_hand_key()` tuples directly — the allocation was dead weight, not a functional gap. Verified against known equity benchmarks: AA vs random ≈85.75% (ref 85.2%), AKs (67.70%) > KQs (62.43%), forced-tie scenario exactly 50.00%. See §10 for full verification detail.

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

### 5.5 QuantGrid — Option B Implemented (commit `6c31c50`, 2026-08-07)

**Current state:** QuantGrid computes `win_odds` internally via `calculate_win_odds()` (Monte Carlo simulation) rather than receiving it from a caller. `score_hand()` still calls `chen_score()` and caches the result for interface consistency with the other agents, but the returned score is **vestigial** — `decide()` no longer reads it, and Chen no longer gates any fold/call/raise decision. `score_hand()`'s real job under Option B is caching `hole_cards`/`community_cards` for `decide()` to pass into `calculate_win_odds()`.

**Decision tree — gated on `kelly_f`, not a fixed `win_odds` cutoff:** `calculate_kelly_fraction()` (`risk.py`) already incorporates the real pot odds for the decision via `b = pot_size / cost_to_call`, so gating on `kelly_f` magnitude (rather than a fixed `win_odds` threshold) correctly adapts to the price being offered — a hand that's a fold at 1:1 pot odds may be a clear call at 5:1. A fixed `win_odds` cutoff would get both cases wrong.

- `cost_to_call > 0`: `kelly_f < 0.05` → fold; `0.05 ≤ kelly_f ≤ 0.35` → raise 30% / call 70%; `kelly_f > 0.35` → raise 80% / call 20%.
- `cost_to_call == 0` (free to check): `calculate_kelly_fraction()` hardcodes `kelly_f = 1.0` for this case, so it carries no information — gated on `win_odds` directly instead: `win_odds < 0.50` → check; `win_odds ≥ 0.50` → raise 60% / check 40%.

**Threshold values are deliberate starting points, not final.** The `0.05` fold floor and `0.35` raise-weighted floor both sit a margin above their exact mathematical breakpoints (0.0 = Kelly breakeven). This is a personality/risk-tuning choice for QuantGrid — same category as Fish's A9o double-penalty threshold tuning (§4.3) — not a formula correction. Revisit both values once real Phase IV simulation data (BB/100 results across agents) exists to justify tightening or loosening them.

**Signature diverges from the `Agent` base class — intentional.** `QuantGrid.decide(self, pot_size, cost_to_call, min_raise, bankroll)` drops the `win_odds` parameter present in `Agent.decide()`'s signature, since QuantGrid now computes it internally. `QuantGrid.__init__(self, engine)` also takes a `PokerEngine` instance, which Fish/Grinder/Whale do not. Not a bug — Python doesn't enforce subclass signature parity, and any caller passing `win_odds` positionally to `QuantGrid.decide()` will get a `TypeError` rather than silently wrong behavior.

**Option A (13×13 preflop range grid + postflop decay)** remains undesigned and unbuilt — Option B was chosen and implemented instead. Left here for historical reference only; not planned.

**Phase V — QuantGrid Empirical Hand Memory (future, documented, not built):**
QuantGrid maintains a persistent `hand_type -> observed_win_rate` table, accumulating across sessions (keyed by hand type, not by opponent). Its `decide()` blends this empirical data with whatever static score it's using — now Option B's simulation output. Both are already on a `[0,1]` win-probability scale, so no unit-conversion step is needed; blending is direct arithmetic. Depends on `decide()` baseline logic existing first (satisfied, Option B implemented).

### 5.6 Whale — Implemented (commit `3242717`, 2026-08-07)

Deep-stack maniac, full Kelly (α = 1.0). Uses the same real Monte Carlo `win_odds` signal as QuantGrid (Option B), not Chen — Whale understands the game and chooses to overbet; a heuristic-driven signal would make it Fish with a bigger stack.

**Continuance vs QuantGrid — nearly identical, slightly looser:** fold floor is `kelly_f < 0.03` (vs QuantGrid's `0.05`), a consistent ~1–1.6 percentage-point loosening in the win-odds it implies depending on pot odds. The raise-weighted threshold (`kelly_f > 0.35`) and both probability splits (30/70, 80/20) are identical to QuantGrid's — recklessness is not expressed as playing weaker hands.

**Sizing is where the personality lives:** `aggression=1.2` (a deterministic overbet bias) multiplied by a random band `uniform(0.8, 1.6)` (variance) applied to `kelly_raise`. Both factors scale the Kelly-derived amount; neither decides whether to act, so this stays compliant with §9's ban on score-independent branches. Free-check path (`cost_to_call == 0`) sizes as a pot-relative overbet (`pot_size * 1.5 * aggression`) rather than `bankroll * kelly_f * kelly_alpha`, because `risk.py` hardcodes `kelly_f = 1.0` on that path — with `alpha=1.0` that formula would shove the entire stack on every free-check raise. Whale overbets the pot; it doesn't reflexively jam.

**Bankroll ceiling:** every raise path is wrapped in `clamp_to_bankroll()` (see §10 — discovered while implementing Whale, fixed as a shared addition to `risk.py` in commit `9b44ff4`, applied to Fish/Grinder/QuantGrid too).

Verified: fold-floor boundary table confirms Whale folds a strict subset of QuantGrid's folds (10/27 vs 15/27 on the standard hand set); 0 bankroll violations across a stress sweep including 4× compounded tilt aggression; mean/spread of bet size materially larger than QuantGrid's at the same spot, both bounded ≤ bankroll.

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
  * `calculate_win_odds()` comparator fixed, including the feature-infill dead-code removal (commit `3b4e339`, see §4.5).
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

* **Phase V: QuantGrid Real Scoring** — Option B implemented, see §5.5 for full detail (empirical memory sub-feature still not built).

* **Phase VI: Whale Implementation** — implemented, see §5.6.

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
| `calculate_win_odds()` feature_matrix all-zero infill | **Fixed** — verified 2026-08-03, commit `3b4e339`. Verified: AA 85.75% (ref 85.2%), AKs 67.70% > KQs 62.43%, forced-tie 50.00% exact, wins+ties+losses=simulations confirmed. Unblocks QuantGrid Option B. | — |
| QuantGrid `decide()` has no `win_odds` source | **Fixed** — Option B implemented and verified 2026-08-07, commit `6c31c50`. See §5.5. | — |
| No agent's raise sizing was bounded by bankroll — Fish/Grinder ignored bankroll entirely (sized off `pot_size`); QuantGrid was safe only by luck at `alpha=0.25`. Discovered while implementing Whale (`alpha=1.0` made the gap immediately visible). | **Fixed** — `clamp_to_bankroll()` added to `risk.py` and applied to Fish/Grinder/QuantGrid, commit `9b44ff4`; Whale built with the clamp from the start, commit `3242717`. Verified 2026-08-07: existing agents produce identical output in normal play, previously-overflowing edge cases now clamp correctly. | — |
| `Agent.from_dict()` raises `TypeError` on every subclass — `Fish`/`Grinder`/`QuantGrid`/`Whale` all override `__init__()` with a signature that doesn't accept the kwargs (`name`, `kelly_alpha`, `aggression`, `is_tilted`, `_tilt_hands_remaining`) the base classmethod passes to `cls(...)`. Confirmed empirically on all four (identical error: `unexpected keyword argument 'name'`) while writing `tests/test_engine.py` — worked around there by testing against base `Agent` directly rather than fixed. | Open — will actively break any future save/load or checkpoint functionality (relevant to Phase IV environments, §6) | **Medium-High** |
| `generate_dataset.py` module-level execution on import | Fixed (commit 6839ce3) | — |
| `PokerEngine.__init__` crashes on fresh clone if model files (`data/poker_model.pth`, `data/poker_scaler.pkl`) are absent — both are gitignored, so this fails immediately for anyone cloning the repo without first training a model | Open — previously referenced only in this section's footer, with no table row; added here | Medium |
| Tilt aggression compounds permanently across repeated tilt episodes (no reset to base) | Open — the bankroll clamp (above) bounds the *consequence* of unbounded aggression growth, but the underlying compounding logic itself is still unfixed | Medium |
| `generate_boats()` indentation bug (pre-existing, causes duplicate row corruption in dataset generation) | Open, not yet addressed this session | Low (dataset-gen only, not runtime-critical) |
| `record_action()` / `plot_session_results()` called in old `__main__` block but never defined | Open, likely dead code post-restructure — confirm still referenced anywhere before fixing | Low |
| `tests/test_engine.py` empty — no automated regression coverage | Open | **Highest** — next task; increasingly important now that all four agents exist |

---

*Last updated: 2026-08-07 — Whale implemented and verified (commit `3242717`); shared bankroll clamp added (commit `9b44ff4`). Next: `tests/test_engine.py` conversion, tilt wiring + compounding fix, `PokerEngine.__init__` crash bug.*