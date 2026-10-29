import asyncio
from functools import partial
from typing import Literal
from uuid import uuid4

from pydantic import create_model, model_validator

from ..domain import gate_for
from ..execution.verification import POLICY, TRUSTED_COMMAND
from ..framework import reviewed_context
from ..models import ModelError
from . import prompts
from .allowance import attempt_limit, state_hash
from .contracts import (
    OutlineProposal,
    PhaseProposal,
    PlanApproval,
    PlanAttempt,
    PlanDocument,
    PlanVerification,
    ScreenProposal,
    SourceItem,
)
from .validation import (
    accept_outline,
    accept_phase,
    accept_screen,
    check_citations,
    statement_catalog,
    validate_plan,
)


def checked_schema(schema, *checks):
    """Keep deterministic section failures inside the adapter's existing repair."""
    @model_validator(mode="after")
    def checked(proposal):
        for check in checks:
            check(proposal)
        return proposal

    return create_model(
        f"Checked{schema.__name__}", __base__=schema, __validators__={"checked": checked}
    )


class PlanningService:
    def __init__(self, store, models, settings):
        self.store, self.models, self.settings = store, models, settings

    def attempt_limit(self, session):
        return attempt_limit(session, self.settings.planning_max_attempts)

    def guard(self, session):
        if session.mode != self.settings.mode:
            raise ValueError("This session uses a different mode")
        if not gate_for(session).ready or session.approved_revision != session.revision:
            raise ValueError(
                "Requirements changed or are incomplete. Approve the current requirements before planning."
            )
        if session.build.status == "running":
            raise ValueError("Wait for the current build to finish")

    def document(self, session, attempt, phases=None):
        return PlanDocument(
            id=attempt.plan_id,
            revision=attempt.revision,
            requirements_revision=attempt.requirements_revision,
            mode=session.mode,
            outline=attempt.outline,
            screens=attempt.screens,
            phases=attempt.phases if phases is None else phases,
            sources=[
                SourceItem(**x.model_dump(include={"id", "type", "text", "status", "source", "turn"}))
                for x in session.ledger
            ],
        )

    def accepted_phase(self, session, attempt, index, proposal):
        check_citations(proposal, session.ledger)
        accepted = accept_phase(proposal, attempt.outline, index)
        phases = [*attempt.phases, accepted]
        validate_plan(
            self.document(session, attempt, phases), session.ledger,
            complete=len(phases) == len(attempt.outline.phases),
        )
        return accepted

    def event(self, session, kind, message=None):
        state = session.planning
        attempt = state.attempts[-1] if state.attempts else None
        return {
            "type": kind,
            "message": message,
            "session_id": session.id,
            "requirements_revision": session.revision,
            "attempt_revision": attempt.revision if attempt else None,
            "section_version": (
                int(attempt.outline is not None) + len(attempt.screens) + len(attempt.phases)
                if attempt
                else 0
            ),
            "planning": state.public(),
        }

    async def call(self, session, role, schema, prompt, payload):
        attempt = session.planning.attempts[-1]
        if len(attempt.passes) >= self.settings.planning_max_passes:
            raise ModelError("Planning pass allowance exhausted")
        if role in attempt.passes:
            raise ValueError("Planning pass was already reserved")
        attempt.passes.append(role)
        self.store.save(session)
        try:
            return await self.models.call(session, role, schema, prompt, payload)
        finally:
            self.store.save(session)

    async def generate(self, session):
        self.guard(session)
        state = session.planning
        if state.status in {"review_ready", "approved"} and state.active:
            plan = self.store.get_plan(session.id, state.active.plan_id, state.active.revision)
            validate_plan(plan, session.ledger)
            yield self.event(session, "plan_ready")
            return
        if state.status == "planning":
            raise ValueError("A planning attempt is already running")
        if len(state.attempts) >= self.attempt_limit(session):
            raise ValueError("Planning attempt allowance exhausted for this session")
        expected = state_hash(session)
        attempt = PlanAttempt(
            plan_id=state.attempts[0].plan_id if state.attempts else str(uuid4()),
            revision=len(state.attempts) + 1,
            requirements_revision=session.revision,
        )
        state.attempts.append(attempt)
        if attempt.revision == 3:
            state.extension.status = "consumed"
        elif attempt.revision == 4:
            state.requalification.status = "consumed"
        elif attempt.revision == 5:
            state.fifth_attempt.status = "consumed"
        elif attempt.revision == 6:
            state.sixth_attempt.status = "consumed"
        state.status, state.approval, state.active = "planning", None, None
        self.store.save(session, expected_state_hash=expected)
        finished = False
        context = {
            "ledger": [x.model_dump(mode="json") for x in session.ledger],
            "reviewed_framework": reviewed_context(session),
            "requirements_revision": session.revision,
            "confirmed_ledger_ids": [x.id for x in session.ledger if x.status == "confirmed"],
            "unconfirmed_ledger_ids": [x.id for x in session.ledger if x.status != "confirmed"],
            "constraint_ledger_ids": [
                x.id for x in session.ledger
                if x.status == "confirmed" and x.type in {"constraint", "non-goal"}
            ],
        }

        outline_schema = checked_schema(OutlineProposal, partial(accept_outline, ledger=session.ledger))
        try:
            yield self.event(session, "plan_started")
            outline = await self.call(session, "planner:outline", outline_schema, prompts.OUTLINE, context)
            attempt.outline = accept_outline(outline, session.ledger)
            self.store.save(session)
            yield self.event(session, "plan_section")
            for screen in outline.screens:
                draft = await self.call(
                    session,
                    f"planner:screen:{screen.ref}",
                    checked_schema(
                        create_model(
                            "RequestedScreen", __base__=ScreenProposal, ref=(Literal[screen.ref], ...)
                        ),
                        partial(check_citations, ledger=session.ledger),
                        partial(accept_screen, outline=outline, ref=screen.ref),
                    ),
                    prompts.SCREEN,
                    {**context, "outline": outline.model_dump(), "screen": screen.model_dump()},
                )
                check_citations(draft, session.ledger)
                attempt.screens.append(accept_screen(draft, outline, screen.ref))
                self.store.save(session)
                yield self.event(session, "plan_section")
            for index, phase in enumerate(outline.phases):
                draft = await self.call(
                    session,
                    f"planner:phase:{phase.ref}",
                    checked_schema(
                        create_model("RequestedPhase", __base__=PhaseProposal, ref=(Literal[phase.ref], ...)),
                        partial(self.accepted_phase, session, attempt, index),
                    ),
                    prompts.PHASE,
                    {
                        **context,
                        "outline": outline.model_dump(),
                        "phase": phase.model_dump(),
                        "accepted_phases": [x.model_dump() for x in attempt.phases],
                        "execution_policy": (
                            {
                                "name": POLICY,
                                "allowed_commands": [list(TRUSTED_COMMAND)],
                                "behavioral_tests_supported": False,
                            }
                            if self.settings.allow_codex_execution
                            else None
                        ),
                    },
                )
                accepted = self.accepted_phase(session, attempt, index, draft)
                attempt.phases.append(accepted)
                self.store.save(session)
                yield self.event(session, "plan_section")
            plan = self.document(session, attempt)
            validate_plan(plan, session.ledger)
            catalog = statement_catalog(plan)
            verification = await self.call(
                session,
                "planner:verify",
                PlanVerification,
                prompts.VERIFY,
                {
                    **context,
                    "plan": plan.model_dump(mode="json"),
                    "statements": {key: value.model_dump() for key, value in catalog.items()},
                },
            )
            if (
                set(verification.reviewed_statement_ids) != set(catalog)
                or verification.rejected_statement_ids
                or verification.missing_ledger_ids
            ):
                raise ValueError("Plan semantic verification failed or did not review every statement")
            self.store.save_plan(session.id, plan)
            state.active = PlanApproval(
                plan_id=plan.id,
                revision=plan.revision,
                content_hash=plan.content_hash,
                requirements_revision=session.revision,
            )
            state.status = "review_ready"
            self.store.save(session)
            finished = True
            yield self.event(session, "plan_ready")
        except (ModelError, ValueError) as error:
            state.status = "blocked"
            attempt.error = str(error)[:500]
            self.store.save(session)
            finished = True
            yield self.event(session, "plan_error", attempt.error)
        except (asyncio.CancelledError, GeneratorExit):
            raise
        finally:
            if not finished:
                state.status = "blocked"
                attempt.error = "Planning interrupted. Accepted sections and usage were preserved."
                self.store.save(session)
