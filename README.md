# fc_replay

Prototype for a "Your Replay" experience built on Temporal.

- `worker/`: Temporal workflows and the versioned worker (PINNED, build 1.0)
- `cortex-mock/`: stdlib-only mock of the Cortex Fan Data Platform API with fake data

## Run everything
    docker compose up --build

Starts Temporal (dev server), the Cortex mock, the worker, and a one-shot `bootstrap` job that makes build `BUILD_ID`
(see `.env`) current, creates the `member-sync` Schedule (every 5m) and triggers the first sync.

- Temporal Web UI: http://localhost:8233 (workflows `member-<scvUserId>`, the `member-sync` schedule)
- Mock Cortex API: http://localhost:8080/_mock/health, `/_mock/fans`
- Query a Member: `docker compose run --rm --no-deps --entrypoint python worker -m member_replay.starter summary <scvUserId>`

The Temporal dev server is in-memory: restarting it wipes workflows and the schedule. `docker compose up` re-runs
bootstrap and the first sync repopulates every Member from Cortex.
