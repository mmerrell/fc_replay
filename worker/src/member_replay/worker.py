import asyncio
import logging

from temporalio.client import Client
from temporalio.common import VersioningBehavior, WorkerDeploymentVersion
from temporalio.worker import Worker, WorkerDeploymentConfig

from member_replay import config
from member_replay.activities import CortexActivities
from member_replay.cortex import CortexClient
from member_replay.workflows import MemberSyncWorkflow, MemberWorkflow


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    client = await Client.connect(config.TEMPORAL_ADDRESS, namespace=config.TEMPORAL_NAMESPACE)
    cortex = CortexClient(config.CORTEX_BASE_URL, config.CORTEX_CLIENT_ID, config.CORTEX_API_KEY)
    acts = CortexActivities(client, cortex)
    worker = Worker(
        client,
        task_queue=config.TASK_QUEUE,
        workflows=[MemberWorkflow, MemberSyncWorkflow],
        activities=[acts.list_member_ids, acts.sync_members],
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
