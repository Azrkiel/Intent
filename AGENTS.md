# Prompt Caller project instructions

## Commit cadence

- Commit after each small, coherent, verified milestone: a feature, a regression
  fix, or a documentation update. Do not batch a whole session into one large commit.
- Run the checks relevant to that change before committing. Keep failing experiments
  uncommitted until resolved; do not skip checks to meet a time interval.
- Separate unrelated changes. Use descriptive commit messages and report checkpoint
  hashes when handing work back to the user.
- Local commits are authorized. Pushes, pull requests and releases require task scope
  that includes those actions.
- Never commit `.env`, credentials, certificate bundles, session data, generated apps
  or evaluation reports. Runtime artifacts belong in the ignored `.data/` directory.

## Architecture constraints

- The orchestrator owns ledger IDs, source checks, impact scores and readiness.
  Models return validated deltas; they never replace the whole ledger.
- A confirmed requirement needs an exact quote from the relevant user turn.
- Failed extraction or critic passes must not open the build gate. New utterances
  invalidate playback approval, the compiled brief and the displayed build result.
- Demo responses and demo builds must stay labeled. Never fall back from live mode
  to scripted output, or charge a restored demo session after switching server mode.
- Keep the default runtime on loopback. The app has no account authentication.
- The current coding adapter produces self-contained HTML apps. Do not claim it
  implements a generated backend or cross-device sync.

## Verification

- Backend changes: `uv run pytest -q` and `uv run ruff check backend`.
- Frontend behaviour: `npm test`, `npm run typecheck`, and `npm run build`.
- Pipeline smoke without API credits: `npm run eval:demo`.
- Documentation-only changes: check paths, commands and `git diff --check`;
  do not rerun the full application suite for prose changes.
- Live smoke: `uv run python -m backend.smoke`. Requires `NEBIUS_API_KEY`.
  Never print keys or treat scripted evaluation results as model-quality evidence.
- Do not run a production build against an active dev server's `.next` directory.
  Stop the owned dev server first, then restart it after verification if needed.
- Read `frontend/AGENTS.md` and the installed Next.js guides before frontend edits.
