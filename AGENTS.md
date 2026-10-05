# AGENTS.md

## Project

W26-Cobot-Axis is the ME 472 (Mechatronics, Winter 2026) capstone project. A
stepper motor drives a pump that works as a 7th axis of a Universal Robots
UR30. The pump dispenses metal paste. The repository is public. Willem reviews
every merge.

The UR30 runs URScript and writes RTDE registers. A Python bridge daemon on a
headless Raspberry Pi reads them and sends G-code to Klipper over its Unix
socket. Klipper drives the stepper through a BigTreeTech SKR Pico (RP2040,
TMC2209 drivers). The system must run standalone, without the optional Pi400
HMI. `docs/agents/project-reference.md` holds the architecture, the hardware,
the repository layout, and the file index.

Main languages: Python, C (Klipper overlay), URScript, and shell.

Read `todo.md` before you start work. It is the master task tracker: the
Bolton 7-step progress, the phase deliverables, the software tasks (written,
to do, needs hardware), and the source code index with status.

Folder rules are in these files. Read the file for the folder you edit:

- `src/bridge/CLAUDE.md`: bridge modules, register names, tests
- `src/klipper_mods/CLAUDE.md`: StallGuard firmware overlay, patch anchors
- `src/urscript/CLAUDE.md`: URScript programs, register sync, manual tests
- `docs/design/CLAUDE.md`: design documents and the final-report mapping
- `reports/CLAUDE.md`: report and presentation sources and builds

## Commands

```sh
pip install -r requirements.txt        # ur-rtde, pytest, ruff
pre-commit install
python -m pytest src/bridge/tests/ -v  # bridge unit tests, no hardware
ruff check src/bridge/
make check    # ruff, pytest (90 % coverage gate), mypy, yamllint, codespell
python3 tools/agents_md_lint.py        # collection check: AI files
python3 tools/check_docs.py            # collection check: README
```

Firmware overlay build (needs `arm-none-eabi-gcc`):

```sh
git clone --depth 1 https://github.com/Klipper3d/klipper.git vendor/klipper
make firmware
```

`vendor/` is git-ignored. `vendor/klipper` is a third-party clone of Klipper.
Use it to check that the StallGuard patches (`src/klipper_mods/*.patch`) apply
to the real Klipper source tree. Do not edit it and do not commit it.

Report and presentation builds (the Markdown files are the source):

```sh
python reports/turn-in/report/build_report.py
python reports/turn-in/presentation/build_presentation.py
```

Deployment runs on the lab hardware only: `bash deploy.sh` on the headless Pi
(`SETUP.md`), and `bash scripts/dev-sync.sh PI_HOST` for the dev bench
(`DEVELOPMENT.md`, `docs/dev_bench_guide.md`).

## Code style

Follow the config files. Do not paste a style guide into this file.

- Python: ruff (`.pre-commit-config.yaml`) and mypy (`pyproject.toml`)
- Markdown: `.markdownlint.jsonc` (permissive on purpose; read its header)
- YAML: `.yamllint` for the workflows; `enforcement/yamllint/.yamllint.yml`
- Editor defaults: `.editorconfig`
- Prose: use the skill in `.agents/skills/simplified-technical-english/`
- Commit messages: `enforcement/commitlint/commitlint.config.js`
- Secrets scan: `enforcement/gitleaks/.gitleaks.toml`

Collection standards live in the private repository `wrbell/standards`.
`.standards.json` records the adopted version. When a standards file and this
file disagree, this file wins. Say that in the pull request body.

Project rules:

- Klipper is the firmware stack (chosen over Lingua Franca; see
  `trades/lingua_franca_vs_klipper.md`). A `[manual_stepper]` section
  controls the single pump axis.
- The folder files above hold the cross-file rules: the RTDE register map,
  `MAX_EXTRUSION_RATE` in two places, and `printer.cfg` over the design docs.
- Follow Bolton's mechatronics 7-step design process: need, problem analysis,
  specification, possible solutions, solution selection, detailed design,
  working drawings. Iteration between steps is expected.
- Team split: Willem does software and EE (RTDE comms, Klipper integration,
  firmware, electrical documentation). Dawood does mechanical (packaging,
  cabling, end effector, procurement).
- The final report has a limit of 2000 words. Figures and tables do not
  count (`reports/CLAUDE.md`).

## Tests

- Bridge: `src/bridge/tests/`, one test file per module. Tests do not touch
  hardware. The fakes are in `src/bridge/tests/conftest.py`. CI fails below
  90 % coverage; the target for the bridge is 100 %.
- URScript: no pytest target. Validate on the teach pendant
  (`src/urscript/CLAUDE.md`).
