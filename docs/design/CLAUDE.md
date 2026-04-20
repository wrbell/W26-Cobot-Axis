# docs/design — Design Documents

Software-oriented design docs. Some are **report-bearing** (cited in the final report and Phase 2/3 memos); others are **infrastructure** (CI/CD, dev process) and should not be cited in the student-facing report.

## Bolton-step mapping (for the final report)

| Bolton Step | Report Section | Load-bearing docs here |
|-------------|----------------|------------------------|
| 1. Need | A. Intro | — (see `reqs/initial_scope.md`) |
| 2. Problem analysis | B | — (see `docs/problem_analysis.md`, `docs/latency_analysis.md`) |
| 3. Specification | C | — (see `docs/design_specification.md`, `docs/register_allocation.md`) |
| 4. Possible solutions | D | — (see `trades/*.md`) |
| 5. Solution selection | E | `phase2_deliverables.md` summary |
| 6. Detailed design | F | **`stepper_driving.md`**, **`network_architecture.md`**, **`bridge_enhancements.md`**, `klipper_config.md`, `urscript_programs.md` |
| 7. Working drawings + Phase 3 | G | **`integration_plan.md`**, **`hitl_plan.md`**, `test_procedures.md`, `deployment.md` |
| Outline of everything | — | **`final_report_outline.md`** — canonical skeleton used to build `reports/turn-in/report/report.md` |

## Report skeleton

`final_report_outline.md` is the canonical outline: Sections A–J, word budgets totaling 2000, figure/table/reference lists, team-work split, timeline. When editing the report, propagate changes back here so the two stay aligned.

## Not report content

These are infra — cite only in internal memos or the supplementary README, not in the student-facing final report:

- `ci_cd_guide.md` — three-tier CI/CD (lint, firmware cross-compile, HITL)
- `testing_strategy.md` — pytest tiers + coverage policy
- `phase2_memo_outline.md` — Phase 2 memo layout (superseded once memo is submitted)

## When editing

- `stepper_driving.md` is the canonical stepper subsystem reference (~550 lines). If it disagrees with `src/klipper/printer.cfg`, `printer.cfg` wins — update this doc.
- `integration_plan.md` defines the 8 integration stages referenced from the Phase 3 memo (`docs/phase3/progress_memo_draft.md` Table 1). Keep stage IDs stable.
- `hitl_plan.md` defines `TP-06` (StallGuard HITL), referenced from Report Section G.2.
