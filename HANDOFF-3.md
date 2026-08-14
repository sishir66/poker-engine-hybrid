# PokerEngine — Session Handoff #3

Supersedes `HANDOFF-2.md` for anything they disagree on (same convention
`HANDOFF-2.md` used against the original `HANDOFF.md`). Attach alongside
`HANDOFF-2.md`, `PokerEngine_Blueprint.md`, and `CLAUDE.md`.

`HANDOFF-2.md`'s content (agent internals — Fish/Grinder/QuantGrid/Whale,
the `win_odds` audit, threshold history, the bankroll clamp, tilt
compounding, `from_dict()`, the MLP-retirement decision) is **unchanged
and still authoritative** — nothing in this session touched any of it.
This document covers everything closed *since* `HANDOFF-2.md`: all of
Phase IV through Stage 2 and its post-hardening, plus Stage 3's full
scope, locked and approved but **not yet implemented**.

Also present in the repo but not the current thread of work: `HANDOFF.md`
— a separate, older, commit-log-style document that was updated in
parallel with this session's early Phase IV commits (Stage 0 through the
size-floor fix) using a different format (a running table + "known bugs"
list rather than this narrative style). Its content through commit
`6dc6cbd` is accurate and more granular per-commit than this document —
worth keeping as a reference, but this file is the one written for
picking the work back up in a new chat.

---

## 1. Current state

| Component | State |
|---|---|
| Everything in `HANDOFF-2.md`'s table (Fish/Grinder/QuantGrid/Whale, bankroll clamp, tilt compounding, `from_dict()`, `PokerEngine.__init__`) | Unchanged, still true |
| `check_tilt()` wiring | **No longer blocked.** Wired into `play_hand()` (Stage 2, commit `8faa683`) — called once per seated agent, every hand, using start-of-hand bankroll. See §2. |
| Multi-opponent equity threading (`HANDOFF-2.md` §5, "must be resolved before >2 players") | **Still open, unchanged.** Not touched — everything built since is heads-up only by explicit scope lock. |
| Phase IV Stage 0 (cache-key bug, tie-split bug, `decide()` unification, `Card.__hash__`) | Done, commit `335db89` |
| Phase IV Stage 0.5 (narrow C hand evaluator) | Done, commit `3888071` — 12.6x measured speedup, ~2.62 hr ceiling for 100k heads-up hands |
| Phase IV Stage 1 (`Dealer`, `PotManager`, `Table`, `Ledger`, standalone `check_tilt()` tests) | Done, commit `2c630a1` |
| Phase IV Stage 2 (betting loop, hand state machine, Showdown) | Done, commit `8faa683` — first code that plays an actual hand |
| Post-Stage-2 hardening (undershoot-raise doc, size==0 raise-floor fix) | Done, commits `44cf8c3`, `6dc6cbd` |
| Phase IV Stage 3 (multi-hand session loop) | **Scoped and approved this session — not yet implemented.** See §3. |
| Test suite | **180 tests**, all passing (`tests/test_engine.py`, `tests/test_dealer.py`, `tests/test_hand_runner.py`) |
| Latest commit | `6dc6cbd` — "Fix: floor raise size at 1 chip in `_act()`'s raise branch" |

---

## 2. What closed since HANDOFF2 — Phase IV, Stage 0 through Stage 2

`HANDOFF-2.md` left off with `check_tilt()` wiring genuinely blocked (no orchestration loop existed anywhere) and Phase IV entirely unstarted. That loop now exists. In order:

