#!/bin/sh
# Re-runnable. With Worker Versioning nothing is routed to a build until it is made current, and the dev
# server forgets everything on restart, so this runs on every `docker compose up`.
set -u
ADDR="${TEMPORAL_ADDRESS:-temporal:7233}"
DEPLOY="${TEMPORAL_DEPLOYMENT:-member-replay}"
BUILD="${BUILD_ID:-1.0}"
TQ="${TEMPORAL_TASK_QUEUE:-member-replay}"
EVERY="${SYNC_EVERY:-5m}"
T="temporal --address $ADDR"

echo "bootstrap: waiting for worker $DEPLOY/$BUILD to register (it must be polling before it can be made current)"
i=0
until $T worker deployment set-current-version --deployment-name "$DEPLOY" --build-id "$BUILD" --yes; do
  i=$((i + 1))
  if [ "$i" -ge 45 ]; then echo "bootstrap: worker version never appeared; giving up"; exit 1; fi
  sleep 2
done
echo "bootstrap: $DEPLOY/$BUILD is current"

if $T schedule describe --schedule-id member-sync >/dev/null 2>&1; then
  echo "bootstrap: schedule member-sync already exists"
else
  $T schedule create --schedule-id member-sync --interval "$EVERY" --overlap-policy Skip \
    --workflow-id member-sync-scheduled --task-queue "$TQ" --type MemberSyncWorkflow || exit 1
  echo "bootstrap: created schedule member-sync every $EVERY"
fi

$T schedule trigger --schedule-id member-sync && echo "bootstrap: first sync triggered"
echo "bootstrap: done. Web UI: http://localhost:8233   Mock API: http://localhost:8080/_mock/health"
