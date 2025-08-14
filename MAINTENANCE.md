# Maintenance Runbook

Operational guidance for the Happenstance aggregation + publish pipeline.

## Workflows Summary
| Workflow | Purpose | Schedule | Commits? | Deploys Pages? |
|----------|---------|----------|----------|----------------|
| update-data.yml | Main aggregation (main branch) | 05:00 UTC | Only if COMMIT_DATA=1 & items_changed | No |
| update-data-beta.yml | Beta aggregation (beta branch) | On push/manual | Only if COMMIT_DATA=1 & items_changed | No |
| publish-pages.yml | Pages deploy from docs/ | 05:30 UTC & manual | No (artifact only) | Yes |

## Commit Gating
Set repository or org variable `COMMIT_DATA=1` to enable commits. Leave unset / 0 to suppress.
Manual one-off: rerun workflow with a temporary override using "Run workflow" → specify environment variable if using custom dispatch (future enhancement).

## Force Pages Deploy
Use workflow dispatch on `publish-pages.yml` with `force_deploy=true` to redeploy without item changes.

## Adding a New Profile
1. Edit `config/config_logic.json`, append profile object.
2. Reference it by setting env var `PROFILE=<name>` in workflow or dispatch input (future enhancement).
3. (Optional) Add unique live search URL groups for region.

## Live Search URL Groups
Located in `config/config_logic.json` (url_groups). Rotation logic selects subsets per pass to stay within domain limits. Add new arrays or adjust membership cautiously.

## Dependency Upgrades
1. Bump versions in `requirements.txt`.
2. Recreate virtual environment locally & run quick pass: `MAX_RUN_PASSES=1 python scripts/aggregate.py`.
3. Commit with `chore(deps): bump <package>` and update changelog if impactful.

## Structured Output Schema Changes
1. Update Pydantic models.
2. Update fallback JSON extraction mapping.
3. Increment minor version (0.x -> 0.x+1) & document migration notes in changelog.

## Link Validation Tuning
Environment flags:
- `LINK_HTTP_VALIDATE=1` to enable.
- `LINK_DROP_INVALID=1` to exclude failing entries.
Consider running with validation off if rate-limited or latency spikes.

## Debug Artifacts
Artifacts uploaded each run:
- prompts_* (final concatenated prompt with pass context)
- citations_*.json
- link_validation_*.json
- last_run_raw_*.json / last_run_validated_*.json
- meta.json (includes hashing meta, counts)

## Investigating Empty Outputs
1. Download debug artifacts for the run (Actions UI).
2. Inspect `last_run_raw_*` vs `last_run_validated_*` for data loss due to validation.
3. Loosen validation: `VALIDATION_MODE=soft` (or `off`) temporarily.
4. Adjust sources / url_groups if search coverage thin.

## Pricing Overrides
Set `COST_PER_1K_PROMPT` / `COST_PER_1K_COMPLETION` for ad-hoc cost projection in meta. Leave at 0 for default table.

## Manual Backfill / Historical Snapshots
Temporarily set `COMMIT_DATA=1` and run manual dispatch to capture a versioned snapshot in git, then reset the var to 0.

## Rotating Secrets
1. Add new secret with suffix `_NEW`.
2. Patch workflows to reference new key (or adjust environment mapping logic).
3. Once validated, remove old secret.

## Common Issues
| Symptom | Cause | Resolution |
|---------|-------|------------|
| Branch divergence noise | Timestamp-only commits | Keep COMMIT_DATA=0 or rely on deterministic hashing fix (already applied). |
| No citations | `LIVE_SEARCH_MODE=off` or domain limit gating | Set `LIVE_SEARCH_MODE=auto` and ensure url_groups populated. |
| High duplication | Insufficient pass feedback | Verify gap bullets; increase MAX_RUN_PASSES. |
| Slow runs | Link validation or high pass count | Disable `LINK_HTTP_VALIDATE`; lower `MAX_RUN_PASSES`. |

## Future Enhancements (Track in Issues)
- DRY_RUN mode (build prompts, skip API) for costless planning.
- Versioned JSON snapshots on Pages (timestamped directory per deploy).
- Automated domain normalization + canonicalization.
- Test harness for parsing & hashing.

## Contacts
File issues / PRs on GitHub; mention maintainers in discussions for escalation.