**Stage 0 — correctness prerequisites (commit `335db89`).** Two latent bugs found while *scoping* Phase IV, not by the existing test suite (both needed a caller that varied `num_opponents` or triggered a 3+-way tie, and no such caller existed yet): `calculate_win_odds()`'s cache key omitted `num_opponents`/`simulations` (stale results on either changing); its tie handling was hardcoded heads-up (`ties/2`), giving `0.5` instead of the correct `0.333` on a forced 3-way chop. Fixed by extending the cache key and extracting `_showdown_credit(our_key, opp_keys)`, crediting `1/k` for the actual number of players sharing the winning key — not `num_opponents+1`, which breaks on a partial tie. Also: `decide()` unified to `decide(pot_size, cost_to_call, min_raise, bankroll)` across all four agents (Fish/Grinder's dead `win_odds` param dropped), `Card.__hash__` added. Two contracts locked here, used everywhere since: **raise-TO semantics** (a caller states a player's new total contribution, never an increment, when talking to `PotManager`) and the **odd-chip-to-first-clockwise-from-button** rule.

**Stage 0.5 — narrow C hand evaluator (commit `3888071`).** `calculate_win_odds()` was spending 96.3% of its cost in Python hand evaluation, projecting ~31–34 hrs for 100k heads-up hands — too slow to ever produce a trustworthy BB/100. Added `evaluate_seven()` (`src/c_core/hand_eval.c`, C99), called only from `calculate_win_odds()`'s inner loop via a ctypes binding with an automatic pure-Python fallback when the (gitignored, platform-specific) `.so` isn't built. Verified against a 20,000-hand random differential test (0 mismatches) plus explicit edge cases. Measured — not projected, after excluding a one-time warmup artifact that had understated the real speedup by nearly half — **12.6x speedup per hand, ~2.62 hrs for 100k heads-up hands.** New finding, not acted on: ctypes marshaling (mostly array construction, not the C call itself) is ~59% of the binding's own cost — flagged as a candidate follow-up, not a blocker. `evaluate_seven()`'s output is a fixed, zero-padded 6-tuple — **never comparable to `get_hand_key()`'s raw variable-length output without truncating first**; `get_best_hand()` and Showdown both still use `Hand`/`get_hand_key()` directly and were never touched.

**Stage 1 — primitives (commit `2c630a1`).** Four independently-testable components, deliberately not integrated with each other yet: `Dealer` (no-replacement shuffled-deck service, injectable `rng`), `PotManager` (cumulative per-player contribution tracking under raise-TO semantics, `split_pot()` implementing the odd-chip rule — chip arithmetic only, no hand comparison), `Table` (N-ready seat rotation, `blind_seats()` heads-up-special-cased), `Ledger` (per-agent BB/100 with a 95% CI, raises below 2 hands). Plus: standalone `check_tilt()` unit test coverage (8 hand-derived cases), discharging a file-level `TODO` that had sat untested since the compounding-bug fix in `HANDOFF-2.md`'s era.

**Stage 2 — betting loop, hand state machine, Showdown (commit `8faa683`).** The first integration stage — wires all four Stage 1 primitives plus `decide()`/`check_tilt()` into an actual heads-up hand. `src/engine/hand_runner.py` (`run_betting_round()`, `play_hand()`) and `src/engine/showdown.py` (`resolve_showdown()`). Locked design decisions, each verified rather than assumed:
- `decide()`'s returned raise `size` is an **increment**, converted to a raise-TO total (`new_total = contribution + size`) before it reaches `PotManager`, clamped by remaining stack.
- Betting-round closure is a **closure predicate over live/actionable seats** (`acted.issuperset(actionable) AND all(amount_to_call(s)==0)`), not a hardcoded 2-player alternation — N-general even though only 2 seats run today.
- `get_best_hand()`'s `cache_sig` includes hole cards, so two contenders in one showdown sharing an engine instance never collide — proven via independent recompute, not assumed from reading the cache-key code.
- No side pots / all-in-for-less can occur in this MVP, and it's a **proof**, not an assumption: heads-up + reset-equal-stacks-every-hand + per-action `clamp_to_bankroll` together guarantee no seat's contribution can ever exceed its own starting stack, so a call is always fully affordable.
- Chip conservation (`sum(deltas)==0`, `awards==total_pot`) is `assert`ed inside `play_hand()` on every hand, not only in tests.
- `check_tilt()` finally has a real call site: once per **every seated agent** (including folders — profit is the negative of whatever they'd contributed before folding), using each agent's **start-of-hand** stack as `bankroll` — never the post-settlement one.

**Post-Stage-2 hardening — two rounds of the same pattern (documented, then a real bug found).** First, the undershoot-raise path (`decide()` returns `("raise", size)` with `size < cost_to_call`, not all-in) got the full traced-and-cited treatment in `HANDOFF.md`: it's left as a genuine under-call, `acted` gets the seat added regardless (not excluded), and the round stays correctly blocked by the *separate* `amount_to_call==0` half of the closure predicate — proven convergent via a live instrumented trace, both in isolation and through a full 4-street `play_hand()`. Documenting this surfaced a **second, more serious case the first pass hadn't covered**: `size == 0` specifically. Unlike `size > 0` (contribution strictly increases every turn, guaranteeing termination), `size == 0` was a complete no-op — same contribution, same `amount_to_call`, nothing forcing progress. That's a genuine, silent-hang risk, not just an odd edge case. Fixed (commit `6dc6cbd`) by flooring the increment: `size = max(1, min(size, stack_left))` — `stack_left` is always `>= 1` for an actionable seat, so the floor never conflicts with the existing upper-bound clamp. Confirmed no-op for any `size >= 1` (all pre-existing `TestClosurePredicate` tests pass byte-for-byte unchanged — diff stat on the test file: `28 insertions, 0 deletions`, only the new test added). Traced live (reproduced again this session, three requests later, finally landed clearly):
```
[1] p1 checks                                    contrib(p1)=2  contrib(p2)=2
[2] p2 raises to 52 (real raise)                 contrib(p1)=2  contrib(p2)=52  amount_to_call(p1)=50
[3] p1 raises by 0 -- FLOORS to 1 chip            contrib(p1)=3  contrib(p2)=52  amount_to_call(p1)=49  acted={p1,p2} (full, but still blocked)
[4] p2 checks (no-op, cost_to_call=0 for p2)      contrib(p1)=3  contrib(p2)=52  amount_to_call(p1)=49  (still blocked)
[5] p1 calls the remaining 49                    contrib(p1)=52 contrib(p2)=52  amount_to_call=0 for both -- CLOSES
```
Round terminates normally after 5 `decide()` calls. No hang.

---

## 3. Stage 3 — multi-hand session loop (scoped and approved, not yet built)

**Scope lock, explicit:** heads-up only (matches everything built so far). Full no-limit min-raise escalation and N>2/side-pot logic are **not** part of this stage — filed under the design doc's §G with no stage number attached, and N>2 specifically requires side-pot work already flagged as non-trivial. Either gets its own scoped stage if picked up, the same way Stage 0.5 was deliberately pulled forward rather than silently absorbed into whatever was next. **Do not fold either into Stage 3's implementation without a fresh, explicit scoping round.**

**Design, `src/engine/session.py`, `run_session(agents, table, engine, num_hands, seed=None, ledger=None)`:** plays `num_hands` in sequence, one shared `Dealer` per hand drawing from a continuing rng stream, `table.rotate_button()` between hands, a session-wide `sum(deltas)==0` check independent of `play_hand()`'s own per-hand asserts. `play_hand()`/`Table`/`Dealer`/`Ledger` need zero changes — Stage 3 is purely additive.

**The randomness audit — a real gap found before any code was written.** `grep -n "random\.\|np\.random" src/engine/agent.py src/engine/simulation.py` confirms: all four agents' dice-roll branches (`Fish`/`Grinder`/`QuantGrid`/`Whale`, 5 call sites total) draw from Python's **global** `random` module; `calculate_win_odds()`'s Monte Carlo sampling draws from **global** `np.random`. Neither accepts an injectable rng anywhere (confirmed by a second grep for `rng`/`Random(` turning up nothing). A stray `random.random()` inside `PokerEngine.make_decision()` is dead code — confirmed unreferenced anywhere in the repo, doesn't affect any real `decide()` path. Consequence: seeding only the injected `Dealer` rng — the original, first-draft design — does **not** guarantee reproducible sessions. Demonstrated empirically, not just reasoned about: two same-seed runs matched on every hand's *cards* (the `Dealer`'s own stream is correctly independent) but diverged in *outcome* starting at hand 1 — an agent's decision differed because the global `random` state entering that decision differed (leftover consumption from hand 0, never reset), which changed fold timing, which changed how many community cards got dealt, cascading forward. **Fix:** `random.seed(seed)` and `np.random.seed(seed)` explicitly at the top of `run_session()`, in addition to the existing injected `Dealer` rng. Re-verified with real `Grinder`/`Whale` (exercising both global sources) across two independent same-seed calls: cards identical, **and now deltas identical too** — full reproducibility, not just card reproducibility. This mutates global interpreter state; accepted as the only lever available without changing `agent.py`/`simulation.py`, which is out of scope for this stage.

**The behavioral-test redesign — a test with no power got caught before it was written.** Original design: a symmetric self-play sanity check (two identical `Fish` vs each other; a `Whale`-CI-vs-`Grinder`-CI width comparison). Rejected: a fold/raise-inversion bug applied identically to both sides of a symmetric matchup still averages to ~0 for both — such a test would pass just as easily against a fully broken `decide()` as a correct one. It only checks engine/dealing fairness (blind assignment, button-seat symmetry), not decision-logic correctness, and shouldn't be sold as the latter. Replaced with a **directional-edge test with demonstrated power**: `Grinder` vs `Fish`, 5000 hands, asserting `Grinder`'s `bb_per_100` mean is positive *and* its 95% CI excludes zero. Proven to actually distinguish correct from broken, not assumed: an `InvertedGrinder` (swaps the two ends of the Chen-threshold logic — folds its best hands, raises its worst) run against the same seed and opponent:
```
CORRECT Grinder vs Fish, n=5000:   grinder =   35.51 +/-  24.98   CI excludes 0: True
INVERTED Grinder vs Fish, n=5000:  grinder = -177.62 +/- 119.50   CI excludes 0: False   sign flipped
```
5000 was chosen as the smallest of {500, 2000, 5000, 20000} tried where the correct implementation's CI first excludes zero (500 and 2000 don't); it also runs in well under a second since neither agent calls `calculate_win_odds()`.

