"""One effective limit shared by planning, API detail, and operator preflight."""

from .contracts import content_hash


def state_hash(session):
    return content_hash(session.model_dump(mode="json", round_trip=True))


def attempt_limit(session, default):
    qualification = session.planning.requalification
    if default == 2 and qualification and qualification.session_id == session.id:
        if qualification.status == "consumed" or (
            qualification.status == "granted"
            and qualification.requirements_revision == session.revision == session.approved_revision
        ):
            return 4
    grant = session.planning.extension
    if default == 2 and grant and grant.session_id == session.id:
        if grant.status == "consumed" or (
            grant.status == "granted"
            and grant.requirements_revision == session.revision == session.approved_revision
        ):
            return 3
    return default
