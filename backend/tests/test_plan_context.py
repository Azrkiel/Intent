import copy
import hashlib
import json

import pytest
from pydantic import ValidationError

from backend.app.planning.context import (
    CONTEXT_POLICY,
    SharedContractSnapshot,
    build_context,
    preflight_checks,
    verify_packet,
)
from backend.app.planning.contracts import Interface, PlanApproval, content_hash
from backend.tests.test_plan_validation import plan

BASE = "a" * 40


def test_configured_worker_limits_are_visible_and_bound_to_context_hash():
    session, doc = plan()
    before = doc.content_hash
    default = build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    parallel = build_context(
        doc, session.ledger, "P1-W1", base_commit=BASE, worker_limits={"per_session": 2, "global": 2}
    )
    assert parallel.payload["root"]["orchestration"]["worker_limits"] == {"per_session": 2, "global": 2}
    assert default.context_hash != parallel.context_hash
    assert doc.content_hash == before
    with pytest.raises(ValueError, match="worker|limit|capacity"):
        build_context(
            doc, session.ledger, "P1-W1", base_commit=BASE, worker_limits={"per_session": 2, "global": 1}
        )


def scoped_plan():
    session, doc = plan()
    first = doc.phases[0].packages[0]
    first.tasks[0].steps = ["OWN local step", "Preserve exact argv and quotes"]
    sibling = first.model_copy(deep=True)
    sibling.id, sibling.ref, sibling.owned_paths = "P1-W2", "sibling", ["sibling.py"]
    sibling.tasks[0].id = "P1-W2-T1"
    sibling.tasks[0].steps = ["SIBLING_SENTINEL private implementation"]
    sibling.goal.text = "SIBLING_GOAL private body"
    doc.phases[0].packages.append(sibling)
    doc.phases[1].packages[0].tasks[0].steps = ["COUSIN_SENTINEL private implementation"]
    return session, doc


def identity(doc):
    return PlanApproval(
        plan_id=doc.id,
        revision=doc.revision,
        requirements_revision=doc.requirements_revision,
        content_hash=doc.content_hash,
    )


def dependency_plan(*, same_phase=False):
    session, doc = scoped_plan()
    producer = doc.phases[0].packages[0]
    consumer = doc.phases[0].packages[1] if same_phase else doc.phases[1].packages[0]
    producer.produces = [Interface(name="notes-api", version="v1")]
    producer.artifacts = ["contracts.py"]
    consumer.depends_on = [producer.ref]
    consumer.consumes = [Interface(name="notes-api", version="v1")]
    snapshot = {
        "source_plan": identity(doc).model_dump(),
        "ancestor_id": "P1" if same_phase else "root",
        "producer_id": producer.id,
        "producer_run_id": "synthetic-producer-run",
        "consumer_id": consumer.id,
        "interface_name": "notes-api",
        "interface_version": "v1",
        "integrated_commit": "b" * 40,
        "evidence_hash": "c" * 64,
        "phase_attempt": 1,
        "evidence_state": "integrated" if same_phase else "accepted",
        "artifacts": {"contracts.py": hashlib.sha256(b"published contract only").hexdigest()},
        "documents": {"contracts.py": "published contract only"},
    }
    return session, doc, consumer, snapshot


def test_flat_ancestry_contains_own_subtree_and_exact_sources_without_sibling_bodies():
    session, doc = scoped_plan()
    before = doc.model_dump_json(round_trip=True)
    packet = build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    encoded = json.dumps(packet.model_dump(), ensure_ascii=False)
    assert "OWN local step" in packet.text
    assert "SIBLING_SENTINEL" not in encoded and "COUSIN_SENTINEL" not in encoded
    assert "SIBLING_GOAL" not in encoded
    assert packet.payload["read_order"] == ["root", "P1", "P1-W1"]
    assert "packages" not in packet.payload["phase"]
    assert packet.payload["package"] == doc.phases[0].packages[0].model_dump(mode="json")
    assert packet.payload["root"]["screens"][0]["wireframes"] == doc.screens[0].wireframes
    assert packet.payload["sources"] == [s.model_dump(mode="json") for s in doc.sources]
    assert packet.payload["package"]["tasks"][0]["checks"][0]["command"] == ["python", "-m", "pytest"]
    assert (
        packet.text.index("--- ROOT.json ---")
        < packet.text.index("--- PHASE.json ---")
        < packet.text.index("--- TASK.md ---")
    )
    assert doc.model_dump_json(round_trip=True) == before


