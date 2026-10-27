"""Synthetic planning examples, not model-quality or implementation evidence."""


def demo_response(session, role, payload):
    ledger = session.ledger
    confirmed = [x for x in ledger if x.status == "confirmed"]
    ids = [x.id for x in confirmed]

    def statement(text, references=None, status="proposal"):
        return {"text": text, "ledger_ids": references or ids[:1], "status": status}

    decisions = [statement(x.text, [x.id], "confirmed") for x in confirmed]
    exclusions = [
        statement(x.text, [x.id], "confirmed") for x in confirmed if x.type in {"constraint", "non-goal"}
    ]

    if role == "planner:outline":
        return {
            "vision": statement("Synthetic implementation outline for the approved idea"),
            "journeys": [statement("Follow the approved core flow, then verify the saved result")],
            "specification": decisions,
            "common_rules": exclusions,
            "choices": [
                statement("Python API and a browser UI are fixture proposals, not confirmed choices"),
                statement(
                    "Choose a runtime and persistence design before real execution", status="unresolved"
                ),
            ]
            + [statement(x.text, [x.id], "unresolved") for x in ledger if x.status != "confirmed"],
            "architecture": "[Browser UI] -> [API contract] -> [Persistence adapter]\n"
            "[Invalid input / save failure] -> [Visible error and retry]",
            "screens": [
                {"ref": "main", "title": "Main workflow", "states": ["empty", "loading", "error", "success"]}
            ],
            "phases": [
                {"ref": "foundation", "title": "Shared contracts", "depends_on": []},
                {"ref": "implementation", "title": "Implement the workflow", "depends_on": ["foundation"]},
            ],
        }
    if role.startswith("planner:screen:"):
        return {
            "ref": "main",
            "purpose": statement("Proposed screen for the approved core workflow"),
            "wireframes": {
                state: f"+----------------------+\n| Main workflow        |\n"
                f"| {state:<20} |\n+----------------------+"
                for state in ("empty", "loading", "error", "success")
            },
        }
    if role.startswith("planner:phase:"):
        ref = payload["phase"]["ref"]

        def package(name, path, deps, produces=None, consumes=None):
            return {
                "ref": name,
                "goal": statement(f"Implement the proposed {name} package"),
                "depends_on": deps,
                "owned_paths": [path],
                "produces": produces or [],
                "consumes": consumes or [],
                "preconditions": ["Current plan approved", "Dependency outputs integrated"],
                "inputs": ["Cited specification and common constraints"],
                "outputs": [path, "Verification evidence"],
                "flow": "[Validate input] -> [Perform action] -> [Show result]\n"
                "[Invalid input / action failure] -> [Show error; preserve data]",
                "tasks": [
                    {
                        "title": f"Implement and verify {name}",
                        "steps": [
                            "Write failing checks for the cited acceptance criteria",
                            "Implement within owned paths and the agreed interface",
                            "Run checks and report actual artifacts and remaining decisions",
                        ],
                        "acceptance": decisions,
                        "checks": [
                            {
                                "command": ["python", "-m", "pytest"],
                                "expected": "Acceptance checks pass; failure-path checks pass",
                            }
                        ],
                    }
                ],
                "acceptance": decisions,
                "exclusions": exclusions,
                "choices": [statement("Verification commands are fixture suggestions and require review")],
                "artifacts": [path, "Changed paths and check results"],
            }

        interface = [{"name": "workflow", "version": "v1"}]
        packages = (
            [package("contracts", "contracts", [], produces=interface)]
            if ref == "foundation"
            else [
                package("ui", "ui", ["contracts"], consumes=interface),
                package("api", "api", ["contracts"], consumes=interface),
            ]
        )
        return {
            "ref": ref,
            "goal": statement(f"Complete the proposed {ref} phase"),
            "flow": "[Implement packages] -> [Integrate and test] -> [User review]\n"
            "[Failed checks] -> [Repair current phase; preserve changes]",
            "packages": packages,
        }
    if role == "planner:verify":
        return {
            "reviewed_statement_ids": list(payload["statements"]),
            "rejected_statement_ids": [],
            "missing_ledger_ids": [],
        }
    raise ValueError("Unknown synthetic planning role")
