# reports — Capstone Report + Presentation Deliverables

Final course deliverables. Final report due **Thu Apr 23, 2026 (6:00 PM)**; oral presentation **Thu Apr 24, 2026 (6:30–9:30 PM)**.

## Layout

```
reports/
├── template/
│   ├── report/
│   │   ├── report_prompt.md      # instructor prompt, word limit, format rules
│   │   └── design_process.md     # Bolton 7-step (from textbook / syllabus)
│   └── prez/                     # (no template yet)
└── turn-in/                      # deliverable slot
    ├── report/
    │   ├── report.md             # source of truth (markdown)
    │   ├── build_report.py       # python-docx renderer
    │   └── report.docx           # generated
    └── presentation/
        ├── presentation.md       # source of truth
        ├── build_presentation.py # python-pptx renderer
        └── presentation.pptx     # generated
```

## Rules from `template/report/report_prompt.md`

- **≤ 2000 words**, figures/tables **excluded** from count.
- Single PDF + supplementary materials (source code, configs, drawings).
- IEEE-style in-text citations.
- Word Styles (Heading 1/2, Caption, Body) — no Google Docs (per instructor: resizing corrupts figure resolution).
- Editor pass by at least one teammate before submission.

## Build

```bash
python reports/turn-in/report/build_report.py              # → report.docx + word count per section
python reports/turn-in/presentation/build_presentation.py  # → presentation.pptx
```

Markdown is the source of truth — regenerate `.docx` / `.pptx` after every edit. Never edit the Office files directly (they will be overwritten).

## Workflow

1. Edit `report.md` / `presentation.md` directly.
2. Rerun the build script.
3. Open `report.docx` / `presentation.pptx` to spot-check formatting.
4. When satisfied: **Word** → Save As → PDF for final submission.

## What not to do

- Don't invent new prose when `docs/phase2/memo_draft.md`, `docs/phase3/progress_memo_draft.md`, `docs/problem_analysis.md`, `docs/design_specification.md`, `docs/latency_analysis.md`, or `trades/*.md` already has the content. Lift + trim.
- Don't commit generated `.docx` / `.pptx` without first regenerating from the latest markdown.
- Don't exceed 2000 body words — `build_report.py` prints a running total per section to keep you honest.

## Canonical skeleton

`docs/design/final_report_outline.md` — section structure, word budgets, figure list, table list, references, team-work split, timeline. Report and presentation both derive from this.
