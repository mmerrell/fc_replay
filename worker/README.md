# worker

Temporal workflows for the "Your Replay" prototype. Python, Worker Versioning with PINNED, build `1.0`.

## What's here
- `MemberWorkflow`: one long-running workflow per Member (id `member-<scvUserId>`). Signals `ticket_purchased`,
  `retail_order_placed`, `events_batch` (backfill), `member_deleted`. Queries `summary` (Replay aggregates) and
  `timeline`. Dedupes on Cortex record ids (Signals are at-least-once). Continues-as-new when the history grows
  or a newer build is available (upgrade-on-Continue-as-New, see below).
- `MemberSyncWorkflow`: reconciliation. Lists Members, pulls each one's tickets/retail from Cortex in chunks,
  and signal-with-starts their `MemberWorkflow` with one batched Signal. Run it from a Schedule.
- `models.py` holds all the state logic as plain Python (no Temporal imports), so it is unit-tested directly.
- `cortex.py` is a stdlib GraphQL client for Cortex SFV (works against `../cortex-mock`).
- `starter.py` is a demo CLI (below).

## Run it
    # 1. Temporal dev server (Temporal CLI >= 1.4.1; Worker Versioning needs server >= 1.29.1)
    temporal server start-dev
    # 2. the mock Cortex API
    (cd ../cortex-mock && docker compose up --build)
    # 3. worker (Docker) -- or locally: pip install -e '.[test]' && python -m member_replay.worker
    docker compose up --build
    # 4. make build 1.0 current, otherwise it receives no new workflows
    temporal worker deployment set-current-version --deployment-name member-replay --build-id 1.0

    python -m member_replay.starter sync                 # one sync now
    python -m member_replay.starter schedule --minutes 5 # recurring sync
    python -m member_replay.starter summary <scvUserId>  # a Member's Replay numbers (ids: curl localhost:8080/_mock/fans)
    python -m member_replay.starter ticket  <scvUserId>  # push a synthetic purchase (live-demo 'push' path)

## Tests
    pip install -e '.[test]' && pytest
`test_models.py` and `test_cortex.py` need no Temporal. `test_workflows.py` starts a local dev server.

## Versioning
Deployment `member-replay`, build `BUILD_ID` (default `1.0`). Runs are pinned to the build they start on. On
Continue-as-New, if `is_target_worker_deployment_version_changed()` is true the next run starts with
`AUTO_UPGRADE` and re-pins to the new build. Idle Members wake hourly to notice. This API is Public Preview and
newer than Worker Versioning; on an older SDK the workflow skips the upgrade and stays pinned.
To ship 1.1: build the image with `BUILD_ID=1.1`, start it, then `set-current-version --build-id 1.1`.
