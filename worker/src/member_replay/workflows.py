import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import VersioningBehavior

with workflow.unsafe.imports_passed_through():
    from member_replay.activities import CortexActivities
    from member_replay.models import (
        EventsBatch,
        MemberProfile,
        MemberState,
        ReplaySummary,
        RetailOrderPlaced,
        SyncMarks,
        SyncParams,
        SyncResult,
        TicketPurchased,
        TimelineEntry,
    )

try:  # Upgrade-on-Continue-as-New is newer than Worker Versioning itself; degrade gracefully on older SDKs.
    from temporalio.workflow import ContinueAsNewVersioningBehavior
except ImportError:  # pragma: no cover
    ContinueAsNewVersioningBehavior = None

# An idle Member gets no Workflow Tasks, and "newer build available" is only refreshed when one runs.
# This timer wakes idle Members so they can notice a new build and upgrade at Continue-as-New.
VERSION_CHECK_INTERVAL = timedelta(hours=1)


def _newer_build_available() -> bool:
    check = getattr(workflow.info(), "is_target_worker_deployment_version_changed", None)
    return bool(check and check())


@workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
class MemberWorkflow:
    """One long-running execution per Member (id = member_workflow_id(scv_user_id)).

    Cortex remains the source of truth; this is the Member's materialised timeline and Replay aggregates.
    Pinned: a run stays on the build it started on and moves to a newer build only at Continue-as-New."""

    @workflow.init
    def __init__(self, state: MemberState) -> None:
        # @workflow.init so a Signal delivered with the start (signal-with-start) sees real state.
        self._state = state
        self._deleted = False

    @workflow.run
    async def run(self, state: MemberState) -> None:
        while not (self._deleted or self._should_continue_as_new()):
            try:
                await workflow.wait_condition(
                    lambda: self._deleted or self._should_continue_as_new(), timeout=VERSION_CHECK_INTERVAL
                )
            except asyncio.TimeoutError:
                pass  # just a wake-up so the "newer build" flag gets refreshed

        await workflow.wait_condition(workflow.all_handlers_finished)
        if self._deleted:
            return  # Member removed upstream (e.g. Cortex fan deletion): end the workflow

        kwargs = {}
        if ContinueAsNewVersioningBehavior is not None and _newer_build_available():
            kwargs["initial_versioning_behavior"] = ContinueAsNewVersioningBehavior.AUTO_UPGRADE
        workflow.continue_as_new(self._state, **kwargs)

    def _should_continue_as_new(self) -> bool:
        return workflow.info().is_continue_as_new_suggested() or _newer_build_available()

    # --- Signals (at-least-once delivery; MemberState dedupes on Cortex record ids) ---
    @workflow.signal
    def ticket_purchased(self, event: TicketPurchased) -> None:
        self._state.apply_ticket(event)

    @workflow.signal
    def retail_order_placed(self, event: RetailOrderPlaced) -> None:
        self._state.apply_retail(event)

    @workflow.signal
    def events_batch(self, batch: EventsBatch) -> None:
        self._state.apply_batch(batch)

    @workflow.signal
    def profile_updated(self, profile: MemberProfile) -> None:
        self._state.apply_profile(profile)

    @workflow.signal
    def member_deleted(self) -> None:
        self._deleted = True

    # --- Queries ---
    @workflow.query
    def summary(self) -> ReplaySummary:
        return self._state.summary()

    @workflow.query
    def sync_marks(self) -> SyncMarks:
        return self._state.sync_marks()

    @workflow.query
    def timeline(self) -> list[TimelineEntry]:
        return self._state.sorted_timeline()


@workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
class MemberSyncWorkflow:
    """Reconciliation path (run by a Temporal Schedule): pull every Member from Cortex and signal their
    MemberWorkflow. Named 'Sync' rather than 'Update' to avoid confusion with Temporal Updates."""

    @workflow.run
    async def run(self, params: Optional[SyncParams] = None) -> SyncResult:
        params = params or SyncParams()
        ids = await workflow.execute_activity_method(
            CortexActivities.list_member_ids, start_to_close_timeout=timedelta(minutes=1)
        )
        chunks = [ids[i : i + params.chunk_size] for i in range(0, len(ids), params.chunk_size)]
        gate = asyncio.Semaphore(params.concurrency)

        async def run_chunk(chunk: list[str]) -> SyncResult:
            async with gate:
                return await workflow.execute_activity_method(
                    CortexActivities.sync_members,
                    chunk,
                    start_to_close_timeout=timedelta(minutes=5),
                    heartbeat_timeout=timedelta(seconds=30),
                )

        total = SyncResult()
        for r in await asyncio.gather(*(run_chunk(c) for c in chunks)):
            total.members += r.members
            total.tickets += r.tickets
            total.retails += r.retails
            total.errors.extend(r.errors)
        return total
