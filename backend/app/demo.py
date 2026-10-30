"""Deterministic, labeled fixture provider. Never used as fallback for live requests."""

import re

from .domain import (
    Brief,
    BriefLine,
    Candidate,
    Critique,
    Delta,
    Playback,
    Ranking,
    Session,
    Verification,
    gate_for,
)

SYNC_QUESTION = "Without login, how should your habits find you on another device?"
AUTO_QUESTION = "When you say automatic, what should reminders do?"


def make_question(lens, question, options, code_diff, slot=None, targets=None, score=3):
    return Candidate(
        lens=lens,
        question=question,
        options=options,
        code_diff=code_diff,
        targets=targets or [],
        divergence=3,
        uncertainty=score,
        cost_to_change=3,
        slot=slot,
    )


# v2 sessions ask North Star and decision questions; their answers fill the gate's slots,
# so the v1 slot questions only remain as a fallback for whatever is still missing.
NORTH_STAR_SLOTS = {
    "who-when": ("user", "access"),
    "good": ("success-criterion", "success-criterion"),
}
DECISION_SLOTS = {"data-model": ("data", "data")}


def v2_answer_slot(question, text):
    """The ledger type and slot a scripted v2 answer fills, or None."""
    if question.lens == "north-star":
        return next(
            (slot for name, slot in NORTH_STAR_SLOTS.items() if question.id.startswith(f"NS-{name}-")), None
        )
    if question.lens == "decision":
        category = question.id.split(":")[1] if question.id.startswith("D:") else ""
        if category == "identity" and text.strip() == question.options[0].strip():
            return "non-goal", "non-goals"
        return DECISION_SLOTS.get(category)
    return None


def slot_question(slot: str) -> Candidate:
    questions = {
        "goal": (
            "done-ness",
            "What is the main thing you want to build?",
            ["A personal habit tracker", "A shared task board", "A simple notes app"],
            "Habit/day tables vs board/task tables vs note documents and editor routes.",
        ),
        "core-flow": (
            "behaviour",
            "What should the first version let you do?",
            [
                "Create habits and check them off daily",
                "Record a daily journal entry",
                "View a read-only summary",
            ],
            "Habit creation and completion controls vs a text editor vs a read-only dashboard.",
        ),
        "data": (
            "data",
            "Where should the first version save your data?",
            ["In this browser only", "Sync across devices", "Do not save anything yet"],
            "localStorage adapter vs server persistence and sync routes vs in-memory state.",
        ),
        "access": (
            "identity",
            "Who can access the first version?",
            ["Only me, without an account", "Anyone with a private share link", "People who sign in"],
            "Browser-local state vs capability-token routes vs an auth provider and users table.",
        ),
        "non-goals": (
            "edges",
            "What should we keep out of the first version?",
            ["No accounts or payments", "No sharing or social features", "No notifications or integrations"],
            "Excludes auth and billing tables vs collaboration routes "
            "vs notification workers and API clients.",
        ),
        "success-criterion": (
            "done-ness",
            "What would you check first to call it working?",
            [
                "Save an entry, reload, and see it again",
                "Open the same project on a second device",
                "Complete the main action without signing in",
            ],
            "Reload-persistence acceptance test vs cross-device sync test vs anonymous-access test.",
        ),
    }
    lens, question, options, diff = questions[slot]
    return make_question(lens, question, options, diff, slot=slot, score=2)


