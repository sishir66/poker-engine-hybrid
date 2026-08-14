# PokerEngine — Session Handoff #2
 
Supersedes the original `HANDOFF.md` for anything they disagree on. Attach
alongside `PokerEngine_Blueprint.md` and `CLAUDE.md`.
 
This document covers the sessions in which: `calculate_win_odds()` was fixed,
QuantGrid Option B landed, Whale was built, the bankroll clamp was discovered
and fixed, the tilt-compounding bug was fixed, `PokerEngine.__init__`'s crash
was fixed, `from_dict()`'s subclass bug was fixed, and `tests/test_engine.py`
went from a one-line stub to a real suite.
 
---
 
## 1. Current state — all four agents are real, no placeholders left
 
| Component | State |
|---|---|
| Fish | Complete, verified |
| Grinder | Complete, verified |
| QuantGrid | Complete — Option B, real Monte Carlo `win_odds` (no longer a placeholder) |
| Whale | Complete, verified |
| `calculate_win_odds()` | Fixed and verified |
| `clamp_to_bankroll()` | New, in `risk.py`, applied to all four agents |
| Tilt compounding | Fixed via `base_aggression` |
| `PokerEngine.__init__` | No longer crashes on missing model files |
| `from_dict()` subclass bug | Fixed via `_restore_state()` |
| `tests/test_engine.py` | ~110 tests, all passing |
| `check_tilt()` wiring | **Blocked** — see §5 |
 
Every bug on the original priority list is closed, plus every bug discovered
along the way. Nothing in the four agents is a stub, a placeholder, or an
unverified assumption.
 
---
 
## 2. Agent reference — what each one is and why
 
### Fish — loose-passive, deliberately biased
- `score_hand()`: legacy heuristic written *before* any formula research,
  tuned only by eyeballing hand rankings. Repurposed intentionally as Fish's
  "brain."
- **Preserved biases (personality, not bugs):** flat +30 for any pocket pair
  regardless of rank; `calculate_high()` actually returns the LOW card;
  `calculate_difference()` uses `value % 14` not true rank distance;
  double-penalty for offsuit + low kicker.
- **One real bug patched:** `% 14` made AK/AQ/AJ/AT compute the *maximum* gap
  penalty (backwards). Patched for those four only — A2–A9 keep the quirk
  intentionally.
- **One deliberate tuning:** double-penalty threshold moved `<10` → `<9`, so
  A9o escapes it (was 5, now 14). Explicitly tuning, not a bug fix.
- **One real bug fixed:** an unconditional 8% fold on *any* hand scoring ≥20,
  including AA. Removed. This is the origin of the standing "no
  unconditional/score-independent branches" rule (Blueprint §9.4).
- `decide()` uses Fish's own cached score, **not** `win_odds` — deliberate.
  Fish's whole personality is acting on its own biased self-assessment.
- Reference values: AA=78, AKs=63, AKo=43, A9o=14, A8o=6, A5s=34, 77=44,
  KQs=58. Note 77 (44) > AKo (43) — a real, deliberate emergent quirk.
### Grinder — tight-aggressive, disciplined heuristic
- `score_hand()`: calls `chen_score()` directly from `preflop.py`.
- `decide()`: Chen <7 fold / 7–9 raise 30% call 70% / ≥10 raise 80% call 20%.
  Free-check path: <7 check / 7–9 raise 25% / ≥10 raise 60%.
- Chen's pair floor of 5 means 22–66 all fold to any bet. **Accepted, not a
  bug to fix** — it's a conscious tight stance.
- Chen reference values (hand-verified): AA=20, AKs=12, AKo=10, KQs=10, 77=7,
  JTs=8, A9o=5, A2s=A3s=A4s=A5s=7 (documented tie), 95s=4, 72o=0, AQs=11,
  AJs=10, ATs=8.
### QuantGrid — the mathematically rigorous agent (Option B)
- **Was** a placeholder reusing Chen — scoring identical to Grinder. **No
  longer.**
- `score_hand()` still calls `chen_score()`, but the return value is
  **vestigial** — decide() ignores it. Its real job is caching
  `_hole_cards` / `_community_cards` for `decide()` to consume.
- `decide()` computes `win_odds` internally by calling
  `self._engine.calculate_win_odds(...)`, then derives `kelly_f` from the
  *actual* pot odds for that decision.
- **Thresholds:** `kelly_f < 0.05` → fold; `0.05 ≤ kelly_f ≤ 0.35` → raise 30%
  / call 70%; `kelly_f > 0.35` → raise 80% / call 20%.
- **Free-check path** (`cost_to_call == 0`) gates on `win_odds ≥ 0.50` instead,
  because `calculate_kelly_fraction()` hardcodes a return of 1.0 when
  `cost_to_call <= 0` — so `kelly_f` carries no information there.
