"""Demo/ops CLI:  python -m member_replay.starter <command>
  sync                    run one sync now and print the result
  schedule [--minutes N]  create/update the recurring sync Schedule (default every 5 minutes)
  summary <scvUserId>     query a Member's Replay aggregates
  timeline <scvUserId>    query a Member's timeline
  ticket <scvUserId>      push a synthetic ticket purchase (the 'push' path, for live demos)
  retail <scvUserId>      push a synthetic retail order (home shirt)
  delete <scvUserId>      signal that a Member was deleted upstream (ends their workflow)"""
import argparse
import asyncio
import dataclasses
import json
import uuid
from datetime import datetime, timedelta, timezone

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleUpdate,
)

from member_replay import config, ingest
from member_replay.models import RetailOrderPlaced, TicketPurchased
from member_replay.workflows import MemberSyncWorkflow, MemberWorkflow


def _dump(obj) -> str:
    return json.dumps(dataclasses.asdict(obj) if dataclasses.is_dataclass(obj) else obj, indent=2, default=str)


async def main() -> None:
    p = argparse.ArgumentParser(prog="member_replay.starter")
    p.add_argument("command", choices=["sync", "schedule", "summary", "timeline", "ticket", "retail", "delete"])
    p.add_argument("member", nargs="?", help="scvUserId")
    p.add_argument("--minutes", type=int, default=5)
    a = p.parse_args()
    client = await Client.connect(config.TEMPORAL_ADDRESS, namespace=config.TEMPORAL_NAMESPACE)

    if a.command == "sync":
        result = await client.execute_workflow(
            MemberSyncWorkflow.run, id=f"member-sync-{uuid.uuid4().hex[:8]}", task_queue=config.TASK_QUEUE
        )
        print(_dump(result))
        return

    if a.command == "schedule":
        schedule = Schedule(
            action=ScheduleActionStartWorkflow(
                MemberSyncWorkflow.run, id="member-sync-scheduled", task_queue=config.TASK_QUEUE
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(minutes=a.minutes))]),
            policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
        )
        try:
            await client.create_schedule(config.SYNC_SCHEDULE_ID, schedule)
            print(f"created schedule {config.SYNC_SCHEDULE_ID} every {a.minutes}m")
        except Exception as e:  # already exists -> update in place
            if "already" not in str(e).lower():
                raise
            handle = client.get_schedule_handle(config.SYNC_SCHEDULE_ID)

            async def _update(_):
                return ScheduleUpdate(schedule=schedule)

            await handle.update(_update)
            print(f"updated schedule {config.SYNC_SCHEDULE_ID} every {a.minutes}m")
        return

    if not a.member:
        p.error(f"{a.command} needs a scvUserId")
    handle = client.get_workflow_handle(config.member_workflow_id(a.member))
    if a.command == "summary":
        print(_dump(await handle.query(MemberWorkflow.summary)))
    elif a.command == "timeline":
        print(_dump([dataclasses.asdict(t) for t in await handle.query(MemberWorkflow.timeline)]))
    elif a.command == "delete":
        await handle.signal(MemberWorkflow.member_deleted)
        print("signalled member_deleted")
    elif a.command == "ticket":
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        await ingest.send_ticket(
            client,
            a.member,
            TicketPurchased(
                event_id=f"demo-{uuid.uuid4().hex[:12]}",
                product_id="demo-product",
                product_name="Crystal Palace v Demo FC",
                transaction_date=now,
                transaction_value=35.0,
                has_attended=False,
            ),
        )
        print("pushed synthetic ticket")
    elif a.command == "retail":
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        await ingest.send_retail(
            client,
            a.member,
            RetailOrderPlaced(
                event_id=f"demo-{uuid.uuid4().hex[:12]}",
                product_id="SHOP-HOME-KIT",
                product_name="Home Shirt 26/27",
                transaction_date=now,
                transaction_value=65.0,
                transaction_quantity=1,
                category="Kit",
            ),
        )
        print("pushed synthetic retail order")


if __name__ == "__main__":
    asyncio.run(main())
