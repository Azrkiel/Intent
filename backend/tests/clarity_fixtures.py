"""Reading-queue ledger from the 2026-10-29 human review. Synthetic, not live evidence."""

from backend.app.clarity.contracts import ClaimDraft, Span
from backend.app.domain import AskedQuestion, Candidate, LedgerItem, Session, Turn

SOURCES = [
    ("L1", "goal", "goal", "Build my reading queue"),
    ("L2", "constraint", "access", "Only me, one laptop browser, no account"),
    (
        "L3",
        "feature",
        "core-flow",
        "Enter a title and https URL, click Add, and show the unread article newest first",
    ),
    ("L4", "data", "data", "Save id, title, URL and read status in localStorage"),
    (
        "L5",
        "feature",
        None,
        "I can mark read/unread, filter All/Unread/Read, open links in a new tab and delete immediately",
    ),
    ("L6", "constraint", None, "Reject blank titles and non-https URLs inline; allow duplicates"),
    ("L7", "constraint", None, "If saving fails keep the old list and form inputs with a Retry button"),
    ("L8", "constraint", None, "If stored JSON is corrupt offer Reset and wait for my click"),
    (
        "L9",
        "non-goal",
        "non-goals",
        "No server, sync, sharing, scraping, summaries, notifications or payments",
    ),
    (
        "L10",
        "success-criterion",
        "success-criterion",
        "Success: add two links, mark one read, filter unread to see the other, reload to retain "
        "state, delete one and reload to confirm deletion",
    ),
    ("L11", "decision", None, "Use reversible technical defaults."),
]


# What the scripted demo asks of a v2 session, with the answers a user would give.
ANSWERS = [
    ("north-star", "NS-who-when-missing-r1", "Who uses it?", "Just me, on my laptop, once a day"),
    ("north-star", "NS-ambition-missing-r2", "How big?", "A personal tool only I use"),
    ("north-star", "NS-today-missing-r3", "Today?", "I keep links in browser tabs and lose them"),
    ("north-star", "NS-good-missing-r4", "Good looks like?", "I find a saved link in under ten seconds"),
    ("north-star", "NS-fails-if-missing-r5", "Fails if?", "If a saved link is gone after a reload"),
    (
        "decision",
        "D:data-model:6:1",
        "Should your information stay on this device, or be stored on a server?",
        "Keep it on this device only",
    ),
    (
        "decision",
        "D:identity:7:1",
        "Should the first version leave out accounts, payments and sharing?",
        "Leave them out of the first version",
    ),
]


def answer_scripted_questions(session: Session) -> Session:
    for lens, key, question, answer in ANSWERS:
        number = len(session.turns) + 1
        session.turns.append(Turn(number=number, text=answer))
        candidate = Candidate(
            id=key,
            lens=lens,
            targets=[],
            question=question,
            options=[answer, "Something else"],
            code_diff="Scripted follow-up for the demo conversation",
            divergence=3,
            uncertainty=3,
            cost_to_change=3,
        )
        session.questions.append(AskedQuestion(question=candidate, answer=answer, turn=number))
    return session


def reading_queue_session(answered: bool = True) -> Session:
    text = ". ".join(source.rstrip(".") for *_, source in SOURCES) + "."
    session = Session(
        id="reading-queue",
        mode="live",
        clarity_version=2,
        revision=1,
        extracted_revision=1,
        analysis_complete=True,
        turns=[Turn(number=1, text=text)],
    )
    session.ledger = [
        LedgerItem(id=id, type=type, slot=slot, text=source, source=source, status="confirmed", turn=1)
        for id, type, slot, source in SOURCES
    ]
    return answer_scripted_questions(session) if answered else session


def draft(text, tags, basis="stated", spans=(), **extra) -> ClaimDraft:
    return ClaimDraft(
        text=text,
        tags=list(tags),
        basis=basis,
        spans=[Span(item_id=item, quote=quote) for item, quote in spans],
        **extra,
    )
