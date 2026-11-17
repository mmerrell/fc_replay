"""Workflow tests against a local Temporal dev server (downloads it on first run; needs network).
NOTE: the worker here is unversioned. If your SDK rejects a PINNED-annotated workflow on an unversioned worker,
give the Worker the same deployment_config as worker.py and set the version current first."""
import uuid

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from member_replay.models import EventsBatch, MemberState, RetailOrderPlaced, TicketPurchased
from member_replay.workflows import MemberWorkflow

TQ = "test-member-replay"


def _t(i, v=30.0, attended=False):
    return TicketPurchased(i, "p", "Crystal Palace v Fulham", "2026-09-01T12:00:00.000Z", v, attended)


async def test_signals_aggregate_and_dedupe():
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(env.client, task_queue=TQ, workflows=[MemberWorkflow]):
            h = await env.client.start_workflow(
                MemberWorkflow.run, MemberState("u1"), id=f"member-{uuid.uuid4()}", task_queue=TQ
            )
            await h.signal(MemberWorkflow.ticket_purchased, _t("t1"))
            await h.signal(MemberWorkflow.ticket_purchased, _t("t1"))  # duplicate delivery
            await h.signal(MemberWorkflow.ticket_purchased, _t("t1", attended=True))  # attendance arrives later
            await h.signal(MemberWorkflow.retail_order_placed,
                           RetailOrderPlaced("r1", "sku", "Pie", "2026-09-01T13:00:00.000Z", 11.0, 2, "Food"))
            s = await h.query(MemberWorkflow.summary)
            assert (s.tickets_purchased, s.matches_attended, s.ticket_spend) == (1, 1, 30.0)
            assert (s.retail_orders, s.retail_items, s.total_spend) == (1, 2, 41.0)
            assert [e.event_id for e in await h.query(MemberWorkflow.timeline)] == ["t1", "r1"]


async def test_signal_with_start_and_batch():
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(env.client, task_queue=TQ, workflows=[MemberWorkflow]):
            wid = f"member-{uuid.uuid4()}"
            h = await env.client.start_workflow(
                "MemberWorkflow", MemberState("u2"), id=wid, task_queue=TQ,
                start_signal="events_batch", start_signal_args=[EventsBatch(tickets=[_t("a"), _t("b", 20.0)])],
            )
            assert (await h.query(MemberWorkflow.summary)).tickets_purchased == 2


async def test_member_deleted_ends_workflow():
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(env.client, task_queue=TQ, workflows=[MemberWorkflow]):
            h = await env.client.start_workflow(
                MemberWorkflow.run, MemberState("u3"), id=f"member-{uuid.uuid4()}", task_queue=TQ
            )
            await h.signal(MemberWorkflow.member_deleted)
            assert await h.result() is None


async def test_profile_signal_and_sync_marks():
    from member_replay.models import MemberProfile
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(env.client, task_queue=TQ, workflows=[MemberWorkflow]):
            h = await env.client.start_workflow(
                "MemberWorkflow", MemberState("u4"), id=f"member-{uuid.uuid4()}", task_queue=TQ,
                start_signal="profile_updated",
                start_signal_args=[MemberProfile("Ada", "Lowe", "Reading", "GB", "Adam Sandoval", "3000", "fp")],
            )
            s = await h.query(MemberWorkflow.summary)
            assert s.profile.first_name == "Ada" and s.profile.favourite_player == "Adam Sandoval"
            marks = await h.query(MemberWorkflow.sync_marks)
            assert marks.profile_fingerprint == "fp" and marks.activity_watermark is None