- `kelly_alpha = 0.25`. `__init__(self, engine)`.
- **Signature divergence:** `decide()` drops the `win_odds` parameter that the
  base class declares. Deliberate, documented — callers passing it positionally
  get a loud `TypeError` rather than silent misbehavior.
### Whale — deep-stack maniac, hand-aware but reckless
- Uses **real `win_odds`**, same signal as QuantGrid — explicitly *not* Chen.
  The intent is "understands the game, has enough money not to care," **not**
  "rich Fish." A heuristic signal would have made it the latter.
- `kelly_alpha = 1.0` (no fractional dampener), `aggression = 1.2`.
- **Fold floor `kelly_f < 0.03`** — only slightly looser than QuantGrid's 0.05
  (≈1–1.6 percentage points of win probability across b=1/2/5). Folds a strict
  subset of QuantGrid's folds (10/27 vs 15/27 on the standard boundary set).
- **Raise-weighted threshold stays at 0.35**, identical to QuantGrid. The
  recklessness lives in *sizing*, not in what it's willing to continue with.
- Sizing: `bankroll * kelly_f * kelly_alpha * aggression * uniform(0.8, 1.6)`,
  then clamped to bankroll.
- Free-check path uses a **pot-relative overbet** (`pot_size * 1.5 *
  aggression`) rather than the Kelly path — because with `kelly_f` hardcoded to
  1.0 and `kelly_alpha = 1.0`, the Kelly path would shove the entire stack
  every single time.
---
 
## 3. Decisions we made ourselves (and why) — the important history
 
These are the judgment calls. They are not in the original Blueprint's design
and they were not obvious; each came out of catching something wrong.
 
### 3a. The `win_odds` audit — QuantGrid's sizing was floating
The Kelly *formula* in QuantGrid was correct all along, but `win_odds` was a
caller-supplied parameter **with no real source**. Test output that looked
meaningful (AA sizing to 203, 77 to 45) came from a human hardcoding `0.85`
into a test script because they knew AA's real equity — not from anything
QuantGrid computed. No `chen_score → win_odds` mapping ever existed anywhere in
the code; the two paths shared no data. Nobody had noticed because the numbers
*looked* plausible.
 
**Lesson that generalizes:** correct math applied to an unverified input is not
correctness.
 
### 3b. Fixed `win_odds` thresholds are pot-odds-blind — the core correction
The first Option B plan proposed `win_odds < 0.40 → fold` and `≥ 0.55 → raise`,
justified with algebra at a **fixed `b = 2`**. That's wrong, because
`b = pot_size / cost_to_call` changes every decision and breakeven is
`p = 1/(b+1)`:
 
- At `b = 1`, breakeven is 50% — a fixed 0.40 floor calls at 42%, which is -EV.
- At `b = 5`, breakeven is 16.7% — a fixed 0.40 floor folds hands that are
  comfortably +EV.
**Fix:** gate on `kelly_f`, which already folds win probability and real pot
odds together, instead of a flat probability cutoff. `kelly_f == 0` *is* the
exact breakeven signal, already computed correctly by
`calculate_kelly_fraction()`'s `max(0, ...)` clamp.
 
This same trap was then re-attempted once (a "raise the floor to 0.35" idea that
would have reintroduced a flat `win_odds` cutoff) and caught again. **Any
proposal to gate a decision on a fixed `win_odds` number should be treated as
suspect.**
 
### 3c. The chosen threshold values are personality tuning, not derived truth
- `kelly_f < 0.05` fold (QuantGrid) — a deliberate safety margin *above* pure
  breakeven. "Don't call razor-thin +EV spots."
- `kelly_f > 0.35` raise-weighted — raised from the 0.30 that fell out of the
  original derivation, to make the aggressive tier a tighter bar.
- `kelly_f < 0.03` fold (Whale) — slightly looser than QuantGrid, not
  degenerate.
**All three are explicitly starting points**, to be revisited once Phase IV
produces real BB/100 data. Same category as Fish's A9o threshold tuning: a
personality choice, documented as such, *not* a derived constant. Do not treat
them as settled.
 
### 3d. The bankroll clamp — found while building Whale
Nothing anywhere clamped a raise to available bankroll. Fish and Grinder size
off `pot_size` and never reference bankroll at all (bankroll=100, pot=500 →
Fish bets 375, Grinder bets 500). All four could exceed the stack whenever
`min_raise > bankroll`.
 
**Fix:** `clamp_to_bankroll(raise_size, bankroll)` in `risk.py`, shared by all
four agents. **Ordering matters and is non-obvious:** the clamp must be the
**outermost** operation, applied *after* `max(min_raise, ...)` flooring —
because `min_raise` itself can exceed a short stack.
 
