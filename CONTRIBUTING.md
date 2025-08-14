# Contributing to Happenstance

Thanks for your interest in improving Happenstance! This document outlines how to propose changes and keep history clean.

## Workflow Overview
1. Fork or create a feature branch from `beta` (integration branch).
2. Name branches `feat/<short>`, `fix/<short>`, or `chore/<short>`.
3. Keep PRs focused; separate unrelated changes (docs vs feature).
4. Ensure aggregation still runs locally (`MAX_RUN_PASSES=1 python scripts/aggregate.py`).
5. Update docs / changelog if you introduce user-visible changes.
6. Open PR → CI runs. Address review feedback. Squash or rebase before merge for linear history.

## Commit Message Style
```
<type>(scope?): concise description

Optional body explaining rationale / trade-offs.
```
Types: feat, fix, chore, docs, refactor, perf, test, ci.

Examples:
- `feat(aggregation): add gap analysis bullet injection`
- `fix(live-search): guard empty domain list before slice`

## Changelog Updates
Add an entry under `Unreleased` (or create new version section if bundling multiple features). The maintainer will finalize version/date during release.

## Running Locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GROK_API_KEY=...  # required
MAX_RUN_PASSES=1 python scripts/aggregate.py
```
Use environment flags to test features:
- `LIVE_SEARCH_MODE=auto`
- `LINK_HTTP_VALIDATE=1 LINK_DROP_INVALID=1`

## Coding Guidelines
- Prefer pure functions; isolate I/O.
- Log artifacts to `debug/` (prefixed for grouping): prompts_, citations_, link_validation_.
- Avoid hard-coding region specifics outside profiles / config.
- Keep public JSON schema stable; if changing fields, note it in changelog and bump minor version.

## Structured Outputs
If adding fields, update Pydantic models and fallback JSON parsing. Provide migration hints in the changelog.

## Tests (Future)
Test scaffolding may be added; until then, emphasize manual verification via debug artifacts.

## Security & Secrets
Never commit secrets. Use GitHub Environment `beta` for API keys. If adding new secrets, document them in README env table.

## Release Process
1. Ensure `CHANGELOG.md` Unreleased section is curated.
2. Create version section with date; bump version badge if added later.
3. Tag release: `git tag -a v0.x.y -m "v0.x.y" && git push origin v0.x.y`.
4. (Optional) Trigger manual publish workflow.

Happy aggregating!
