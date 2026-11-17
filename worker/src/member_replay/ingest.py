"""The one place anything (sync activity, push producer, demo CLI) turns Cortex data into a Signal.
Signal-with-start creates the Member's workflow on its first event and signals it if it already exists."""
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from member_replay import config
from member_replay.models import EventsBatch, MemberProfile, MemberState, RetailOrderPlaced, TicketPurchased


async def _signal_with_start(client: Client, scv_user_id: str, signal: str, arg: object) -> None:
    await client.start_workflow(
        "MemberWorkflow",  # by name: importing the class here would create an import cycle
        MemberState(scv_user_id=scv_user_id),
        id=config.member_workflow_id(scv_user_id),
        task_queue=config.TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        start_signal=signal,
        start_signal_args=[arg],
    )


async def ensure_member(client: Client, scv_user_id: str) -> None:
    """Every Member gets a workflow, active or not. No Signal, so an existing one is left untouched."""
    await client.start_workflow(
        "MemberWorkflow",
        MemberState(scv_user_id=scv_user_id),
        id=config.member_workflow_id(scv_user_id),
        task_queue=config.TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


async def send_ticket(client: Client, scv_user_id: str, event: TicketPurchased) -> None:
    await _signal_with_start(client, scv_user_id, "ticket_purchased", event)


async def send_retail(client: Client, scv_user_id: str, event: RetailOrderPlaced) -> None:
    await _signal_with_start(client, scv_user_id, "retail_order_placed", event)


async def send_profile(client: Client, scv_user_id: str, profile: MemberProfile) -> None:
    await _signal_with_start(client, scv_user_id, "profile_updated", profile)


async def send_batch(client: Client, scv_user_id: str, batch: EventsBatch) -> None:
    await _signal_with_start(client, scv_user_id, "events_batch", batch)
