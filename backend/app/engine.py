import asyncio

from . import prompts
from .demo import slot_question
from .domain import (
    LENSES,
    AskedQuestion,
    Brief,
    Build,
    Candidate,
    Critique,
    Delta,
    LedgerItem,
    Playback,
    Ranking,
    Session,
    Turn,
    Verification,
    apply_delta,
    gate_for,
    public_session,
    rank_candidates,
    trace_brief,
)
from .models import ModelError
from .store import Store


def context(session: Session) -> dict:
    return {
        "ledger": [item.model_dump() for item in session.ledger],
        "already_asked": [item.model_dump(round_trip=True) for item in session.questions],
        "active_question": session.current_question.model_dump(round_trip=True)
        if session.current_question
        else None,
    }


def stage(message, session=None):
    event = {"type": "stage", "message": message}
    if session:
        event["session"] = public_session(session)
    return event


def missing_slot_question(slot: str, mode: str) -> Candidate:
    question = slot_question(slot)
    if mode == "live" and slot == "core-flow":
        question.options = [
            "Create and edit records",
            "Browse a read-only dashboard",
            "A multi-step approval flow",
        ]
        question.code_diff = (
            "CRUD forms and write routes vs read-only queries vs workflow state and approval routes."
        )
    return question


class Engine:
    def __init__(self, store: Store, models, critic_mode="lenses"):
        self.store, self.models = store, models
        self.critic_mode = critic_mode

    async def call(self, session, role, schema, instruction, payload):
        try:
            return await self.models.call(session, role, schema, instruction, payload)
        finally:
            # Failed validation can still consume tokens; preserve every billed response.
            self.store.save(session)

    async def turn(self, session: Session, text: str, *, scope=None):
        session.revision += 1
        session.approved_revision = None
        for grant in (
            session.planning.extension, session.planning.requalification, session.planning.fifth_attempt
        ):
            if grant and grant.status == "granted":
                grant.status = "invalidated"
        if session.planning.attempts:
            session.planning.status = "stale"
            session.planning.approval = None
        session.playback_revision = None
        session.playback = None
        session.brief = None
        session.build = Build()
        session.analysis_complete = False
        session.warnings = []
        number = len(session.turns) + 1
        session.turns.append(
            Turn(
                number=number,
                text=text,
                question_id=session.current_question.id if session.current_question else None,
                scope=scope,
            )
        )
        if session.title == "Untitled idea":
            session.title = text.strip()[:65]
        self.store.save(session)
        yield stage("Extracting the intent behind your words…", session)
        try:
            await self.extract_latest(session)
            yield stage("Ledger updated. Checking six perspectives…", session)
            async for event in self.analyze(session):
                yield event
        except (ModelError, ValueError) as error:
            session.analysis_complete = False
            session.warnings.append(str(error)[:500])
            self.store.save(session)
            yield {"type": "error", "message": str(error)[:500], "session": public_session(session)}

    async def extract_latest(self, session: Session):
        if session.extracted_revision == session.revision:
            return
        turn = session.turns[-1]
        scope = {}
        if turn.scope:
            from .discussion.store import DiscussionStore

            scope = {
                "scope": turn.scope.model_dump(mode="json"),
                "scope_context": DiscussionStore(self.store).context_for_turn(session.id, turn.number),
            }
        delta = await self.call(
            session,
            "extractor",
            Delta,
            prompts.EXTRACT,
            {**context(session), "text": turn.text, "turn": turn.number, **scope},
        )
        apply_delta(session, delta, turn.number)
        if session.current_question and delta.answers_question == session.current_question.id:
            session.questions.append(
                AskedQuestion(question=session.current_question, answer=turn.text, turn=turn.number)
            )
            session.current_question = None
        session.extracted_revision = session.revision
        self.store.save(session)

    async def analyze(self, session: Session):
        session.analysis_complete = False
        session.warnings = []
        self.store.save(session)
        payload = context(session)

        async def critic(lens):
            try:
                result = await self.call(
                    session,
                    f"critic:{lens}" if lens != "single" else "baseline",
                    Critique,
                    prompts.critic_prompt(lens) if lens != "single" else prompts.BASELINE,
                    payload,
                )
                valid_ids = {item.id for item in session.ledger}
                valid = [
                    q
                    for q in result.candidates
                    if (q.lens == lens or lens == "single") and set(q.targets) <= valid_ids
                ]
                if len(valid) != len(result.candidates):
                    return lens, [], "Critic returned invalid targets or the wrong lens."
                return lens, valid, None
            except ModelError as error:
                return lens, [], str(error)

        candidates, failures = [], []
        tasks = [
            asyncio.create_task(critic(lens))
            for lens in (LENSES if self.critic_mode == "lenses" else ["single"])
        ]
        try:
            for task in asyncio.as_completed(tasks):
                lens, result, error = await task
                candidates.extend(result)
                if error:
                    failures.append(f"{lens}: {error}")
                yield {"type": "lens", "lens": lens, "count": len(result), "failed": bool(error)}
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        for index, question in enumerate(candidates):
            question.id = f"Q{session.revision}-{index + 1}"
        yield stage("Ranking questions by what would change in the build…")
        if candidates:
            try:
                ranking = await self.call(
                    session,
                    "ranker",
                    Ranking,
                    prompts.RANK,
                    {**context(session), "candidates": [q.model_dump(round_trip=True) for q in candidates]},
                )
                scores = {score.id: score for score in ranking.scores}
                for question in candidates:
                    if question.id in scores:
                        score = scores[question.id]
                        question.divergence = score.divergence
                        question.uncertainty = score.uncertainty
                        question.cost_to_change = score.cost_to_change
            except ModelError as error:
                failures.append(f"ranker: {error}")
        ranked = rank_candidates(candidates, session.questions)
        session.rejected_candidates = [q for q in candidates if q not in ranked]
        # Missing required slots remain askable even when all model critics return nothing.
        for slot in gate_for(session).missing:
            if not any(q.slot == slot for q in ranked):
                question = missing_slot_question(slot, session.mode)
                question.id = f"Q{session.revision}-slot-{slot}"
                ranked.append(question)
        session.candidates = rank_candidates(ranked, session.questions)
        session.analysis_complete = not failures
        session.warnings = failures
        if not gate_for(session).ready:
            session.current_question = session.candidates[0] if session.candidates else None
        else:
            session.current_question = None
        if session.questions and len(session.questions) % 4 == 0:
            try:
                await self.playback(session)
            except ModelError as error:
                session.warnings.append(str(error))
        self.store.save(session)
        yield {"type": "done", "session": public_session(session)}

    async def playback(self, session: Session):
        result = await self.call(session, "playback", Playback, prompts.PLAYBACK, context(session))
        session.playback = result
        session.playback_revision = session.revision
        self.store.save(session)

    async def compile(self, session: Session):
        if session.brief:
            return
        # Remaining low-impact gaps must remain visible to the coding agent.
        next_id = max([int(item.id[1:]) for item in session.ledger] or [0]) + 1
        for question in session.candidates:
            text = f"{question.id}: {question.question} Options: {'; '.join(question.options)}"
            if not any(item.type == "open-question" and item.text == text for item in session.ledger):
                session.ledger.append(
                    LedgerItem(
                        id=f"L{next_id}",
                        type="open-question",
                        text=text,
                        status="open",
                        turn=len(session.turns),
                    )
                )
                next_id += 1
        # Ultra is capped to one logical call per session; later revisions use exact ledger text.
        if session.compiler_calls == 0:
            session.compiler_calls += 1
            self.store.save(session)
            draft = await self.call(session, "compiler", Brief, prompts.COMPILE, context(session))
            verification = await self.call(
                session,
                "verifier",
                Verification,
                prompts.VERIFY,
                {**context(session), "lines": [line.model_dump() for line in draft.lines]},
            )
            session.brief = trace_brief(session, draft, verification.rejected_line_indices)
        else:
            session.brief = trace_brief(session, Brief())
            session.warnings.append(
                "Ultra was already used. This revision is compiled verbatim from the ledger."
            )
        self.store.save(session)