- Firmware: CI cross-compiles the overlay (`.github/workflows/firmware.yml`)
  and checks the patch anchors every week (`patch-freshness.yml`).

Give each task a check you can run.
Write or update the failing test first.
Show that the test fails, then make it pass.
A test checks correctness. It does not define the solution.
Do not hard-code a value or a special case to pass a test.
If a test is wrong, say so.
For numeric code, keep the simple correct version as a reference test.
Then optimize only while that test passes.

## Pull requests and commits

Use a Conventional Commit subject (`enforcement/commitlint/`).
Open the pull request as a draft. Fill in `.github/PULL_REQUEST_TEMPLATE.md`.
Wait for CI to pass: `ci.yml` (Tier 1), `firmware.yml` (Tier 2), and
`standards.yml` (collection checks).
List each assumption and each open tradeoff in the pull request body.
Keep each change near 100 lines.
Do not edit files outside the task.
A new dependency needs a reason in the pull request.
Do not force-push, rewrite history, delete a branch, merge, or publish
unless Willem asks.

## Security

Do not commit a secret.
Do not put a secret in a prompt or a log.
Do not use a production credential.
Use a test credential with a budget limit.
Run unattended mode only in a sandbox.

This repository is public. Do not commit course handouts, vendor manuals, or
other copyrighted PDFs. `.gitignore` ignores `*.pdf`. List a local PDF in the
`INDEX.md` of its folder (`reqs/INDEX.md`, `docs/provided/INDEX.md`).

## Clarity

Write explanations to Willem in Simplified Technical English. Use the same style
for a pull request description, a commit message body, and prose in a README or
another doc. Aim for about 80 percent of the rules. Full compliance with
ASD-STE100 is not the goal.

The rules are in the standards repository at `standards/writing-ste/ste.md`.
The upstream skill is
[simplified-technical-english](https://github.com/0xpili/simplified-technical-english/tree/1e148d670cba46685ad2b4c3f2354a637a7fdbbe)
(MIT, commit `1e148d670cba46685ad2b4c3f2354a637a7fdbbe`). Link to that skill.
Do not copy the skill into this repository again.

Code, identifiers, math, command-line output, and quoted error text are exempt.

When structure, flow, or architecture is the point, use a mermaid diagram.
For a complex result, offer a self-contained HTML page.
That page is a throwaway file.
Do not commit it unless Willem asks.

Make a video only when Willem asks for a video.
Do not add an API key or a secret.

`scripts/ste_check.py` in the upstream skill is an optional check on docs.
Do not use it as a CI gate.

<!-- standards:begin -->
## Collection standards

Every project under `/Users/willem/Code` follows the shared standards in
`/Users/willem/Code/standards/` (index: `standards/STANDARDS.md`; future
standards: `standards/ROADMAP.md`).

- **Presentations:** build every deck from
  `standards/powerpoint template/Willem-Default.potx` (theme "Helena": Neue Haas
  Grotesk Text Pro, 16:9, black on white with a gray ramp, template v2). Spec:
  `standards/powerpoint template/STANDARD.md`. Generate with
  `standards/powerpoint template/house_style.py` (open
  `Willem-Default-Base.pptx`, never the `.potx`) and gate with
  `standards/powerpoint template/deck_checks.py` before calling a deck done.
- **Deck rules:** no speaker notes in submitted decks; editable shapes, not
  chart images; numbered, linked superscript citations with a final References
  slide; no bottom rules, citation strips, or page counters; footer text only
  when a course or client requires it (for example `ME460 HWx`), which overrides
  the default of no footer; export the deliverable PDF with native PowerPoint
  and use LibreOffice renders only for QA.
- **Everything else:** do not invent facts, dates, or numbers; mark unknowns TBD
  and point at the source. Keep copyrighted course material out of git. This
  block is managed by `standards/tools/apply_standards.py`; edit
  `standards/ai-files/BLOCK-root.md`, not this copy.
- **AI use (school work):** no AI-generated or AI-modified images in any school
  deliverable; AI-written deliverable text only with written adviser
  pre-clearance (`docs/ai-clearances/`); never cite an AI tool as a source;
  never edit graded report text (the repo's `protected-paths.txt`; example:
  `standards/enforcement/senior-design-repo/sd-protected-paths.txt`). AI-use
  logging and attestation are opt-in per repo via `ai-attestation-roots.txt`;
  see `standards/standards/ai-use-disclosure/ai-use-disclosure.md`.
- **AI files:** one `AGENTS.md` (≤ 200 lines, Clarity verbatim); `CLAUDE.md` is
  `@AGENTS.md`. Gates: `standards/tools/agents_md_lint.py`, `ai_file_lint.py`.
<!-- standards:end -->
