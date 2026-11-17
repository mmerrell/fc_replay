#!/bin/sh
# Simulates the 'push' path: three Members buy things, straight into their MemberWorkflows.
# Run from the repo root after `docker compose build worker` and once the first sync has populated Members.
run() { docker compose run --rm --no-deps --entrypoint python worker -m member_replay.starter "$@" 2>/dev/null; }
keys='"first_name"|"city"|"favourite_player"|"tickets_purchased"|"matches_attended"|"retail_orders"|"retail_items"|"total_spend"'
show() { run summary "$1" | grep -E "$keys" | tr -d ' \n'; echo; }

ADRIAN=c880d715046e3f89775c0f656636b680   # Adrian Clarke, Brighton: active (6 tickets, 8 retail orders)
PRIYA=3c3c511dcffd727bd9dbdb6b2520cd95    # Priya Park, Brighton: active (3 tickets, 7 retail orders)
DEV=c243d608f9b4a4f67640c466c4ac9b71      # Dev Nolan, Redhill: inactive until now

echo "--- BEFORE"; for u in $ADRIAN $PRIYA $DEV; do show $u; done

run ticket $ADRIAN; run retail $ADRIAN      # +1 ticket (35.00), +1 home shirt (65.00)
run retail $PRIYA;  run retail $PRIYA       # two shirt orders (2 x 65.00)
run ticket $DEV;    run retail $DEV         # first-ever activity for a Member with none

echo "--- AFTER"; for u in $ADRIAN $PRIYA $DEV; do show $u; done
