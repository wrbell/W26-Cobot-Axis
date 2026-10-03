# Agent instructions

Other project facts are in `CLAUDE.md`.

## Clarity

Write explanations to Willem in Simplified Technical English.
Write pull request descriptions in Simplified Technical English.
Write commit message bodies in Simplified Technical English.
Write the prose in the README and in the docs in Simplified Technical English.

Use the skill in `.agents/skills/simplified-technical-english/`.
Obey approximately 80% of the STE standard.
Do not obey the full standard.

Code, identifiers, math, command-line output, and quoted error text do not use this standard.

When structure, flow, or architecture is the primary information, use a `mermaid` diagram.
For a large result, give a self-contained HTML explainer.
That HTML file is a temporary aid.
Commit that file only when Willem tells you to commit it.

Make a video explainer only when a person tells you to make the video.
Do not add API keys or secrets.

The script `.agents/skills/simplified-technical-english/scripts/ste_check.py` is an optional check of the manuals.
The check gives information only.
The check does not stop CI.
