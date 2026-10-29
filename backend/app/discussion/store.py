import json

from ..planning.contracts import content_hash
from .contracts import DiscussionMessage, DiscussionTarget


class DiscussionStore:
    """A durable unique request is claimed before any external model side effect."""

    def __init__(self, sessions):
        self.sessions = sessions
        with sessions.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS graph_discussions (
                session_id TEXT NOT NULL, request_id TEXT NOT NULL, thread_hash TEXT NOT NULL,
                target TEXT NOT NULL, title TEXT NOT NULL, payload_hash TEXT NOT NULL,
                record TEXT NOT NULL, context TEXT NOT NULL, created_at REAL NOT NULL,
                PRIMARY KEY(session_id,request_id))""")

    def lookup(self, session_id, request):
        with self.sessions.connect() as db:
            row = db.execute(
                "SELECT payload_hash,record FROM graph_discussions WHERE session_id=? AND request_id=?",
                (session_id, request.request_id),
            ).fetchone()
        if not row:
            return None
        if row[0] != content_hash(request.model_dump(mode="json", exclude={"request_id"})):
            raise ValueError("Request ID was already used for different text or source")
        return DiscussionMessage.model_validate_json(row[1])

    def reserve(self, session_id, request, title, context):
        digest = content_hash(request.model_dump(mode="json", exclude={"request_id"}))
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload_hash,record FROM graph_discussions WHERE session_id=? AND request_id=?",
                (session_id, request.request_id),
            ).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError("Request ID was already used for different text or source")
                return DiscussionMessage.model_validate_json(row[1]), False
            message = DiscussionMessage(request_id=request.request_id, mode=request.mode, text=request.text)
            target = request.target.model_dump(mode="json")
            db.execute("INSERT INTO graph_discussions VALUES(?,?,?,?,?,?,?,?,?)", (
                session_id, request.request_id, content_hash(target), json.dumps(target), title, digest,
                message.model_dump_json(), json.dumps(context, ensure_ascii=False), message.created_at,
            ))
        return message, True

    def update(self, session_id, message):
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT record FROM graph_discussions WHERE session_id=? AND request_id=?",
                (session_id, message.request_id),
            ).fetchone()
            saved = DiscussionMessage.model_validate_json(row[0])
            if saved.status != "pending":
                return saved
            db.execute("UPDATE graph_discussions SET record=? WHERE session_id=? AND request_id=?",
                       (message.model_dump_json(), session_id, message.request_id))
        return message

    def rows(self, session_id):
        with self.sessions.connect() as db:
            return db.execute(
                "SELECT target,title,record,context FROM graph_discussions "
                "WHERE session_id=? ORDER BY created_at,request_id",
                (session_id,),
            ).fetchall()

    def messages(self, session_id, target):
        return [DiscussionMessage.model_validate_json(row[2]) for row in self.rows(session_id)
                if DiscussionTarget.model_validate_json(row[0]) == target]

    def history(self, session_id, target):
        groups = {}
        for raw, title, record, _ in self.rows(session_id):
            source = DiscussionTarget.model_validate_json(raw)
            if source.node_id != target.node_id or source == target:
                continue
            entry = groups.setdefault(content_hash(source.model_dump()), {
                "target": source.model_dump(), "title": title, "messages": [],
            })
            entry["messages"].append(DiscussionMessage.model_validate_json(record).model_dump())
        return list(groups.values())

    def activity(self, session_id, target):
        activity = {}
        identity = target.model_dump(exclude={"node_id", "node_hash"})
        for raw, _, record, _ in self.rows(session_id):
            source = DiscussionTarget.model_validate_json(raw)
            if source.model_dump(exclude={"node_id", "node_hash"}) != identity:
                continue
            if source.kind == "intent" and source.node_hash != target.node_hash:
                continue
            message = DiscussionMessage.model_validate_json(record)
            entry = activity.setdefault(source.node_id, {"messages": 0, "pending_direction": False})
            entry["messages"] += 1
            entry["pending_direction"] |= message.mode == "direction" and message.turn_number is not None
        return activity

    def context_for_turn(self, session_id, turn_number):
        for _, _, record, context in self.rows(session_id):
            message = DiscussionMessage.model_validate_json(record)
            if message.mode == "direction" and message.turn_number == turn_number:
                return json.loads(context)
        return None

    def recover(self):
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT session_id,request_id,record FROM graph_discussions").fetchall()
            for session_id, request_id, raw in rows:
                message = DiscussionMessage.model_validate_json(raw)
                if message.status == "pending":
                    message.status = "uncertain"
                    message.error = "The server stopped during this request. No automatic replay will occur."
                    db.execute("UPDATE graph_discussions SET record=? WHERE session_id=? AND request_id=?",
                               (message.model_dump_json(), session_id, request_id))
