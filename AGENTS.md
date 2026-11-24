# Oil Observatory — contributor and agent guide

Applies to any contributor or coding agent. Before changing code, read `README.md`, `CODEX_HANDOFF.md` (handoff history; may be dated) and `docs-kevin/00_index.md` (current plan and decisions).

## Application

- Python 3.10+ with PyYAML; vanilla HTML/CSS/JavaScript. Node is optional, for syntax checks only.
- `python serve.py` serves the public information site at http://localhost:8501.
- `python serve.py --research --port 8502` serves the legacy local research dashboard (contains raw test data; local use only).
- `python research.py --help` lists the research pipeline commands (Cofacts, YouTube, annotation, drafts, report). Operating steps are in `docs-kevin/10_operator_guide.md`.
- Existing source code is reference material and may be changed where the requirements call for it.

## Checks before finishing a change

- `python -m unittest discover -s tests -q`
- `python build_public.py` after backend or content changes
- `node --check web/app.js` after JavaScript changes

## Product requirements (document dated 2026-11-19)

- The site has information pages and a simple Q&A tool. Answers come only from previously reviewed content.
- Facts and regulatory wording are reviewed by both the academic advisor and the partner organisation before release. Editing reviewed content changes its hash and invalidates the reviews.
- Public pages must not contain accounts, identifiable quotations, brand comparisons, purchase links, or video- or creator-level details. Video-level summaries belong only in the report appendix.
- Public pages are published under a neutral project name. Do not add organisation names, logos or links to the public site.
- The 20 initial topics are editorial examples, not a measured ranking. Do not present them as research results or create review signatures. Keep the zero-sample state until real, validated annotations exist.
- Required sources: Cofacts and YouTube. The YouTube target is the top 100 relevant videos by views in the study window, excluding ads and brand official channels. Only legally obtained data may be used, under each source's terms, with no paid data purchases.
- The legacy local research mode stays separate from the public site.

## Data, credentials and source control

- Never commit credentials (`.env`, API keys) or collected raw data. Runtime outputs, `observations.json` and the raw/processed/annotation/reports folders under `data-kevin/` are git-ignored.
- Keep drafts, research data and working notes in `data-kevin/` and `docs-kevin/`. Draft answers must not reach the public site before dual review.
- Preserve other people's uncommitted changes. Check `git remote -v` and confirm the intended repository before pushing. Pushing code does not publish the website.
