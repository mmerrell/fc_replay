import asyncio

from temporalio import activity
from temporalio.client import Client

from member_replay import config, ingest
from member_replay.cortex import CortexClient
from member_replay.models import EventsBatch, SyncMarks, SyncResult


class CortexActivities:
    """Activities that talk to Cortex and push what they find into MemberWorkflows (all I/O lives here)."""

    def __init__(self, client: Client, cortex: CortexClient) -> None:
        self._client = client
        self._cortex = cortex

    @activity.defn
    async def list_member_ids(self) -> list[str]:
        # MOCK ONLY (see CortexClient.list_member_ids): real source of Member ids is TBD.
        return await asyncio.to_thread(self._cortex.list_member_ids)

    async def _marks(self, scv_user_id: str) -> SyncMarks:
        """What the Member's workflow has already applied (empty marks if it doesn't exist yet)."""
        try:
            return await self._client.get_workflow_handle(config.member_workflow_id(scv_user_id)).query(
                "sync_marks", result_type=SyncMarks
            )
        except Exception:  # noqa: BLE001 - no workflow yet (or not reachable): fall back to a full sync
            return SyncMarks()

    @activity.defn
    async def sync_members(self, scv_user_ids: list[str]) -> SyncResult:
        """Pull one chunk of Members from Cortex. Only records newer than each Member's watermark, and only a
        changed profile, are sent, so an unchanged Member costs no workflow history. Every Member gets a workflow
        (the first profile Signal creates it), active or not. Safe to re-run: MemberWorkflow also dedupes on
        Cortex record ids. One bad Member doesn't fail the chunk; it is reported in `errors`."""
        result = SyncResult()
        for uid in scv_user_ids:
            activity.heartbeat(uid)
            try:
                marks = await self._marks(uid)
                act = await asyncio.to_thread(self._cortex.fetch_activity, uid, marks.activity_watermark)
                profile = await asyncio.to_thread(self._cortex.fetch_profile, uid)
                if profile.fingerprint != marks.profile_fingerprint:
                    await ingest.send_profile(self._client, uid, profile)  # also creates the workflow
                if act.tickets or act.retails:
                    await ingest.send_batch(self._client, uid, EventsBatch(tickets=act.tickets, retails=act.retails))
                result.members += 1
                result.tickets += len(act.tickets)
                result.retails += len(act.retails)
            except Exception as e:  # noqa: BLE001 - per-member isolation
                activity.logger.warning("sync failed for %s: %s", uid, e)
                result.errors.append(f"{uid}: {e}")
        return result