**Still outstanding at implementation time:** the equity-cache decision (whether Stage 0's "no preflop cache needed" call still holds) gets closed with a real `QuantGrid`/`Whale` session's measured wall-clock time against the Stage 0.5 ceiling, not another estimate — this is explicitly part of Stage 3's verification, not yet run.

---

## 4. Explicitly deferred — no stage number attached to any of these

- **Full no-limit min-raise escalation** (minimum legal raise = size of the previous raise/bet, not a flat `big_blind` floor). Stage 2/3 use the flat floor as a documented simplification.
- **N>2 seats.** Requires side-pot logic (`HANDOFF-2.md` §5 already flagged multi-opponent equity threading as a prerequisite; this session's own no-side-pots proof is heads-up-specific and breaks the moment a third seat exists).
- **Side-pot logic itself.** Non-trivial, not started, not designed.

If any of these are wanted, they get their own `/plan` round with their own scope lock — same treatment Stage 0.5 got when it was pulled forward ahead of the rest of Phase I.

---

## 5. How we work — carry this into the new chat

Everything in `HANDOFF-2.md` §7 still applies, unchanged. Two items on that list are worth restating with a concrete example from *this* session, because one of them took three rounds to actually land:

- **The actual terminal output gets pasted back — never a summary, and never "trust me, I already showed this."** The size==0 raise-floor trace (§2 above) was requested four separate times across this session before it was delivered in a form that actually registered. Each time, a summary or a reference to an earlier tool call wasn't sufficient — only the literal printed trace, front-and-center, with nothing else competing for attention in the same message, closed the loop. Do not assume a claim landed because it was true and previously demonstrated; show it again, plainly, if asked again.
- **`/plan` mode for anything touching shared or decision logic.** Every plan this session that touched the betting loop, the raise contract, or a behavioral test got pushed back on at least once before approval, and the pushback was substantive every time: the raise-increment vs raise-TO ambiguity, the `PotManager` cumulative-contribution invariant, the cache_sig collision risk, the undershoot-raise mechanism, the size==0 hang, the randomness audit, and the symmetric-self-play test's lack of power were all caught this way — none were things a first draft got right unprompted.
- **Independent verification before trusting any claimed value — including your own prior claims.** Every number in §2 and §3 above was re-derived this session via an actual run, not carried forward from an earlier description of it (e.g., the raise-floor trace was re-run fresh three times before this document; the behavioral test's power was proven by actually breaking `Grinder` and confirming the test would have caught it, not asserted from the test's design alone).

---

## 6. First message for the new chat

> Continuing PokerEngine. Attached: HANDOFF-3.md, HANDOFF-2.md, PokerEngine_Blueprint.md, CLAUDE.md. Phase IV Stages 0 through 2 are complete and hardened (betting loop, hand state machine, Showdown, check_tilt() finally wired in); 180 tests passing, latest commit `6dc6cbd`. Stage 3 (multi-hand session loop) is fully scoped and approved — heads-up only, global random/np.random seeding fix, Grinder-vs-Fish directional-edge behavioral test — but not yet implemented. Read HANDOFF-3.md first, then HANDOFF-2.md for agent internals, then start Stage 3 implementation per HANDOFF-3.md §3.
