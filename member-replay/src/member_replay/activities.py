from temporalio import activity

# All I/O lives here (workflow code must stay deterministic).


@activity.defn
async def list_member_ids() -> list[str]:
    """TODO: where does the member list come from? Cortex's query API is per-user only; the mock has /_mock/fans."""
    raise NotImplementedError


@activity.defn
async def fetch_member_activity(scv_user_id: str, since: str | None) -> dict:
    """TODO: page tickets/retails/structuredEvents for one Member (sort -updatedAt, stop at `since`)."""
    raise NotImplementedError
