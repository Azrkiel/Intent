"""Intent owns dispatch. A completed turn never proves integration or phase acceptance."""

from ..planning.validation import safe_path


def interface_conflict(left, right):
    def parse(value):
        mode, _, ref = value.partition(":")
        if mode not in {"read", "write"}:
            return "write", value, None
        name, _, version = ref.partition("@")
        return mode, name, version

    for a in left:
        am, an, av = parse(a)
        for b in right:
            bm, bn, bv = parse(b)
            if an == bn and (am != "read" or bm != "read" or av != bv):
                return True
    return False


class Scheduler:
    def __init__(self, runs, *, capacity=1, global_capacity=2):
        if not 1 <= capacity <= global_capacity <= 2:
            raise ValueError("Worker capacity must be one or two and fit the global limit")
        self.runs, self.capacity, self.global_capacity = runs, capacity, global_capacity

    def eligible(self, session_id, document, phase_id):
        phase = next((p for p in document.phases if p.id == phase_id), None)
        if phase is None:
            raise ValueError("Unknown phase")
        phases = {
            p.phase_id: p
            for p in self.runs.phases(session_id)
            if p.plan.content_hash == document.content_hash
        }
        for earlier in document.phases[: document.phases.index(phase)]:
            saved = phases.get(earlier.id)
            if not saved or saved.status != "accepted" or saved.stale or saved.promotion_intent:
                raise ValueError("Earlier phases must be explicitly accepted before dispatch")
        saved = phases.get(phase_id)
        if saved and (
            saved.status != "running" or saved.stale or saved.integration_intent or saved.promotion_intent
        ):
            raise ValueError("Phase requires review, acceptance, repair, or reconciliation")
        records = [
            r for r in self.runs.current_runs(session_id) if r.plan.content_hash == document.content_hash
        ]
        current = [r for r in records if r.package_id.split("-W")[0] == phase_id]
        if any(r.status in {"blocked", "cancelled"} or r.stale for r in current):
            raise ValueError("Phase is blocked; repair/review is required")
        attempted = {r.package_id for r in records}
        integrated = {r.package_id for r in records if r.status == "integrated" and r.integrated_commit}
        producers = {i.name: p.id for ph in document.phases for p in ph.packages for i in p.produces}
        return [
            p
            for p in sorted(phase.packages, key=lambda p: p.id)
            if p.id not in attempted
            and set(document.dependency_ids[p.id]) <= integrated
            and all(producers.get(i.name) in integrated for i in p.consumes)
        ]

    def claim(self, run, paths, interfaces, *, allowance=True):
        if not allowance:
            raise ValueError("Codex account allowance is exhausted")
        for path in paths:
            safe_path(path)
        run.owned_paths, run.interfaces = list(paths), sorted(set(interfaces))
        return self.runs.claim(run, capacity=self.capacity, global_capacity=self.global_capacity)