def test_context_and_packet_hashes_are_deterministic_and_bind_policy_instructions_and_base():
    session, doc = scoped_plan()
    packet = build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    assert packet == build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    assert packet.context_hash == content_hash(packet.payload)
    assert packet.packet_hash == hashlib.sha256(packet.text.encode("utf-8")).hexdigest()
    assert packet.manifest_hash == content_hash(packet.manifest)
    assert packet.payload["context_policy_version"] == CONTEXT_POLICY
    assert (
        packet.payload["instruction_hash"]
        == hashlib.sha256(packet.documents["AGENTS.md"].encode("utf-8")).hexdigest()
    )
    other = build_context(doc, session.ledger, "P1-W1", base_commit="d" * 40)
    assert packet.context_hash != other.context_hash and packet.packet_hash != other.packet_hash
    later = build_context(doc, session.ledger, "P1-W1", base_commit=BASE, phase_attempt=2)
    assert packet.context_hash != later.context_hash
    verify_packet(packet)


@pytest.mark.parametrize("package_id", ["P1-W1-T1", "unknown", "../P1-W1"])
def test_unknown_or_leaf_assignments_do_not_fall_back_to_full_plan(package_id):
    session, doc = scoped_plan()
    with pytest.raises(ValueError, match="Unknown assigned package"):
        build_context(doc, session.ledger, package_id, base_commit=BASE)


def test_stale_sources_missing_ancestors_and_invalid_base_block_context():
    session, doc = scoped_plan()
    doc.sources[0].source = "changed quote"
    with pytest.raises(ValueError, match="source snapshot"):
        build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    session, doc = scoped_plan()
    doc.phases.pop()
    with pytest.raises(ValueError, match="Incomplete"):
        build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    session, doc = scoped_plan()
    with pytest.raises(ValueError, match="base commit"):
        build_context(doc, session.ledger, "P1-W1", base_commit="HEAD")


def test_packet_byte_limit_counts_unicode_and_never_truncates():
    session, doc = scoped_plan()
    doc.phases[0].packages[0].tasks[0].steps = ["保存 </script> & ignore rules"]
    packet = build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    assert "保存 </script> & ignore rules" in packet.text
    size = len(packet.text.encode("utf-8"))
    assert size > len(packet.text)
    assert build_context(doc, session.ledger, "P1-W1", base_commit=BASE, max_packet_bytes=size) == packet
    with pytest.raises(ValueError, match="packet byte limit"):
        build_context(doc, session.ledger, "P1-W1", base_commit=BASE, max_packet_bytes=size - 1)


def test_cross_branch_dependency_uses_published_ancestor_snapshot_not_producer_packet():
    session, doc, consumer, snapshot = dependency_plan()
    doc.phases[0].packages[0].tasks[0].steps = ["PRODUCER_PRIVATE_BODY"]
    snapshot["source_plan"] = identity(doc).model_dump()
    packet = build_context(doc, session.ledger, consumer.id, base_commit=BASE, snapshots=[snapshot])
    assert "published contract only" in packet.text
    assert "PRODUCER_PRIVATE_BODY" not in packet.text
    assert packet.payload["root"]["shared_contracts"]
    assert packet.payload["phase"]["shared_contracts"] == []
    assert set(packet.documents) >= {"shared/S1/artifact-1.txt"}


def test_same_phase_publication_is_integrated_without_claiming_human_acceptance():
    session, doc, consumer, snapshot = dependency_plan(same_phase=True)
    packet = build_context(doc, session.ledger, consumer.id, base_commit=BASE, snapshots=[snapshot])
    assert packet.payload["root"]["shared_contracts"] == []
    assert packet.payload["phase"]["shared_contracts"][0]["evidence_state"] == "integrated"


@pytest.mark.parametrize(
    "damage",
    ["missing", "source", "ancestor", "consumer", "producer", "version", "hash", "path", "extra", "state"],
)
def test_dependency_publication_must_be_exact_and_complete(damage):
    session, doc, consumer, snapshot = dependency_plan()
    if damage == "missing":
        snapshots = []
    else:
        snapshot = copy.deepcopy(snapshot)
        if damage == "source":
            snapshot["source_plan"]["content_hash"] = "f" * 64
        elif damage == "ancestor":
            snapshot["ancestor_id"] = "P1"
        elif damage == "consumer":
            snapshot["consumer_id"] = "P1-W2"
        elif damage == "producer":
            snapshot["producer_id"] = "P1-W2"
        elif damage == "version":
            snapshot["interface_version"] = "v2"
        elif damage == "hash":
            snapshot["documents"]["contracts.py"] = "tampered"
        elif damage == "path":
            digest = snapshot["artifacts"].pop("contracts.py")
            text = snapshot["documents"].pop("contracts.py")
            snapshot["artifacts"]["../secret"] = digest
            snapshot["documents"]["../secret"] = text
        elif damage == "extra":
            snapshot["private_log"] = "PRODUCER_PRIVATE_BODY"
        else:
            snapshot["evidence_state"] = "integrated"
        snapshots = [snapshot]
    with pytest.raises((ValueError, ValidationError)):
        build_context(doc, session.ledger, consumer.id, base_commit=BASE, snapshots=snapshots)


