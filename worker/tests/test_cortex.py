"""Runs the real CortexClient against the real cortex-mock (started as a subprocess on a free port)."""
import contextlib
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from member_replay.cortex import CortexClient

MOCK = Path(__file__).resolve().parents[2] / "cortex-mock" / "server.py"


@contextlib.contextmanager
def running_mock():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "PORT": str(port), "MOCK_NOW": "2026-11-17T12:00:00+00:00"}
    proc = subprocess.Popen([sys.executable, str(MOCK)], cwd=MOCK.parent, env=env, stdout=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/_mock/health", timeout=1).read()
                break
            except Exception:
                time.sleep(0.2)
        yield CortexClient(f"http://127.0.0.1:{port}", "DEMO")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_lists_members_and_fetches_activity():
    with running_mock() as cortex:
        ids = cortex.list_member_ids()
        assert len(ids) == 100
        counts = [(len(a.tickets), len(a.retails)) for a in map(cortex.fetch_activity, ids[:30])]
        assert any(t > 0 for t, _ in counts)
        act = next(cortex.fetch_activity(i) for i in ids if cortex.fetch_activity(i).tickets)
        t = act.tickets[0]
        assert t.event_id and t.product_name.startswith("Crystal Palace v") and t.transaction_value > 0


def test_inactive_member_has_no_activity():
    with running_mock() as cortex:
        import json
        fans = json.loads(urllib.request.urlopen(cortex.base_url + "/_mock/fans").read())["data"]
        inactive = [f["scvUserId"] for f in fans if not f["hasActivity"]]
        assert len(inactive) == 15
        act = cortex.fetch_activity(inactive[0])
        assert act.tickets == [] and act.retails == []


def test_paging_covers_every_record():
    # The busiest mock member has > 50 structured events but tickets/retails are small; force paging via module constant.
    import member_replay.cortex as c
    with running_mock() as cortex:
        ids = cortex.list_member_ids()
        best = max(ids, key=lambda i: len(cortex.fetch_activity(i).tickets))
        full = cortex.fetch_activity(best)
        c_tickets_q = c.TICKETS_Q.replace("size:%d" % c.PAGE_SIZE, "size:2")
        c_retails_q = c.RETAILS_Q.replace("size:%d" % c.PAGE_SIZE, "size:2")
        orig = (c.TICKETS_Q, c.RETAILS_Q)
        try:
            c.TICKETS_Q, c.RETAILS_Q = c_tickets_q, c_retails_q
            paged = cortex.fetch_activity(best)
        finally:
            c.TICKETS_Q, c.RETAILS_Q = orig
        assert len(full.tickets) > 2
        assert sorted(t.event_id for t in paged.tickets) == sorted(t.event_id for t in full.tickets)
        assert sorted(r.event_id for r in paged.retails) == sorted(r.event_id for r in full.retails)


def test_since_returns_only_newer_records():
    with running_mock() as cortex:
        ids = cortex.list_member_ids()
        uid = max(ids, key=lambda i: len(cortex.fetch_activity(i).tickets))
        full = cortex.fetch_activity(uid)
        stamps = sorted({x.updated_at for x in full.tickets + full.retails})
        assert len(stamps) > 2
        assert cortex.fetch_activity(uid, since=stamps[-1]) .tickets == []  # nothing newer than the newest
        newer = cortex.fetch_activity(uid, since=stamps[1])
        got = {x.updated_at for x in newer.tickets + newer.retails}
        assert got and min(got) > stamps[1] and max(got) == stamps[-1]
        everything = cortex.fetch_activity(uid, since=None)
        assert len(everything.tickets) == len(full.tickets)


def test_profile_has_name_city_and_favourite_player():
    with running_mock() as cortex:
        ids = cortex.list_member_ids()
        profiles = [cortex.fetch_profile(i) for i in ids[:30]]
        assert all(p.first_name and p.last_name and p.city and p.country_code == "GB" for p in profiles)
        assert sum(1 for p in profiles if p.favourite_player) >= 20  # ~90% pick one
        p = next(p for p in profiles if p.favourite_player)
        assert p.favourite_player_source_id.isdigit() and p.fingerprint
        assert cortex.fetch_profile(ids[0]).fingerprint == profiles[0].fingerprint  # stable
