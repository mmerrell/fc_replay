import asyncio
import logging

from temporalio.client import Client
from temporalio.common import VersioningBehavior, WorkerDeploymentVersion
from temporalio.worker import Worker, WorkerDeploymentConfig

from member_replay import config
from member_replay.activities import fetch_member_activity, list_member_ids
from member_replay.workflows import MemberSyncWorkflow, MemberWorkflow


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    client = await Client.connect(config.TEMPORAL_ADDRESS, namespace=config.TEMPORAL_NAMESPACE)
    worker = Worker(
        client,
        task_queue=config.TASK_QUEUE,
        workflows=[MemberWorkflow, MemberSyncWorkflow],
        activities=[list_member_ids, fetch_member_activity],
        deployment_config=WorkerDeploymentConfig(
            version=WorkerDeploymentVersion(
                deployment_name=config.DEPLOYMENT_NAME,
                build_id=config.BUILD_ID,
            ),
            use_worker_versioning=True,
            default_versioning_behavior=VersioningBehavior.PINNED,
        ),
    )
    logging.info("worker up: %s build %s on %s", config.DEPLOYMENT_NAME, config.BUILD_ID, config.TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
