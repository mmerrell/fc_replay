import os

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "member-replay")

# Worker Deployment Version = deployment name + build id. Bump BUILD_ID for every deploy.
DEPLOYMENT_NAME = os.getenv("TEMPORAL_DEPLOYMENT", "member-replay")
BUILD_ID = os.getenv("BUILD_ID", "1.0")

# Where the Cortex API (or the mock) lives.
CORTEX_BASE_URL = os.getenv("CORTEX_BASE_URL", "http://localhost:8080")
CORTEX_CLIENT_ID = os.getenv("CORTEX_CLIENT_ID", "DEMO")
CORTEX_API_KEY = os.getenv("CORTEX_API_KEY", "")


def member_workflow_id(scv_user_id: str) -> str:
    """One workflow per Member, keyed on the Cortex scvUserId."""
    return f"member-{scv_user_id}"
