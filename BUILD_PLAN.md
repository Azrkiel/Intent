# Prompt Caller implementation

Working branch: `feat/prompt-caller`. Target: a local, single-user vertical slice.

1. Evidence and state: Pydantic contracts, quoted ledger deltas, ranking, readiness,
   traceability, and SQLite persistence. Verify source protection and fail-closed gates.
2. Narrow model passes: Nano extraction/playback, six parallel Super critics,
   Super ranking/verification, Ultra compilation. JSON validation and one repair retry.
   Explicit deterministic demo provider; no silent fallback after live failures.
3. API: streamed turn stages, one active question, revision-bound playback approval,
   cached compilation, session restoration, token usage and cost estimates.
4. Interface: conversation and live ledger, understanding meter, question options,
   ranking inspector, playback correction, transcript/spec comparison, browser speech.
5. Agent adapter: guarded Claude Code subprocess in a separate generated repository,
   JSON stream logs, timeout/budget limits, local HTML result preview and file download.
6. Proof: eight annotated evaluation fixtures and a live evaluation runner with a
   single-prompt baseline. Demo fixtures test plumbing; report no model-quality results
   without actual model calls.
7. Verify: backend behavior and integration tests, frontend stream tests, TypeScript
   checking, production build, local runtime smoke. Document limits and live setup.

## MVP choices

- Name: Prompt Caller (working title).
- Speech: browser Web Speech API and speech synthesis; text always available.
- Runtime: local laptop, loopback only. Generated output is an HTML/CSS/JavaScript app
  so results can be shown without executing an arbitrary generated server.
- Claude Code only. No accounts, phone calls, post-build correction loop, deployment,
  multi-project memory, or Codex adapter.
- Live mode requires explicit configuration. Demo mode labels every simulated pass
  and generated demo preview.
- Model thinking controls are opt-in until verified against the Token Factory account.
- The ledger, rather than the model, owns IDs, evidence checks, scores and readiness.

## Data flow

```text
text / speech --> extract --> validate quotes --> SQLite ledger
                         |                            |
                   invalid JSON                  six critics
                         |                            |
                    retry once                    rank product
                         |                            |
                   visible failure       one question / open slots
                                                      |
                                               playback + approve
                                                      |
                                   compile --> verify --> cited CLAUDE.md
                                                      |
                                      opt-in CLI --> isolated local preview
```

Critic failures retain the ledger but close the readiness gate. Edits invalidate
playback approval and compiled output. A failed live model call never switches to demo.
