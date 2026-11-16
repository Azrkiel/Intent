# Intent report: <working title>

Run: <start> → <end> · Result: done | stopped (<stop condition>) · Last passing commit: <sha>

## Built

| Must-have | Check | Result |
| --- | --- | --- |
| <requirement> [L8] | `<command>` | pass |

## Added by Intent

Each was my call, not something you asked for. Remove any of them with the command shown.

| Addition | Serves | Proxy vote | Commit | Remove with |
| --- | --- | --- | --- | --- |
| <feature> | Fails if: "<text>" | 3 yes | <sha> | `git revert <sha>` |

Budget used: <n of N additions, about x% of effort>.

## Decisions I made

Grouped by what settled them (charter, principle, calibration, reversible default,
reversible path around a one-way door). Full entries are in INTENT.md.

- **By principle P2:** D12 sort by date added; D15 ...
- **Reversible default:** D13 ...

## Suggestions not built

| Idea | Why not |
| --- | --- |
| <feature> | proxy vote 2 yes, 1 no: "<reason>" |

## Needs you

- <stop condition or fallback used>: <exact ask, e.g. "set env STRIPE_KEY and rerun step 3">

## Check results

```text
<output of the final run of every acceptance command, from a clean state>
```

Your edits teach the next run: every addition you remove becomes a "no" in calibration,
and every suggestion you want becomes a "yes".
