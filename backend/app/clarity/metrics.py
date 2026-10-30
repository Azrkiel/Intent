"""Clarity eval metrics. Scripted runs measure plumbing, not model quality."""

from .decisions import wasted_questions


def clarity_metrics(session) -> dict | None:
    if session.clarity_version != 2 or session.clarity is None:
        return None
    state = session.clarity
    wasted, asked = wasted_questions(session)
    return {
        "fields_passed": sum(f.passed for f in state.fields),
        "alpha": {f.field: f.alpha for f in state.fields if f.alpha is not None},
        "failing": {f.field: f.failing for f in state.fields if f.failing},
        "claims": len(state.claims),
        "problems": len(state.problems),
        "decisions": {
            status: sum(d.status == status for d in state.decisions)
            for status in ("open", "decided", "delegated", "deferred", "excluded")
        },
        "review_recall": state.review.recall if state.review else None,
        "review_critical_recall": state.review.critical_recall if state.review else None,
        "review_trusted": state.review.trusted if state.review else None,
        "wasted_questions": [wasted, asked],
    }
