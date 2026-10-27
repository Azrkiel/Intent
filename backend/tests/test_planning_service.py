import pytest

from backend.app.demo import DemoModels
from backend.app.engine import Engine
from backend.app.models import ModelError
from backend.app.planning.service import PlanningService
from backend.app.settings import Settings
from backend.app.store import Store
from backend.tests.planning_fixtures import ready_session


async def collect(service, session):
    return [event async for event in service.generate(session)]


@pytest.fixture
def setup(tmp_path):
    store = Store(str(tmp_path / "sessions.db"))
    session = ready_session()
    store.save(session)
    return store, session, PlanningService(store, DemoModels(), Settings())


async def test_generation_is_incremental_cached_and_does_not_use_compiler(setup):
    store, session, service = setup
    events = await collect(service, session)
    assert events[0]["type"] == "plan_started"
    assert len([e for e in events if e["type"] == "plan_section"]) >= 3
    assert events[-1]["type"] == "plan_ready"
    assert session.planning.status == "review_ready" and session.planning.approval is None
    assert session.compiler_calls == 0
    passes = list(session.planning.attempts[0].passes)
    assert len(await collect(service, session)) == 1
    assert session.planning.attempts[0].passes == passes
    active = session.planning.active
    doc = store.get_plan(session.id, active.plan_id, active.revision)
    assert doc.sources[0].source == "Save notes"
    assert store.get(session.id).planning.active == active


@pytest.mark.parametrize(
    "failure", ["planner:outline", "planner:screen:main", "planner:phase:foundation", "planner:verify"]
)
async def test_failed_passes_block_and_remain_bounded(setup, failure):
    store, session, _ = setup

    class Failing(DemoModels):
        async def call(self, current, role, schema, instruction, payload):
            if role == failure:
                from backend.app.domain import Usage

                current.usage.append(
                    Usage(
                        role=role,
                        model="synthetic",
                        input_tokens=1,
                        output_tokens=1,
                        estimated_usd=0.01,
                        latency_ms=1,
                    )
                )
                raise ModelError("Synthetic failure")
            return await super().call(current, role, schema, instruction, payload)

    service = PlanningService(store, Failing(), Settings())
    for _ in range(2):
        events = await collect(service, session)
        assert events[-1]["type"] == "plan_error"
        assert session.planning.status == "blocked" and session.planning.approval is None
        assert failure in session.planning.attempts[-1].passes
    assert len(store.get(session.id).usage) == 2
    with pytest.raises(ValueError, match="allowance"):
        await collect(service, session)


async def test_semantic_rejection_or_incomplete_review_blocks_readiness(setup):
    store, session, _ = setup

    class Rejecting(DemoModels):
        async def call(self, current, role, schema, instruction, payload):
            if role == "planner:verify":
                return schema(reviewed_statement_ids=[], rejected_statement_ids=[], missing_ledger_ids=[])
            return await super().call(current, role, schema, instruction, payload)

    events = await collect(PlanningService(store, Rejecting(), Settings()), session)
    assert events[-1]["type"] == "plan_error"
    assert session.planning.active is None


async def test_correction_invalidates_plan_and_retains_snapshots_and_attempts(setup):
    store, session, service = setup
    await collect(service, session)
    active = session.planning.active
    session.planning.approval = active
    session.planning.status = "approved"
    engine = Engine(store, DemoModels())
    async for _ in engine.turn(session, "Use browser storage only"):
        pass
    assert session.planning.status == "stale"
    assert session.planning.approval is None
    assert len(session.planning.attempts) == 1
    assert store.get_plan(session.id, active.plan_id, active.revision)


async def test_mode_mismatch_and_unapproved_requirements_cannot_generate(setup):
    _, session, service = setup
    session.approved_revision = None
    with pytest.raises(ValueError):
        await collect(service, session)
    session.approved_revision = 1
    session.mode = "live"
    with pytest.raises(ValueError):
        await collect(service, session)


async def test_interrupted_generator_preserves_sections_and_consumes_attempt(setup):
    store, session, service = setup
    generator = service.generate(session)
    await anext(generator)
    await anext(generator)
    await generator.aclose()
    restored = store.get(session.id)
    assert restored.planning.status == "blocked"
    assert restored.planning.attempts[-1].outline is not None
    assert restored.planning.attempts[-1].error


async def test_live_adapter_planning_uses_super_and_retains_repaired_response_usage(tmp_path):
    import json

    import httpx
    from openai import AsyncOpenAI

    from backend.app.models import LiveModels
    from backend.app.planning.demo import demo_response
    from backend.tests.test_models import completion

    session = ready_session()
    session.mode = "live"
    store = Store(str(tmp_path / "live.db"))
    requests = []
    roles = [
        "planner:outline",
        "planner:screen:main",
        "planner:phase:foundation",
        "planner:phase:implementation",
        "planner:verify",
    ]

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            return httpx.Response(200, json=completion("invalid synthetic JSON"))
        role = roles[len(requests) - 2]
        payload = json.loads(body["messages"][1]["content"])
        return httpx.Response(200, json=completion(json.dumps(demo_response(session, role, payload))))

    client = AsyncOpenAI(
        api_key="synthetic",
        base_url="https://test.invalid/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    settings = Settings(mode="live")
    provider = LiveModels(settings, client=client)
    try:
        events = await collect(PlanningService(store, provider, settings), session)
        assert events[-1]["type"] == "plan_ready", events[-1]
        assert all(x["model"] == settings.super_model for x in requests)
        assert all("reasoning_budget" not in x for x in requests)
        assert len(store.get(session.id).usage) == 6
        assert session.compiler_calls == 0
        assert provider.reserved[session.id] == 0
    finally:
        await client.close()


async def test_planning_uses_existing_budget_without_resetting_usage(setup):
    from backend.app.domain import Usage
    from backend.app.models import LiveModels

    store, session, _ = setup
    session.mode = "live"
    session.usage = [
        Usage(
            role="extractor",
            model="synthetic",
            input_tokens=1,
            output_tokens=1,
            estimated_usd=1.999999,
            latency_ms=1,
        )
    ]
    provider = LiveModels(Settings(mode="live"))
    events = await collect(PlanningService(store, provider, provider.settings), session)
    assert events[-1]["type"] == "plan_error"
    assert "budget" in events[-1]["message"].lower()
    assert len(store.get(session.id).usage) == 1