- Correct: `min(1000, max(1500, 600))` → 1000 ✓
- Wrong: `max(1500, min(1000, 600))` → 1500 ✗
Verified that Fish/Grinder/QuantGrid produce **bit-identical** output to before
the change in normal play; only the previously-overflowing cases changed.
 
### 3e. Tilt compounding
`aggression *= 1.5` had no baseline to reset against, so tilting twice before
cooldown compounded permanently (1.5× → 2.25× → …). Fixed with a
`base_aggression` field set once at `__init__` and never mutated; tilt now does
`aggression = base_aggression * 1.5` (assignment, not `*=`), and cooldown resets
to exactly `base_aggression`. Repeated tilts are now idempotent.
 
Note Whale's `base_aggression` is **1.2**, not 1.0 — so a tilted Whale is 1.8.
Tilt multiplies from each agent's own baseline, not a universal one.
 
### 3f. `from_dict()` subclass fix
`Agent.from_dict()` pushed six kwargs through `cls(...)`. Fish and Grinder
accept **zero** kwargs; QuantGrid and Whale accept only `engine`. All four
raised `TypeError`.
 
**Fix:** split construction from state restoration. `Agent._restore_state(d)`
applies saved fields onto an already-built instance; each subclass's
`from_dict()` constructs itself normally then calls it.
`QuantGrid.from_dict(d, engine)` / `Whale.from_dict(d, engine)` take an extra
required positional — a deliberate Liskov divergence, exactly parallel to the
already-accepted `decide()` divergence. An engine-less QuantGrid is a broken
object, so failing loudly at reconstruction beats a zombie instance.
 
`engine` is correctly **not** serialized (live runtime dependency). Neither are
`_cached_score` / `_hole_cards` / `_community_cards` — those are mid-hand
scratch state; persisting them would mean loading an agent that thinks it's
still holding cards from a finished hand.
 
### 3g. MLP / PyTorch — retired, but scaffolding deliberately kept
Hand evaluation was originally a trained PyTorch MLP; it was replaced with
deterministic `get_hand_key()` tuple comparison because the MLP's scalar 0–9
output **collapsed all within-category kicker information** (two different Two
Pair hands both returned "2"), making kicker comparison structurally impossible
downstream. Nothing in the codebase reads `self.model` or `self.scaler` anymore
— verified by exhaustive search.
 
