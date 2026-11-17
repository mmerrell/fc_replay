from temporalio import workflow
from temporalio.common import VersioningBehavior

with workflow.unsafe.imports_passed_through():
    from member_replay.models import MemberState, RetailOrderPlaced, TicketPurchased


@workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
class MemberWorkflow:
    """One long-running execution per Member; workflow id = member_workflow_id(scv_user_id).

    Pinned: each run stays on the build it started on. Move to newer builds at Continue-as-New
    (see README, 'Versioning')."""

    def __init__(self) -> None:
        # TODO: initialise state / dedupe set
        pass

    @workflow.run
    async def run(self, state: MemberState) -> None:
        # TODO: wait for signals; Continue-as-New on history size and when a newer build is available
        raise NotImplementedError

    @workflow.signal
    async def ticket_purchased(self, event: TicketPurchased) -> None:
        # TODO: dedupe on event.event_id, fold into state
        raise NotImplementedError

    @workflow.signal
    async def retail_order_placed(self, event: RetailOrderPlaced) -> None:
        # TODO
        raise NotImplementedError

    @workflow.query
    def timeline(self) -> dict:
        # TODO: whatever the Replay needs to render
        raise NotImplementedError


@workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
class MemberSyncWorkflow:
    """Reconciliation path: triggered by a Temporal Schedule, pulls from Cortex and signals MemberWorkflows.
    (Named 'Sync' rather than 'Update' to avoid confusion with Temporal Updates.)"""

    @workflow.run
    async def run(self) -> None:
        # TODO: list members -> fetch activity (batched) -> signal-with-start MemberWorkflow
        raise NotImplementedError
