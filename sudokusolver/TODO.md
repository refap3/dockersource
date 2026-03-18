# Sudoku Tutor — Feature TODO

Brainstormed 2026-02-24 via 3 parallel agents.

---

## Quick Wins (Low complexity)

- [ ] **Daily Puzzle + Streak Calendar**
  Seed puzzle from `random.seed(date.today().isoformat())`. Calendar view tracks streaks with color intensity (green=no hints, yellow=light hints, orange=full hints, gray=missed). Persists to JSON. No server required.

- [ ] **Puzzle Difficulty Analyzer**
  After loading any puzzle, run full strategy pipeline in batch and report: strategies used, how many times each fired, numeric rating, and "bottleneck strategy" (hardest single technique required). All solver logic exists — just counting + a report panel.

- [ ] **Candidate Annotation Layer**
  User fills a parallel candidate grid manually; compare against solver's correct set. Extra candidates = amber, missing = red. "Sync" button explains each correction. Teaches foundational elimination step most tutors skip.

- [ ] **Candidate Confidence Voting**
  In play mode, mark each digit entry: certain / think so / guessing. Post-game shows calibration score (certain-and-right vs. certain-and-wrong). Makes overconfident guessing visible and trainable.

---

## Medium Effort, High Impact

- [ ] **Hint Ladder System**
  Replace current 4-level hint with 3-tier gate: A = region only ("look at row 4"), B = strategy name only, C = exact cells highlighted but digit withheld. Must take each tier before unlocking next. Preserves the "aha moment." Existing explanation text can be split with light refactoring.

- [ ] **Assumption Mode (Bowman's Bingo)**
  Click any cell, enter trial digit, branch from that state. Subsequent deductions get a colored "assumption chain" badge. Contradiction = highlight conflict cells + one-click rollback. Multiple nested branches. Teaches methodical trial-and-error for puzzles that exhaust analytic strategies.

- [ ] **Mistake Autopsy Screen**
  Post play-mode: timeline scrubber through every move. Incorrect entries annotated in red with the strategy that would have solved it cleanly shown inline. Reuses existing board renderer and strategy engine.

- [ ] **AIC / Chain Step-Through Replay**
  Tier 5 chains currently shown as static highlight. Record each link (strong→weak→strong) as a discrete animation frame; play back one node at a time with sidebar explaining why each link is strong or weak. Most impactful feature for teaching advanced technique.

- [ ] **Coloring / Medusa Coloring Teacher**
  User clicks a digit; tool propagates two-color assignments across conjugate pairs. Same-color collision in a unit = elimination. Toggle Simple Coloring vs. 3D Medusa. Visual bridge between Tier 3 patterns and Tier 5 chains.

---

## Larger Bets (High complexity)

- [ ] **Strategy Drill Mode** ⭐ (both strategy and UX agents flagged this independently)
  Dedicated training mode: boards stripped to minimal context for exactly one technique. User identifies pattern and marks eliminations. Scores: correct strategy type, correct cells, correct digits — tracked per strategy over time. Hard part: auto-generate clean drill positions by saving mid-solve board states tagged with the next-firing strategy.

- [ ] **Adaptive Difficulty Engine**
  Track which strategies needed hints, mistake count, time-per-cell. Select next puzzle weighted toward the player's weak strategies. Generator and strategy engine already exist; new work is a player profile dict + selection heuristic.

- [ ] **Onboarding Campaign ("The Path")**
  20 hand-crafted micro-puzzles, one new concept per step, as a campaign map. First 5 = 4×4 naked singles only; by node 20 = full 9×9 with hidden pairs. Brief animated intro before each puzzle. Fixes the biggest retention problem: new users dropped into a full 9×9 with no scaffolding.

- [ ] **ALS Highlighter (Tier 6 Extension)**
  Almost Locked Sets: N cells in a house with N+1 candidates. Detect ALS-XZ and ALS-XY-Wing eliminations. Outline valid ALS groups on board; click to see candidate set; show if any ALS pair produces an elimination. Establishes clear growth path beyond current Tier 5 ceiling. Needs bounded subset enumeration for performance.

---

## Priority

| Effort | Best ROI |
|--------|----------|
| Low | Daily Puzzle + Streaks, Difficulty Analyzer |
| Medium | Hint Ladder, Assumption Mode, Chain Replay |
| High | Strategy Drill Mode, Onboarding Campaign |