**But the scaffolding is intentionally not deleted**, because there are two
legitimate future ML use cases that are genuinely different in kind from hand
evaluation: opponent modeling / range prediction (§5.7) and board-texture
classification (§4.6's `M_texture`). Those are prediction-under-uncertainty from
noisy behavioral data — real ML problems. Hand ranking never was.
 
---
 
## 4. Verified benchmark values (use these, don't re-derive from scratch)
 
- AA vs random, heads-up: **85.75%** (reference 85.2%; accept 0.82–0.88)
- AKs **67.70%** > KQs **62.43%** (directional only, Monte Carlo variance)
- Forced-tie on a complete Broadway board (A♠K♥Q♦J♣T♠): **exactly 0.5**, zero
  variance. No flush possible (max 4 spades reachable), no higher straight
  possible (Ace already top), any board-derived pair/trips still loses to the
  straight — so both keys are always `(4, 14)`.
- Simulation integrity: wins + ties + losses == simulations (4216 + 40 + 744 =
  5000)
**Tie convention:** `(wins + ties/2) / simulations`, denominator always
`simulations`. Standard poker equity convention; a split pot returns half value.
**This is only correct heads-up** — see §5.
 
---
 
## 5. Open items and known gaps
 
### Blocked
- **`check_tilt()` wiring.** Genuinely blocked, not deprioritized. It needs
  post-hand-resolution profit/loss, and *no orchestration loop exists anywhere
  in the repo* to supply it (Phase IV not started). Verified by repo-wide
  search. Do not re-attempt wiring without first checking whether Phase IV
  has landed. Do not invent a fake hand loop to have somewhere to put the call.
### Must be resolved before Phase IV can run with >2 players
- **Multi-opponent equity threading.** `decide()` has no idea how many live
  opponents are in the hand, and `calculate_win_odds()` is called without an
  explicit `num_opponents`. QuantGrid and Whale would compute heads-up-shaped
  equity while making decisions in multi-way pots — systematically
  overestimating their edge and playing far looser than their thresholds
  intend. Three concrete pieces: (1) thread live-opponent count into
  `decide()`, (2) pass it to `calculate_win_odds()`, (3) re-derive tie handling
  — a 3-way tie needs `1/k` credit, not `0.5`.
  **There is no closed-form shortcut for this.** `p^n` is wrong: shared board
  and card removal create correlation between "beat A" and "beat B." Real tools
  all simulate per-scenario. The fix is threading a real count into the Monte
  Carlo that already exists, not finding a scaling heuristic.
### Not started
- **Phase IV** — cash/tournament environments, multi-agent hand loop, BB/100,
  ICM survival. This is what produces an actual *result* to talk about.
- **Phases I–III** — C core, FFI, signature caching. Performance work, lowest
  urgency.
- **Recovery third state** (§5.2 point 4) — post-tilt aggression dips *below*
  baseline before renormalizing. Plus a newer related idea: after a
  rebuy-from-bust, the tilt **trigger threshold** itself could tighten
  temporarily (e.g. 50% → ~30% of bankroll) representing increased fragility —
  "state resets, but you're more prone to it." Sibling mechanic to recovery,
  not a separate feature.
- **Phase V** — QuantGrid cross-session empirical hand memory.
- **§5.7** — within-session opponent adaptation (`observe()`, VPIP tracking).
  Note: nothing currently lets any agent perceive another's actions, so any
  "psychological pressure" mechanic is inert until this exists.
### Small / housekeeping
- `generate_boats()` indentation bug in `generate_dataset.py` (low, dataset-gen
  only).
- `seaborn` is imported at module level in `simulation.py` but isn't installed
  anywhere and there is **no requirements file at all**. Worked around in tests
  with a `sys.modules` shim.
- MLP deletion decision — deliberately deferred, see §3g.
---
 
## 6. Test suite
 
`tests/test_engine.py`, ~110 tests, all passing. Organized into ~10 classes by
source. Every assertion traces to a value verified earlier in the project —
**no invented "expected" values.**
 
Two infrastructure choices worth knowing:
- **`FakeEngine`** — a duck-typed stand-in returning a fixed `win_odds`. Used
  for all QuantGrid/Whale threshold tests so they land *exactly* on documented
  breakpoints. Real Monte Carlo noise (±1pt) can flip a decision branch near a
  threshold; this makes those tests deterministic. Separately, Group 4 tests the
  real engine with tolerance bands — the two concerns are deliberately split.
- **`PokerEngine.__new__` bypass** — used for real-engine tests to isolate
  `calculate_win_odds()` from construction machinery. Kept even after the
  `__init__` crash was fixed, because coupling those tests to file I/O would add
  a dependency for zero added coverage.
**No coverage for `check_tilt()`'s trigger logic** — explicit TODO at the top of
the file. Its design exists in the Blueprint but was never confirmed with
printed output, and tests were not written against unverified spec text.
 
---
 
## 7. How we work — carry this into the new chat
 
- **Prompts are written and reviewed before running.** Claude Code runs them,
  and the **actual terminal output gets pasted back — never a summary.** This
  has caught real bugs repeatedly.
- **Every math/heuristic value is independently derived before it's trusted**
  (Blueprint §9.6). This caught a wrong Chen reference value (77), a
  reverse-engineered K=7, an invented "wheel exception," an invented "Ace = rank
  12" hack, and the fixed-`win_odds`-threshold error. **A supplied "expected"
  value is a hypothesis, not ground truth.**
- **`/plan` mode for anything touching shared or decision logic.** Plans get
  read and pushed back on before approval — several have been materially wrong
  on first draft and correct only after a round of correction.
- **Manual mode over auto** for design-judgment tasks; auto is fine for trivial,
  single-file, no-judgment work.
- **`opusplan`** is the configured model alias — Opus reasons during plan mode,
  Sonnet executes after approval.
- **Implementation and documentation are separate commits.** Always.
- **Scope creep gets caught and rejected.** Adjacent work gets logged as a
  documented future item, not bundled in.
- **When a task surfaces an unrelated bug, it gets written into the Blueprint's
  §10 table** — not fixed inline, not left as a chat footnote.
---
 
## 8. Note on phase ordering
 
Actual work diverged from the Blueprint §8 phase numbers: Phases V, VI, and VII
are done while I–IV are untouched. This was deliberate, not drift. The original
sequence assumed a correctness baseline from Phase 0 that turned out not to
hold — `calculate_win_odds()` returned untrustworthy output, QuantGrid's sizing
was floating, nothing clamped to bankroll. Building a C core (Phase I) on top of
a Monte Carlo function that silently returned garbage would have optimized a
wrong answer. Correctness jumped the queue on purpose.
 
---
 
## 9. First message for the new chat
 
> Continuing PokerEngine. Attached: HANDOFF-2.md, PokerEngine_Blueprint.md,
> CLAUDE.md. All four agents (Fish, Grinder, QuantGrid, Whale) are complete and
> verified; every bug from the original list is closed; ~110 tests passing.
> Read all three files, then answer the context questions I'm pasting below
> before we start anything.