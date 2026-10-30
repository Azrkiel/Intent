"""Canary review scoring; the application knows the planted ground truth."""

from backend.app.clarity.canary import plant, score
from backend.app.clarity.contracts import Claim, ClaimReview, ReviewFinding, Span, Thresholds


def claims():
    return [
        Claim(
            id=f"C{i}",
            text=f"Requirement {i} holds",
            tags=["journeys/actions"],
            basis="stated",
            status="confirmed",
            spans=[Span(item_id=f"L{i}", quote=f"Requirement {i}")],
        )
        for i in range(1, 9)
    ]


def perfect(mutated, canaries):
    findings = [
        ReviewFinding(claim_id=c.target, kind=c.kind, detail="planted")
        for c in canaries
        if c.kind != "omitted"
    ]
    omitted = [c.target for c in canaries if c.kind == "omitted"]
    return ClaimReview(findings=findings, omitted_ledger_ids=omitted)


def test_planting_is_deterministic_and_hides_canary_ids():
    ledger = [f"L{i}" for i in range(1, 9)]
    first, second = plant(claims(), ledger, "seed"), plant(claims(), ledger, "seed")
    assert [c.model_dump() for c in first[0]] == [c.model_dump() for c in second[0]]
    assert all(c.id.startswith("R") for c in first[0])
    assert {c.kind for c in first[1]} >= {"invented", "negated", "scope-creep", "vague"}


def test_perfect_reviewer_is_trusted():
    mutated, canaries, id_map = plant(claims(), [f"L{i}" for i in range(1, 9)], "seed")
    state = score(perfect(mutated, canaries), canaries, id_map, Thresholds())
    assert state.trusted and state.recall == 1.0 and state.findings == []


def test_missing_one_critical_canary_is_untrusted():
    mutated, canaries, id_map = plant(claims(), [f"L{i}" for i in range(1, 9)], "seed")
    review = perfect(mutated, canaries)
    critical = next(c for c in canaries if c.cost >= 2 and c.kind != "omitted")
    review.findings = [f for f in review.findings if f.claim_id != critical.target]
    assert not score(review, canaries, id_map, Thresholds()).trusted


def test_missing_only_the_vague_canary_can_still_be_trusted():
    mutated, canaries, id_map = plant(claims(), [f"L{i}" for i in range(1, 9)], "seed")
    review = perfect(mutated, canaries)
    vague = next(c for c in canaries if c.kind == "vague")
    review.findings = [f for f in review.findings if f.claim_id != vague.target]
    state = score(review, canaries, id_map, Thresholds())
    assert state.critical_recall == 1.0 and state.recall >= 0.8 and state.trusted


def test_real_findings_map_back_to_real_claim_ids():
    mutated, canaries, id_map = plant(claims(), [f"L{i}" for i in range(1, 9)], "seed")
    targets = {c.target for c in canaries}
    real = next(c.id for c in mutated if c.id not in targets)
    review = perfect(mutated, canaries)
    review.findings.append(ReviewFinding(claim_id=real, kind="other", detail="too vague"))
    state = score(review, canaries, id_map, Thresholds())
    assert [f.claim_id for f in state.findings] == [id_map[real]]


def test_no_canaries_means_no_trust():
    state = score(ClaimReview(), [], {}, Thresholds())
    assert not state.trusted
