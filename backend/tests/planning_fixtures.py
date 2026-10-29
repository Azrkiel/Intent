import json

from backend.app.domain import LedgerItem, Session, Turn


def repair_response(request, valid_response):
    """Synthetic provider obeys application-owned scopes; no production fallback."""
    try:
        repair = json.loads(request["messages"][-1]["content"])
    except (ValueError, TypeError):
        return valid_response
    if not isinstance(repair, dict) or repair.get("mode") != "field_repair":
        return valid_response
    result = {}
    for key, field in repair["repair_fields"].items():
        value = valid_response
        for token in field["path"]:
            value = value[token]
        result[key] = value
    return result


def statement(text="Save notes", ids=None, status="proposal"):
    return {"text": text, "ledger_ids": ids or ["L1"], "status": status}


def ready_session():
    from backend.app.domain import SLOTS

    session = Session(mode="demo", revision=1, approved_revision=1, analysis_complete=True)
    session.turns = [Turn(number=1, text="Save notes. No payments.")]
    session.ledger = [
        LedgerItem(
            id=f"L{i + 1}",
            type="non-goal" if slot == "non-goals" else "feature",
            text="No payments" if slot == "non-goals" else f"Save notes ({slot})",
            status="confirmed",
            source="No payments" if slot == "non-goals" else "Save notes",
            slot=slot,
            turn=1,
        )
        for i, slot in enumerate(SLOTS)
    ]
    return session


def outline(session=None):
    session = session or ready_session()
    return {
        "vision": statement(),
        "journeys": [statement()],
        "specification": [statement(x.text, [x.id], "confirmed") for x in session.ledger],
        "common_rules": [
            statement(x.text, [x.id], x.status)
            for x in session.ledger
            if x.type in {"constraint", "non-goal"}
        ],
        "choices": [statement("Use Python for the proposed implementation")],
        "architecture": "[Input] -> [Save] -> [Read]\n[Save failure] -> [Retry]",
        "screens": [{"ref": "notes", "title": "Notes", "states": ["empty", "loading", "error", "success"]}],
        "phases": [
            {"ref": "core", "title": "Shared contracts", "depends_on": []},
            {"ref": "app", "title": "Application", "depends_on": ["core"]},
        ],
    }


def package(ref="contracts", path="contracts.py", deps=None, session=None):
    session = session or ready_session()
    return {
        "ref": ref,
        "goal": statement(),
        "depends_on": deps or [],
        "owned_paths": [path],
        "produces": [],
        "consumes": [],
        "preconditions": ["Approved requirements"],
        "inputs": ["Cited intent ledger"],
        "outputs": [path],
        "flow": "[Input] -> [Validate] -> [Save]\n[Invalid] -> [Error]",
        "tasks": [
            {
                "title": "Implement and verify",
                "steps": ["Write a regression test", "Implement the change"],
                "acceptance": [statement()],
                "checks": [{"command": ["python", "-m", "pytest"], "expected": "All checks pass"}],
            }
        ],
        "acceptance": [statement(x.text, [x.id], "confirmed") for x in session.ledger],
        "exclusions": [
            statement(x.text, [x.id], "confirmed")
            for x in session.ledger
            if x.type in {"constraint", "non-goal"}
        ],
        "choices": [],
        "artifacts": [path, "Test evidence"],
    }


def phase(ref="core", packages=None):
    return {
        "ref": ref,
        "goal": statement(),
        "flow": "[Implement] -> [Test]\n[Fail] -> [Repair]",
        "packages": packages or [package()],
    }


def screen():
    return {
        "ref": "notes",
        "purpose": statement(),
        "wireframes": {s: f"+ Notes +\n| {s} |\n+-------+" for s in ("empty", "loading", "error", "success")},
    }
