# Mutation testing pilot — 23/11/2026

Coverage says which lines the tests run; mutation testing says whether they would notice a
bug there. The tool plants one small change at a time (a `>=` for a `>`, a `0` for a `1`,
an empty string) and runs the tests: a change some test fails on is **killed**, one every
test passes with **survived**. The mutation score is killed ÷ all mutants.

This pilot covers the rules and calculations that decide what a municipality sees and
publishes, each judged by its own tests.

## How to run it

| Side | Tool | Command | Scope and report |
|---|---|---|---|
| Backend | mutmut 3.8 | `cd backend && uv run mutmut run --max-children 1`, then `uv run mutmut results` (survivors), `uv run mutmut show <name>` (the change), `uv run mutmut browse` | `[tool.mutmut]` in `pyproject.toml`; results in `backend/mutants/` |
| Frontend | Stryker 10.1 with the vitest runner | `cd frontend && npm run mutation` | `stryker.config.mjs`; report in `frontend/reports/mutation/index.html` |

mutmut only mutates Python, so the frontend uses Stryker, its TypeScript counterpart.

- **One mutant at a time on the backend** (`--max-children 1`): the tests share the
  `gobernar360_test` database and empty it after each test, so parallel mutants would fail
  each other's tests and inflate the score. `process_isolation = "forkserver"` starts every
  mutant from a process without open database connections.
- **Stryker and TypeScript 7:** Stryker's step that rewrites tsconfig paths pointing outside
  its sandbox uses the TypeScript 5 API, gone in TypeScript 7; our tsconfigs point nowhere
  outside, so it is skipped (`tsconfigFile: ''`).
- **Time on this machine (4 cores):** backend 581 mutants in about 1 h 40 min; frontend 346
  mutants in about 52 min (both ran at the same time). Too slow for every commit: run it
  nightly or before a release, or on the files a change touches.

## Results

| Backend module | Mutants | Killed | Survived | Score |
|---|---:|---:|---:|---:|
| `platform/indicators.py` (deviation, on track, months, evolution, combined) | 360 | 343 | 17 | 95.3 % |
| `dashboards/projects/rules.py` (delayed, alerts, progress) | 26 | 25 | 1 | 96.2 % |
| `dashboards/environment/rules.py` (year figure, achievement) | 66 | 59 | 7 | 89.4 % |
| `platform/formatting.py` (Argentine numbers and dates in the PDF) | 116 | 101 | 15 | 87.1 % |
| `platform/masking.py` (small counts on the public page) | 13 | 10 | 3 | 76.9 % |
| **Backend total** | **581** | **538** | **43** | **92.6 %** |

| Frontend file | Mutants | Killed | Survived | No test reaches it | Score |
|---|---:|---:|---:|---:|---:|
| `platform/indicators/format.ts` | 65 | 63 | 2 | 0 | 96.9 % |
| `platform/format.ts` | 67 | 58 | 9 | 0 | 86.6 % |
| `platform/indicators/IndicatorCard.tsx` | 93 | 56 | 33 | 4 | 60.2 % |
| `public/PublicIndicatorCard.tsx` | 37 | 23 | 12 | 2 | 62.2 % |
| `platform/indicators/Sparkline.tsx` | 84 | 29 | 55 | 0 | 34.5 % |
| **Frontend total** | **346** | **229** | **111** | **6** | **66.2 %** |

## What the survivors say

Not every survivor is a gap: some changes cannot alter behaviour ("equivalent mutants").

**Worth a test now (privacy):** `masking.py` survives three changes. No test checks that a
count of exactly **1** is masked (the rule could start at 2 unnoticed), that a count equal to
the threshold is shown, or that a percentage is never masked.

**Real, smaller gaps (backend):**

- Project progress: the test data gives the same result for `100 × done ÷ total` and
  `100 ÷ done ÷ total`.
- Combined indicators: history when only one of the two parts has a snapshot; skipping a
  combined indicator whose dashboard is not installed (a `break` would also hide the rest).
- Evolution: a target of 0 (the deviation ratio), an indicator's unit in the answer.
- Environment achievement with a target of 0; PDF formatting of percentages with decimals
  and of the default number of decimals.

**Equivalent, no action (about 10 of the 43):** e.g. `sum(values)` against
`sum(values, Decimal("0"))`, fetching one more month of history than the twelve shown, a `>`
that became `>=` where zero was already handled a line before. The two survivors of
`indicators/format.ts` are of this kind, so that file is effectively at 100 %.

**Frontend:**

- `Sparkline.tsx` (34.5 %): tests count its lines but never check where points are drawn
  (scale, gaps, the flat-series case).
- `IndicatorCard.tsx`: the up/down arrow, the "Justo en la meta" text, opening the detail by
  clicking the card body, the chart button not also triggering the card, and closing the
  detail are never checked.
- `platform/format.ts`: `todayIso()` is untested; the empty-value guards are only reached
  through other helpers.
- Most other survivors change styling only (colours, sizes, tooltip settings): low value.

## Recommendations

1. Add the three masking tests: they guard the "no personal data" promise of the public page.
2. Fix the backend test data that hides progress and combined-indicator mistakes.
3. Decide whether the sparkline's drawing deserves tests; it is decorative, with the same
   numbers shown as text.
4. Run mutation testing nightly, scoped like this pilot, and track the score per module
   rather than a single project-wide number; then widen the scope module by module.
