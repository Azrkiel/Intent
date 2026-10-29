"""One effective limit shared by planning, API detail, and operator preflight."""

from .contracts import content_hash


def state_hash(session):
    return content_hash(session.model_dump(mode="json", round_trip=True))


def attempt_limit(session, default):
    eighth = session.planning.eighth_attempt
    if default == 2 and eighth and eighth.session_id == session.id:
        if eighth.status == "consumed" or (
            eighth.status == "granted"
            and eighth.requirements_revision == session.revision == session.approved_revision
        ):
            return 8
    seventh = session.planning.seventh_attempt
    if default == 2 and seventh and seventh.session_id == session.id:
        if seventh.status == "consumed" or (
            seventh.status == "granted"
            and seventh.requirements_revision == session.revision == session.approved_revision
        ):
            return 7
    sixth = session.planning.sixth_attempt
    if default == 2 and sixth and sixth.session_id == session.id:
        if sixth.status == "consumed" or (
            sixth.status == "granted"
            and sixth.requirements_revision == session.revision == session.approved_revision
        ):
            return 6
    fifth = session.planning.fifth_attempt
    if default == 2 and fifth and fifth.session_id == session.id:
        if fifth.status == "consumed" or (
            fifth.status == "granted"
            and fifth.requirements_revision == session.revision == session.approved_revision
        ):
            return 5
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