class DemoModels:
    async def close(self):
        pass

    async def call(self, session, role, schema, instruction, payload):
        if role.startswith("clarity:"):
            from .clarity_demo import demo_clarity

            return demo_clarity(session, role, payload)

        if role == "framework:map":
            from .framework_demo import demo_framework

            return demo_framework(session)
        if role == "framework:review":
            from .framework import ASPECTS, FrameworkAssessment

            return FrameworkAssessment(
                reviewed_entry_ids=list(payload["entry_catalog"]), reviewed_areas=list(ASPECTS),
            )
        if role == "graph:question":
            selected = payload["selected"]
            pending = selected.get("status") == "pending"
            return schema(
                text=(
                    f"DEMO · scripted explanation for {selected['title']}. "
                    + ("Details are pending; no implementation is established. " if pending else
                       "Inspect this section's scope, ancestors and cited requirements. ")
                    + "This answer does not change or approve the plan."
                ),
                citations=[f"node:{selected['id']}"],
                follow_up="What should this part do from your point of view?",
            )
        if role.startswith("planner:"):
            from .planning.demo import demo_response

            return schema.model_validate(demo_response(session, role, payload))
        if role == "baseline":
            return Critique(candidates=self.critique(session)[:3])
        if role == "extractor":
            return self.extract(session, payload["text"])
        if role.startswith("critic:"):
            lens = role.split(":", 1)[1]
            candidates = self.critique(session)
            return Critique(candidates=[q for q in candidates if q.lens == lens][:3])
        if role == "ranker":
            return Ranking(scores=[])
        if role == "playback":
            confirmed = [item.text.rstrip(".") for item in session.ledger if item.status == "confirmed"]
            groups = [confirmed[i : i + 3] for i in range(0, min(len(confirmed), 9), 3)]
            return Playback(sentences=["; ".join(group) + "." for group in groups] or ["Tell me your idea."])
        if role == "compiler":
            return Brief(
                lines=[
                    BriefLine(section="Decisions", text=item.text, ledger_ids=[item.id])
                    for item in session.ledger
                    if item.status == "confirmed"
                ]
            )
        if role == "verifier":
            return Verification()
        raise ValueError(f"Unknown demo role: {role}")

    def extract(self, session: Session, text: str) -> Delta:
        additions, updates = [], []

        def add(type, content, source, slot=None):
            additions.append(
                {"type": type, "text": content, "source": source, "status": "confirmed", "slot": slot}
            )

        question = session.current_question
        if question and len(text.strip()) > 1:
            if question.question == SYNC_QUESTION:
                choice = text.lower()
                if "code" in choice:
                    content = "Sync habits across devices using a shareable sync code, without accounts"
                elif "device" in choice:
                    content = "Keep habits on this device only for the first version"
                elif "email" in choice:
                    content = "Use an email magic link for cross-device access"
                    for item in session.ledger:
                        if item.slot == "access":
                            updates.append(
                                {
                                    "id": item.id,
                                    "text": "Use email magic-link access",
                                    "source": text,
                                    "status": "confirmed",
                                }
                            )
                else:
                    content = text
                add("decision", content, text, "data")
            elif question.question == AUTO_QUESTION:
                add("decision", text, text)
                for item in session.ledger:
                    if item.type == "feature" and "automatic" in item.text.lower():
                        updates.append({"id": item.id, "text": text, "source": text, "status": "confirmed"})
            elif session.clarity_version == 2 and v2_answer_slot(question, text):
                kind, slot = v2_answer_slot(question, text)
                add(kind, text, text, slot)
            else:
                types = {
                    "goal": "goal",
                    "core-flow": "feature",
                    "data": "data",
                    "access": "user",
                    "non-goals": "non-goal",
                    "success-criterion": "success-criterion",
                }
                add(types.get(question.slot, "decision"), text, text, question.slot)
            return Delta.model_validate(
                {"add": additions, "update": updates, "answers_question": question.id}
            )
        if session.turns and len(session.turns) > 1:
            for item in session.ledger:
                if "this device only" in text.lower() and item.slot == "data":
                    updates.append(
                        {
                            "id": item.id,
                            "text": "Keep data on this device only",
                            "status": "confirmed",
                            "source": text,
                        }
                    )
            if not updates:
                add("decision", text, text)
            return Delta.model_validate({"add": additions, "update": updates})
        habit = re.search(r"habit tracker", text, re.I)
        if habit:
            add("goal", "Build a personal habit tracker", habit.group(), "goal")
        else:
            add("goal", text[:500], text[:500], "goal")
        if session.clarity_version == 2:
            opening = re.split(r"[.!?;,]", text, maxsplit=1)[0].strip()
            if opening:
                add("feature", opening, opening, "core-flow")
        no_login = re.search(r"no login|without (?:an? )?(?:account|login)", text, re.I)
        if no_login:
            add("constraint", "No login screen", no_login.group(), "access")
        sync = re.search(r"saved across my phone and laptop|(?:sync|saved) across devices", text, re.I)
        if sync:
            add("data", "Habits should be saved across phone and laptop", sync.group(), "data")
        automatic = re.search(r"reminders should be automatic|automatic reminders", text, re.I)
        if automatic:
            add("feature", "Automatic reminders; exact behaviour is undecided", automatic.group())
        return Delta.model_validate({"add": additions})

    def critique(self, session: Session) -> list[Candidate]:
        text = " ".join(item.text.lower() for item in session.ledger)
        asked = {item.question.question for item in session.questions}
        questions = []
        ids = [item.id for item in session.ledger]
        if "no login" in text and "across" in text and SYNC_QUESTION not in asked:
            questions.append(
                make_question(
                    "contradictions",
                    SYNC_QUESTION,
                    ["Shareable sync code", "This device only for now", "Email magic link"],
                    "A code-to-project lookup table and sync API vs localStorage only "
                    "vs an email auth provider and users table.",
                    targets=ids[:3],
                )
            )
        if "automatic" in text and AUTO_QUESTION not in asked:
            questions.append(
                make_question(
                    "behaviour",
                    AUTO_QUESTION,
                    ["Send a daily reminder", "Mark habits done automatically", "Manual reminders for now"],
                    "A notification scheduler and permission UI vs a scheduled "
                    "completion job vs no notification worker.",
                    targets=ids[-1:],
                )
            )
        missing = gate_for(session).missing
        questions.extend(slot_question(slot) for slot in missing)
        return questions