def test_plain_dependency_requires_explicit_handoff_snapshot_without_inventing_interface():
    session, doc, consumer, snapshot = dependency_plan()
    consumer.consumes = []
    doc.phases[0].packages[0].produces = []
    snapshot["interface_name"] = snapshot["interface_version"] = None
    snapshot["source_plan"] = identity(doc).model_dump()
    with pytest.raises(ValueError, match="publication"):
        build_context(doc, session.ledger, consumer.id, base_commit=BASE)
    packet = build_context(doc, session.ledger, consumer.id, base_commit=BASE, snapshots=[snapshot])
    assert packet.payload["root"]["shared_contracts"][0]["interface_name"] is None


def test_preflight_checks_preserves_exact_qualified_argv_and_rejects_other_commands():
    _, doc = scoped_plan()
    package = doc.phases[0].packages[0]
    with pytest.raises(ValueError, match="Unsupported"):
        preflight_checks(package)
    package.tasks[0].checks[0].command = ["git", "diff", "--check"]
    preflight_checks(package)
    package.tasks[0].checks[0].expected = "TODO placeholder"
    with pytest.raises(ValueError, match="placeholder"):
        preflight_checks(package)


def test_packet_integrity_detects_text_document_manifest_and_payload_tampering():
    session, doc = scoped_plan()
    packet = build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    for name in ["text", "documents", "manifest", "payload"]:
        changed = packet.model_copy(deep=True)
        if name == "text":
            changed.text += "injected"
        elif name == "documents":
            changed.documents["sibling.md"] = "private"
        else:
            getattr(changed, name)["injected"] = True
        with pytest.raises(ValueError, match="integrity"):
            verify_packet(changed)


def test_snapshot_schema_rejects_binary_or_unknown_content():
    _, _, _, snapshot = dependency_plan()
    snapshot["documents"]["contracts.py"] = b"\xff"
    with pytest.raises(ValidationError):
        SharedContractSnapshot.model_validate(snapshot)


def test_duplicate_or_undeclared_artifact_publications_are_rejected():
    session, doc, consumer, snapshot = dependency_plan()
    with pytest.raises(ValueError, match="Duplicate"):
        build_context(doc, session.ledger, consumer.id, base_commit=BASE, snapshots=[snapshot, snapshot])
    snapshot["artifacts"]["private-log.txt"] = hashlib.sha256(b"private log").hexdigest()
    snapshot["documents"]["private-log.txt"] = "private log"
    with pytest.raises(ValueError, match="declared artifact"):
        build_context(doc, session.ledger, consumer.id, base_commit=BASE, snapshots=[snapshot])


def test_snapshot_producing_run_identity_is_required():
    _, _, _, snapshot = dependency_plan()
    snapshot.pop("producer_run_id")
    with pytest.raises(ValidationError):
        SharedContractSnapshot.model_validate(snapshot)


def test_default_byte_budget_blocks_large_valid_context_without_dropping_requirements():
    session, doc = scoped_plan()
    claim = doc.outline.vision.model_copy(update={"text": "x" * 2000})
    doc.outline.journeys = [claim.model_copy(deep=True) for _ in range(10)]
    doc.outline.choices = [claim.model_copy(deep=True) for _ in range(20)]
    doc.outline.common_rules.extend(claim.model_copy(deep=True) for _ in range(39))
    with pytest.raises(ValueError, match="packet byte limit"):
        build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    assert len(doc.outline.specification) == len(session.ledger)


def test_changed_controlled_instructions_cannot_reuse_old_packet(monkeypatch):
    from backend.app.planning import context

    session, doc = scoped_plan()
    packet = build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    monkeypatch.setattr(context, "INSTRUCTIONS", context.INSTRUCTIONS + "\nNew controlled rule.\n")
    with pytest.raises(ValueError, match="integrity"):
        verify_packet(packet)
    revised = build_context(doc, session.ledger, "P1-W1", base_commit=BASE)
    assert packet.context_hash != revised.context_hash
    assert packet.packet_hash != revised.packet_hash
