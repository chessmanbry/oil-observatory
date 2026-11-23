# Oil Observatory

Read `CODEX_HANDOFF.md` and `README.md` before making changes.

## Current application

- Python 3.10+ and PyYAML, with vanilla HTML/CSS/JavaScript.
- `python serve.py` serves the company-spec information site at localhost:8501.
- `python serve.py --research --port 8502` serves the legacy local research dashboard.
- Run `python -m unittest discover -s tests -q` and `python build_public.py` after relevant backend changes.
- Run `node --check web/app.js` after JavaScript changes. Node is only a development convenience.

## Company requirements dated 2026-11-19

The website has information pages and a simple Q&A tool. Public answers must come from previously reviewed content. Both the advisor and company review facts and regulatory wording before release. The editorial approval hash invalidates reviews after content changes.

Keep the public projection free of accounts, identifiable quotations, brand comparisons, and individual video/creator details. YouTube video-level summaries belong in the report appendix. Preserve the separate local research mode.

The initial 20 topics are editorial examples, not a measured Top 20. Real samples and approved answers are currently empty. Do not turn these examples into research results or invent review signatures. Retain the zero-sample state until real, validated annotations are added.

Required sources are Cofacts and YouTube. The YouTube target is the top 100 relevant videos by views within the study window, after excluding ads and brand official channels. Automated discovery, Cofacts acquisition, and full data coverage are pending work. See the handoff for details.

## Source control and runtime data

Do not commit credentials or collected raw data. Current runtime outputs and observations.json are ignored. A fresh checkout falls back to observations.example.json. Preserve user changes and confirm remote identity before pushing to an existing repository. The private GitHub repository is chessmanbry/oil-observatory. Use the authenticated GitHub connector when CLI authentication is unavailable. GitHub synchronization does not publish the website.
