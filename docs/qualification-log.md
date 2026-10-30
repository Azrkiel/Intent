# Qualification log

Dated verification and live-provider results for Intent, moved from the README.
Entries are historical and record what was true on their date. Current status is in
the [README](../README.md#what-works-today).

## Live smoke status, first attempt

**Qualification status (2026-10-26, America/New_York):** both CLI configurations
were attempted and exited with code 1 (`missing_credentials`). No provider requests
were made: recorded usage is empty, estimated spend is $0, and provider latency and
output validity are unmeasured. The configured Nano/Super model IDs are listed above;
the alternate extractor is `nvidia/Nemotron-3_5-Lightning`. Offline HTTP contract tests
cover controls omitted by default, Nano thinking off when controls are requested,
Super's requested 2048-token budget and Ultra's requested 6144-token budget. They
verify outgoing fields only. Provider acceptance and actual thinking behaviour remain
unverified; `SEND_THINKING_CONTROLS=false` remains the compatibility default.

That entry records the first attempt. Live requests have since succeeded: the
2026-10-30 demo recording captured one production-app clarification turn with eight
Nano and six Super HTTP 200 responses. To extend qualification, complete a live browser
conversation through playback approval, Ultra compilation and Super verification.
Audit every brief line against its cited source, verify all confirmed decisions remain,
and check corrections, failure/retry and session restoration. Save the session export
and `CLAUDE.md` locally under `.data/live-check/`. No full live session or model-quality
pass is claimed.

## Offline qualification

The 2026-10-26 offline follow-up passed 57 backend tests, Ruff, 4 frontend stream
tests, TypeScript checking, the production build and all 16 scripted demo pipeline
runs. A regression test reproduces CRLF delimiters split across network chunks;
the stream parser now normalizes the joined buffer so valid responses are not
reported as interrupted.

```powershell
uv run pytest backend/tests/test_offline_pipeline.py backend/tests/test_builder_process.py -q
```

These tests exercise the real `LiveModels` adapter against simulated HTTP responses,
including failed JSON repair, retained usage, Nano/Super/Ultra routing, compilation,
SQLite restoration and correction invalidation. Their token and cost values are
synthetic. Coding-adapter tests run a local scripted subprocess to check stdout and
stderr handling, successful-result and output-file requirements, timeouts,
cancellation and process cleanup. They do not invoke Claude Code or require keys.

A production-browser demo run covered blank input, the sync/access and automatic
reminder questions, explicit approval, compilation, brief export, a labeled demo
preview, reload restoration and a correction after approval. All nine confirmed
ledger entries appeared in the demo brief. The correction updated existing data
IDs and cleared approval, the compiled brief and the prior build. Demo session
exports and the brief are saved locally under `.data/offline-check/`.

Claude Code 2.1.310 is installed and its authentication status reports signed in.
No paid coding-agent build was run. Actual provider validity, semantic brief
fidelity, live latency/spend, microphone behaviour and authenticated app generation
still need separate checks. Generated apps remain self-contained HTML and do not
run a backend or synchronize across devices.

## Graph and context verification

Graph/context verification (2026-10-28): 334 backend tests passed with one existing
Windows symlink skip and one existing deprecation warning; Ruff, 23 frontend tests,
type checking, production build and all 16 labeled demo evaluations passed. Browser
checks covered complete/blocked fixtures, identity, search, keyboard controls and
mobile/desktop layout. The browser tool blocks `file://` navigation, so opening
the exported viewer from disk with network disabled remains a manual check. No live
provider call was made for this extension; original Phase 5 qualification remains
incomplete. Checkpoints and limits are in the [current handoff](../.Codex/handoffs/2026-10-28-0843.md).

## Phase 1 status

**Phase 1 status (2026-10-27, America/New_York):** offline implementation and demo
browser verification are complete; the user accepted Phase 1 on 2026-10-27. The suite
passes 109 backend tests, Ruff, 9 frontend tests, TypeScript checking, the production
build, and 16/16 existing scripted evaluations. Additional HTTP fixtures exercise
the live model adapter without making provider requests. The browser check covered
both views, approval, export, reload, and correction invalidation.

Demo planning is a generic, labeled synthetic fixture, not a custom model-generated
implementation contract or evidence of semantic quality. Actual Nemotron planning
qualification remains pending. The Phase 1 UI exports plans; the backend API
described below adds worker execution and phase staging. The
[implementation plan](plans/2026-10-26-phase-plans-codex-orchestration.md)
records scheduling in Phase 3 and the review UI in Phase 4. The existing HTML builder remains
available separately.

## Phases 2 to 4 offline evidence

**Phase 2 offline evidence (2026-10-27):** 156 backend tests, Ruff, and 16/16 scripted
evaluations pass. Tests use real local subprocesses and temporary Git repositories,
including Windows descendant cleanup after parent exit, cancellation, stale
permissions, out-of-scope changes, and uncertain dispatch. A saved synthetic
six-scenario run under ignored `.data/phase-two-check/` preserves every worktree.
No real account-backed generation or provider request was made. Actual login,
effective sandbox/policy compatibility, and generation qualification remain Phase 5
work; the earlier account-isolation probe does not establish those results.

**Phase 3 offline evidence (2026-10-27):** 197 backend tests, Ruff and 16/16 demo
evaluations passed. One symbolic-link test was skipped because of Windows
permissions; both Windows junction regressions passed. The existing Starlette/httpx
deprecation warning remains. A separate fake app-server run exercised two
independent workers, a dependent worker starting from its prerequisite's staged
commit, an integration conflict and an out-of-scope failure. Successful phases
stopped for review; conflict/scope cases stayed blocked. Every worktree was retained
and accepted project trees remained unchanged. Reports stay ignored under
`.data/phase-three-check/`. These are offline integration checks with no provider
requests. The user accepted Phase 3 on 2026-10-27.

**Phase 4 offline evidence (2026-10-27):** 217 backend tests passed, with one
Windows symbolic-link skip and the existing Starlette/httpx warning. Ruff,
15 frontend tests, TypeScript checking, the production build and all 16 scripted
demo evaluations passed. Real temporary Git repositories and fake app-server
processes cover stale review identities, rejected evidence, retained repairs,
compare-and-swap promotion, lost promotion replies, restart history inspection,
failed interruption and successor phases pinned to reviewed commits.

Production-browser simulation covered permission decline, active cancellation,
failed trusted checks, rejection/repair, acceptance, explicit next-phase blocking,
correction and reload. A labeled interrupted-dispatch fixture also showed restart
uncertainty with repair and successor dispatch disabled. Desktop and mobile layouts
were inspected. Screenshots and observations remain ignored under
`.data/phase-four-check/`. No provider requests or real account-backed qualification
were performed. Checkpoints: `c93b6cf` (backend gates) and `a87f42d` (execution UI).
The user accepted Phase 4 on 2026-10-27. Phase 5 qualification tooling is now
implemented; actual provider qualification remains incomplete.

## Phase 5 qualification commands and live results

Run these from the repository root. They use only this server's configured key
and Codex profile. They never enable execution, change billing, sign in, approve
requirements or plans, accept phases, or create replacement sessions.

```powershell
uv run python -m backend.smoke --output .data/live-check/basic.json
uv run python -m backend.qualify_planning --output .data/live-check/planning.json
uv run python -m backend.qualify_codex --output .data/live-check/codex.json
```

The commands announce model requests before making them. Without a key, planning
writes `missing_credentials`; without the explicit execution flag, Codex writes
`execution_disabled`. Neither path makes model requests. When execution is enabled,
the Codex command first checks the existing managed ChatGPT account, profile policy,
model inventory and limits without starting a model turn. An incompatible profile
produces `profile_unavailable`; it is never replaced or silently reconfigured.

For an actual planning attempt, first create a live conversation and explicitly
approve its requirements in the app. Stop the app server before using these CLIs:
they access its SQLite store directly and must not run alongside its orchestrator.
Pass that existing session ID; its budget, reserved passes and two-attempt allowance
remain in effect. Use a separate output directory for each session so saved artifacts
from earlier probes cannot be mistaken for the current result.

An explicitly approved, one-time extension may permit a third attempt for the
same approved requirements. The normal settings maximum remains two. Both failed
attempts and all usage remain stored; the extension cannot be renewed. A correction
invalidates an unused extension. The operator command provides a read-only preflight:

```powershell
uv run python -m backend.planning_extension --session-id-file .data/live-check/SESSION_MARKER.txt --output .data/live-check/extension-preflight.json
```

Only after explicit human authorization, stop the app server and issue the grant
using the preflight's `state_hash`, the exact approval saved in an ignored UTF-8
file, the reason, and the verified implementation's full Git commit hash:

```powershell
uv run python -m backend.planning_extension --session-id-file .data/live-check/SESSION_MARKER.txt --output .data/live-check/extension-issued.json --issue --expected-state-hash 'PREFLIGHT_STATE_HASH' --approval-file .data/live-check/extension-approval.txt --reason 'Approved live requalification after a verified fix' --implementation-commit 'FULL_40_CHARACTER_COMMIT_HASH'
```

The command makes no model requests. Changed preflight state or an existing grant
blocks issuance. Generation reserves attempt 3 atomically, consumes the grant even
on interruption, and stops at the existing plan-review gate. It still has at most
nine logical passes, one JSON repair per pass, and the existing dollar budget.
The grant's private audit fields are excluded from public session/detail/events
and operator reports. See the [approved policy amendment](plans/2026-10-28-planning-requalification-proposal.md).

```powershell
uv run python -m backend.qualify_planning --session-id 'YOUR_LIVE_SESSION_ID' --output .data/live-check/probe-1/planning.json
```

This writes `planning-human.md` and `planning-engineering.md` beside the report.
The plan stops at review. Restart the app, inspect both views and approve the exact
plan revision. Stop the server and rerun the same command to export
`planning-bundle.zip` without repeating model calls. Product content is confined to
these local artifacts and the session store; it is excluded from the redacted report.

For execution, use an approved live plan compatible with `git-inspection-only-v1`.
After configuring execution explicitly and stopping the server, select a phase:

```powershell
uv run python -m backend.qualify_codex --session-id 'YOUR_LIVE_SESSION_ID' --phase-id P1 --output .data/live-check/probe-1/codex.json
```

It dispatches that phase once through the existing executor, or inspects its saved
outcome if already attempted. It never automatically repairs, resumes, accepts or
redispatches an existing phase. Pending permission requests are not granted by this
CLI and can time out; use the app's normal execution flow for interactive permission
review. Restart the app to inspect evidence and accept the exact review before
explicitly starting a successor. For the live audit, use a first phase with one
package, then a successor with two independent packages. Two workers require the
existing explicit concurrency configuration and a qualified compatible profile.

Reports retain per-response planning tokens, estimated dollars and latency, including
failed planning attempts, plus observed Codex tokens separately. String fields are
allowlisted; unknown model names are redacted. Reports exclude credentials, auth
payloads, transcript bodies, account identifiers, paths and exception text. Requested
thinking controls are recorded; provider-side behavior and multiple-account inference
remain `unverified`. CLI exit 0 means its automated checks passed, not Phase 5
acceptance. The report always keeps overall `passed` false; record the manual audit
and Phase 5 acceptance separately. Missing prerequisites and failed automated checks
exit 1.

**Observed results (2026-10-27, America/New_York):** the separate basic smoke and
planning commands exited 1 with `missing_credentials`; the Codex command exited 1
with `execution_disabled`. All three made zero model requests, recorded no usage
and incurred no model spend. The managed account and effective sandbox were not
probed because execution was disabled. Reports remain ignored under
`.data/live-check/`. Offline qualifier tests cover missing prerequisites, retained
failure usage, redaction, approval gates, cleanup failures, actual Git verification
through a fake app-server, and inspection without duplicate dispatch.

Fresh verification at checkpoint `e4e5973`: 229 backend tests passed (12 qualifier
tests), one Windows symbolic-link test skipped, and the existing Starlette/httpx
warning remained. Ruff, 15 frontend tests, TypeScript checking, the production build
and 16/16 scripted demo evaluations passed. A separate loopback server started,
returned healthy demo configuration and an empty session list from a dedicated
database, and shut down cleanly. These checks made no model requests.

Live planning fidelity, exported packet audit, real Codex generation, cancellation,
reload/restart reconciliation, acceptance and correction remain pending. No live
model-quality result or Phase 5 acceptance is claimed.

**Live follow-up (2026-10-28, America/New_York):** the configured Token Factory
key authenticated and the model inventory included the configured Nano, Super and
Ultra IDs. The initial SDK connection failed certificate verification. A local PEM
bundle exported from the machine's existing OS trust roots resolved that connection
failure with TLS verification enabled. The bundle is ignored local configuration,
not a portable project dependency. Test processes used:

```powershell
$env:SSL_CERT_FILE = (Resolve-Path '.data/live-check/2026-10-28/system-trust.pem').Path
uv run python -m backend.smoke --output .data/live-check/2026-10-28/basic-after-prompt.json
```

The basic live Nano/Lightning extraction and Super contradiction smoke passed
before and after the prompt changes. Optional thinking-control probes had mixed
schema/grounding results: one failed on Lightning, a later probe failed on Nano,
and a focused Lightning recheck passed. These requests returned model responses,
but do not establish reliable control behavior. `SEND_THINKING_CONTROLS=false`
remains the application default.

A real three-turn counter clarification session exposed missing source retention,
repeated questions, inflated change-cost scores, and inaccurate playback wording.
`fc573aa` supplies the ledger and answer history to the existing ranking pass and
clarifies extraction, scoring, exclusion and playback instructions. After explicit
diagnostic re-extraction and reanalysis in the same retained session, all six slots
were filled with exact source quotes, no high-impact blockers remained, and the
corrected playback matched the access and recovery decisions. This is one observed
integration case, not a measured quality or reliability result. Grouped extraction
and semantic fidelity still need manual review. That initial clarification checkpoint
retained 54 model responses and an estimated $0.09068 in usage. The subsequent
requirements approval and planning results are recorded below.

With the user's explicit execution opt-in, the original Codex profile was rejected
for inherited tools. A separate local test profile was prepared and the user signed
in with ChatGPT through the CLI. Its browser/app/plugin features and skills were
disabled within that profile. It qualified with CLI 0.164.0, model `gpt-6.1-sol`, no
runtime MCP servers and no enabled skills. Credentials were not copied. No Codex
model turn has started; effective live sandbox behavior, generation and lifecycle
qualification remain pending. Reports stay under `.data/live-check/2026-10-28/`;
authentication state stays in the ignored test profile.

An initial regression run exposed that tests inherited the developer's live `.env`.
`eba9e0e` makes test defaults independent of that file and exported app settings,
uses an isolated test database and blocks unmocked synchronous/asynchronous HTTP
transports. The normal `uv run pytest -q` then passed **234 tests**, with one Windows
symlink skip and the existing dependency warning. Ruff, 15 frontend tests, type
checking, the production build and 16/16 demo evaluations also passed. The five new
cases cover test isolation, network blocking, mocked providers and ranking context
with failure closure. These code checkpoints are local on
`codex/phase-five-live-qualification`.

**After requirements approval (2026-10-28):** the user approved revision 3 through
chat and the approval was recorded through the production API. Ultra compiled the
brief on its first logical call and Super returned no rejected or missing brief
items. Manual review of this artifact retained the core actions, access policy,
storage behavior and exclusions; small unresolved choices stayed labeled. These
two responses cost an estimated $0.01196. The resulting local artifact is
`.data/live-check/2026-10-28/counter-brief-artifact.md`.

Live planning **did not pass**. Attempt 1 used its JSON repair, then failed confirmed
specification coverage. Application-owned confirmed/unconfirmed ID checklists and
explicit statement-status instructions were added. Attempt 2 returned schema-valid
JSON covering all seven confirmed IDs, but the application rejected its non-ASCII
architecture diagram. No outline, screen or phase was accepted. Both session
attempts were consumed at that checkpoint; no allowance was reset and no replacement
session or additional live planning request had been made.

The diagram failure exposed a schema gap: ASCII was checked only after provider
schema validation, so the existing JSON-repair path could not handle it. Checkpoint
`a0af23f` declares the ASCII pattern in the provider schema while retaining
application validation. Offline regressions verify repair of a Unicode diagram,
failure after two invalid responses, Unicode prose support, coverage checklists
and rejection of proposal-only coverage. At that checkpoint the contract fix had
not been requalified live in the exhausted session. Fresh verification passed 242 backend
tests (one Windows symbolic-link skip and the existing dependency warning) and
Ruff. No frontend files changed during this follow-up.

The compile/planning follow-up used five responses costing an estimated $0.02111;
the retained counter session totals an estimated $0.11179. Reports and redacted
field/error diagnostics are in `.data/live-check/2026-10-28/planning-attempt-1/`,
`planning-attempt-2/` and `approved-requirements-test-summary.json`. No valid plan,
plan approval, bundle audit or Codex model turn followed these failures. Phase 5
and real generated-app qualification remain incomplete.

**Approved one-attempt extension (2026-10-28):** after explicit human approval,
`ec14afd` implements one recorded, non-renewable session extension while keeping
the ordinary settings maximum at two. Prior attempts and usage remain intact;
issuance and attempt reservation use atomic snapshot checks. Correction invalidates
an unused extension, and private audit fields are excluded from public responses.
`3c86154` separates transport test startup from short fault-probe deadlines and
closes failed fixture setup; production transport deadlines are unchanged.

Final fresh checks passed: **276 backend tests**, one existing Windows symlink
skip and the existing dependency warning; Ruff, 15 frontend tests, type checking,
production build, and 16/16 labeled demo evaluations. A built-app loopback/proxy
smoke passed streamed demo planning, both views, and the approval gate. The basic
live smoke initially returned generic Nano `model_error`; an instrumented repeat
passed Nano, Lightning and Super without a runtime/prompt change. The optional
thinking-controls smoke passed too, but the default stays off and prior failures
remain evidence. The isolated Codex profile requalified without inference.

The single authorized third planning attempt **failed**. Its outline covered all
seven confirmed IDs and passed ASCII checks, and one screen was accepted. After
one JSON repair, the first phase returned `ui-setup-phase` where the accepted
outline required `ui-setup`; the application correctly rejected that identity.
The unaccepted candidate also contained shell-style checks and a placeholder
verification command incompatible with the trusted runner; none was executed.
Four Super responses cost an estimated **$0.01263540**, bringing the retained
session estimate to **$0.12442798** across 63 usage records.

The extension is consumed and all three attempts remain stored. Postflight
confirmed exhaustion blocks before provider dispatch. No complete immutable plan,
plan approval, bundle, or Codex model turn exists. The outline and screen are
partial accepted sections, not a qualified plan. Evidence is ignored under
`.data/live-check/2026-10-28/extension-attempt-3/`. At that checkpoint, no fourth
attempt, reset, or replacement session was used. Offline checks passed; live planning and
Phase 5 remain failed/incomplete.

**Offline request-contract follow-up (2026-10-28):** screen and phase requests now
require their exact accepted outline reference in the provider validation schema,
so reference drift can use the existing single JSON repair. With Codex execution
enabled, phase requests also receive the trusted runner's actual command policy;
whitespace inspection is not behavioral verification. Existing preflight and
approval gates remain in place. These changes have offline regression coverage,
not a fresh live pass. The [further qualification proposal](plans/2026-10-28-fourth-attempt-requalification-proposal.md)
was subsequently approved, implemented, and consumed as recorded below.

**Fourth-attempt qualification (2026-10-28):** `af20dea` adds one separately
audited grant while preserving the consumed original extension. Atomic preflight,
issuance/reservation, historical hashes, private audit fields, correction/restart
handling, and refusal of attempt 5 have 37 new regressions. Fresh checks passed
377 backend tests, one existing skip/warning, Ruff, and all 16 labeled demo cases.

The one approved fourth attempt **failed at the outline**: its repaired response
violated the ASCII diagram schema at `architecture`. Two Super responses cost an
estimated $0.00818940, bringing retained usage to 65 responses and $0.13261738.
Both grants are consumed. Prior attempts/usage, approved requirements revision 3,
and the compiled brief are unchanged; no active plan, plan approval, or Codex turn
exists. Attempt 5 is blocked before provider dispatch. There is no automatic retry;
live planning and Phase 5 remain failed/incomplete. Evidence stays ignored under
`.data/live-check/2026-10-28/requalification-attempt-4/`.

**Offline response-boundary fixes (2026-10-28):** new provider responses now render
a finite set of common arrow/box glyphs as ASCII in diagram fields only, then apply
the original validation. Unknown characters and oversized diagrams still fail.
Source quotes, identifiers, commands and stored plans are unchanged. Repair now
addresses schema values as well as JSON structure. Planning output marked as
length-limited receives the existing single compacting repair and cannot silently
be accepted as complete. Budgets, token limits and attempt allowances are unchanged.
Integrated simulated-HTTP tests cover planning through graph/views, runner preflight,
preserved source/hash identity and gated export. These checks are not a new live pass;
the retained session remains exhausted. See the [current handoff](../.Codex/handoffs/2026-10-28-0843.md).

Checkpoint `23acab5` passed 387 backend tests with one existing skip and warning,
Ruff, 23 frontend tests, type checking, production build, and all 16 labeled demo
evaluations. No new provider request was made and the retained live state is unchanged.

**Interactive graph update (2026-10-29):** the ASCII conversion described above is
superseded by bounded Unicode descriptions; the adapter preserves Unicode unchanged.
Graph sections now support cited questions, exact scoped direction, saved history,
per-section drafts and optional dictation. These changes do not authorize a fifth
planning attempt or establish live model quality. The retained live session still
has four consumed attempts and no approved plan. See the
[latest handoff](../.Codex/handoffs/2026-10-29-0035.md) for final checks and publication.
Offline verification passed 415 backend tests (one existing skip and warning), Ruff,
31 frontend tests, type checking, production build and all 16 scripted demo runs.
Isolated demo browser checks covered desktop/mobile, scoped questions and direction,
draft restoration, stale gating, keyboard selection and Unicode. Speech lifecycle
was tested with simulated recognition; real microphone and live explanations remain
unverified. The retained live session's stored bytes and usage counts are unchanged.

**Fifth-attempt authorization (2026-10-29):** the human subsequently authorized one
fifth attempt to qualify the merged Unicode fixes. A separate `fifth_attempt` grant
binds the retained session, approved revision, all four prior attempt hashes and
the consumed fourth-attempt grant. Neither earlier grant is reset. The existing
local operator command accepts `--fifth-attempt` for preflight and issuance; issuance
still requires a stopped server, fresh state hash, exact approval file, reason and
verified implementation commit. The grant is consumed atomically before dispatch;
failure, interruption, restart or correction never replenishes it. The ordinary
two-attempt policy, nine-pass cap, one repair per pass and session budget remain.
No sixth attempt is provided. See the [bounded execution plan](plans/2026-10-29-fifth-planning-attempt.md).

The sole fifth attempt **failed outline coverage** after one schema-valid Super
response: `common_rules` omitted L4, "No login, network, backend, or sync", although
the specification covered all seven confirmed IDs. Unicode was accepted. The call
used 2,531 input and 2,416 output tokens, costing an estimated $0.00293370; cumulative
usage is 66 responses and $0.13555108. The fifth grant is consumed. No active plan,
plan approval or coding-agent dispatch exists; attempt 6 is refused before provider
or save. Prior attempts, grants, usage, requirements revision 3, playback approval
and compiled brief were preserved. Private evidence is under
`.data/live-check/2026-10-29/attempt-5/`.

Manual inspection also found unsupported first-launch behavior: the architecture
would treat an absent saved value as a storage failure and disable both buttons.
It also promoted a non-negative-integer restriction and per-tab storage keys to
confirmed rules without explicit support. These observations are fidelity failures,
not reasons to bypass coverage validation or accept the outline.

The failure exposed a repair boundary: deterministic outline checks previously ran
after the adapter had accepted the response, so a coverage failure received no
repair. The follow-up binds the existing outline validator to the response schema
and supplies an explicit constraint-ID checklist. JSON, schema and deterministic
outline failures now share the existing single repair; two failed responses still
close the gate. This is an offline correction, not a sixth live attempt or evidence
that the model's fidelity issues are resolved. No allowance or prior failure was reset.
Checkpoint `8f51a9a` contains the audited fifth-attempt grant; `219b1eb` contains the
repair correction. Fresh verification after the correction passed 459 backend tests
(one existing Windows symlink skip and deprecation warning), Ruff and all 16 scripted
demo evaluations with zero provider calls. These checkpoints were subsequently
included in PR #4, linked below.

**Sixth-attempt qualification (2026-10-29):** the human authorized one sixth
attempt with the outline repair fix. Checkpoint `b1ab901` adds a separate audited
`sixth_attempt` grant and local `--sixth-attempt` operator mode, preserving the
ordinary two-attempt policy and every earlier grant. Its 33 new tests passed;
fresh full verification passed 492 backend tests (one existing skip and warning),
Ruff and all 16 scripted demos.

The sole sixth attempt accepted the outline and one screen, then **failed at the
first phase** with `Package misses scope exclusions`: both returned packages had
empty exclusions, missing L4 (no login, network, backend or sync). The phase had
already used its one JSON/schema repair, so no third response was permitted.
Three logical passes used four Super responses, costing an estimated $0.01181010.
Cumulative usage is 70 responses and $0.14736118. All prior evidence, approved
requirements/playback revision 3 and the compiled brief remain intact. All four
grants are consumed; attempt 7 is refused before provider/save. No complete plan,
plan approval or coding-agent dispatch exists.

The offline follow-up applies the existing deterministic checks to screen and phase
responses inside the same single repair limit, including full coverage at the last
phase. The phase prompt explicitly requires all constraint IDs in every package's
exclusions. Post-call guards and the final semantic reviewer remain; no validation
is weakened, no extra response is added, and the failed sixth attempt is preserved.
This change has no new live qualification evidence. See the
[sixth-attempt record](plans/2026-10-29-sixth-planning-attempt.md); private
diagnostics remain ignored under `.data/live-check/2026-10-29/attempt-6/`.
Repair checkpoint `dfc707a` passed 512 backend tests (one existing Windows symlink
skip and deprecation warning), Ruff and all 16 scripted demos with zero provider
calls. The live sixth-attempt state is unchanged by the correction. These
checkpoints were subsequently published in
[PR #4](https://github.com/Azrkiel/Intent/pull/4), "Add audited planning retries and
bounded section repair", after the human authorized publication and merge. The PR
records the final merge state. A fresh pre-publication run passed 97 grant/repair
tests and Ruff; the fetched base matched the verified base. No seventh attempt or
coding-agent dispatch occurred at that checkpoint.

**Seventh-attempt retest (2026-10-29):** after the user authorized a bounded
retest, `86bbe93` added one separately audited seventh grant bound to the six
retained failures and consumed sixth grant. The normal two-attempt policy,
nine-pass cap, shared single JSON repair and cumulative $2 session budget are
unchanged. A fresh full run passed 571 backend tests, with one existing skip and
deprecation warning; 52 focused grant/section-repair checks, Ruff and all 16 demo
cases passed without provider calls.

The one live invocation accepted its outline, then received **HTTP 529** from the
screen request: the provider reported `worker overloaded`. No screen or phase was
accepted and no complete plan was produced. The phase-validation repair remains
unqualified against a live phase response. One successful response recorded 2,576
input and 2,350 output tokens, estimated $0.0028878; cumulative recorded spend is
$0.15024898 across 71 successful responses. The failed HTTP response is retained
separately. All six earlier attempts, four previous grants, 70 earlier usage
records, approved requirements/playback revision 3 and compiled brief are intact.

The seventh grant is consumed and attempt 8 is refused before provider or save.
The configured Codex profile passed a read-only check; no Codex inference or phase
dispatch occurred. The local demo was restored with its existing database and
sessions. The [retest record](plans/2026-10-29-live-planning-retest.md) contains
the measured outcome; private evidence remains ignored under
`.data/live-check/2026-10-29/attempt-7/`. No additional live retry is authorized by
this record.

**Eighth-attempt qualification (2026-10-29):** the user authorized one eighth
attempt after a handoff and full review of attempts 1 to 7. The
[retrospective](retrospectives/2026-10-29-seven-planning-attempts.md) and
[eighth-attempt record](plans/2026-10-29-eighth-planning-attempt.md) explain the
causes, mitigations and measured outcome. Checkpoint `5270b9c` adds an audited
eighth grant, at most two explicit overload retries shared across that attempt,
and checked runner/review-coverage acceptance. Ordinary sessions retain two
attempts; SDK retries stay disabled. Verification passed 640 backend tests (one
existing skip and warning), 95 focused checks, seven offline rehearsals, Ruff and
all 16 demo cases.

The sole live run accepted its outline and screen, then **failed at phase repair**.
The initial JSON had empty required inputs/preconditions. Its repair fixed those
fields but duplicated a three-task block, exceeding the three-task maximum. All
four responses were HTTP 200 with finish reason `stop`; there was no overload or
truncation. Offline replay reproduced the failure using only captured responses.
No phase, complete plan, plan approval or worker dispatch exists. Estimated new
cost was $0.01464840; cumulative recorded spend is $0.16489738 over 75 responses.
All previous history and approved sources are intact. The eighth grant is
consumed and a ninth is refused before provider/save. The demo was restored with
the same three sessions. No further live inference is authorized by this record.

**Offline repair follow-up (2026-10-29):** the approved
[design](specs/2026-10-29-constrained-planning-repair.md) and
[implementation record](plans/2026-10-29-constrained-planning-repair.md)
replace whole-object repair for complete planning proposals with typed values
bound to application-owned invalid field paths. Valid sibling content is preserved;
the reconstructed proposal still passes the full original checks. Unmapped or
ambiguous errors stop. Malformed or output-limited originals retain one complete
retry, and no pass gets a third response.

Semantic review now explicitly covers architecture, flows, wireframes, task steps,
inputs/readiness and other plan prose. Uncited text receives no invented citations
or confirmed status. The review limit remains 500 entries; genuine rejection
blocks readiness. Captured-response rehearsals exercise preservation and scripted
rejection offline. They do not qualify live model judgment or create a complete
live plan. No new grant, live invocation, approval or dispatch is included.
