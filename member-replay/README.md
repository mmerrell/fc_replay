# member-replay (stub)

Temporal workflows for the "Your Palace Replay" prototype. Everything in `workflows.py`/`activities.py` is a TODO; `worker.py` is wired.

## Versioning (PINNED, build 1.0)
Worker registers as deployment `member-replay`, build `1.0` (`BUILD_ID` env / compose build arg). A version only receives
new workflows once it is made current:

    temporal worker deployment set-current-version --deployment-name member-replay --build-id 1.0

Pinned runs stay on the build they started on, so a Member run on 1.0 never moves by itself. Plan: on Continue-as-New,
check `workflow.info().is_target_worker_deployment_version_changed()` and pass
`initial_versioning_behavior=ContinueAsNewVersioningBehavior.AUTO_UPGRADE` (Public Preview; confirm SDK version).

## Run
    docker compose up --build   # worker only; needs a Temporal server and the cortex-mock
