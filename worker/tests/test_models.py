from member_replay.models import (
    MAX_SEEN, EventsBatch, MemberState, RetailOrderPlaced, TicketPurchased,
)


def ticket(i="t1", value=30.0, attended=False, date="2026-09-01T12:00:00.000Z"):
    return TicketPurchased(i, "p1", "Crystal Palace v Fulham", date, value, attended)


def retail(i="r1", value=10.0, qty=2, cat="Food", date="2026-09-05T12:00:00.000Z"):
    return RetailOrderPlaced(i, "sku", "Pie", date, value, qty, cat)


def test_ticket_counts_once_and_is_idempotent():
    s = MemberState("u1")
    assert s.apply_ticket(ticket()) is True
    assert s.apply_ticket(ticket()) is False  # duplicate Signal delivery
    assert (s.tickets_purchased, s.ticket_spend, s.matches_attended) == (1, 30.0, 0)


def test_attendance_arriving_later_counts_once():
    s = MemberState("u1")
    s.apply_ticket(ticket(attended=False))
    assert s.apply_ticket(ticket(attended=True)) is True  # same ticket, newly attended
    assert s.apply_ticket(ticket(attended=True)) is False
    assert (s.tickets_purchased, s.matches_attended, s.ticket_spend) == (1, 1, 30.0)


def test_retail_aggregates_by_category_and_dedupes():
    s = MemberState("u1")
    s.apply_retail(retail("r1", 11.0, 2, "Food"))
    s.apply_retail(retail("r2", 65.0, 1, "Kit"))
    assert s.apply_retail(retail("r1", 11.0, 2, "Food")) is False
    sm = s.summary()
    assert (sm.retail_orders, sm.retail_items, sm.retail_spend) == (2, 3, 76.0)
    assert sm.spend_by_category == {"Food": 11.0, "Kit": 65.0}


def test_ticket_and_retail_ids_do_not_collide():
    s = MemberState("u1")
    s.apply_ticket(ticket("same"))
    assert s.apply_retail(retail("same")) is True


def test_batch_and_summary_and_activity_window():
    s = MemberState("u1")
    n = s.apply_batch(EventsBatch([ticket("t1", 28, True, "2026-08-20T00:00:00.000Z"), ticket("t2", 32, False, "2026-10-01T00:00:00.000Z")],
                                  [retail("r1", 5.5, 1, "Food", "2026-08-22T00:00:00.000Z")]))
    assert n == 3  # counts records that changed state: t1 (new + attended), t2 (new), r1
    sm = s.summary()
    assert (sm.matches_attended, sm.tickets_purchased, sm.total_spend) == (1, 2, 65.5)
    assert (sm.first_activity, sm.last_activity) == ("2026-08-20T00:00:00.000Z", "2026-10-01T00:00:00.000Z")
    assert [t.event_id for t in s.sorted_timeline()] == ["t1", "r1", "t2"]


def test_empty_member_summary():
    sm = MemberState("nobody").summary()
    assert (sm.matches_attended, sm.total_spend, sm.first_activity) == (0, 0.0, None)


def test_state_stays_bounded():
    s = MemberState("u1")
    for i in range(MAX_SEEN + 50):
        s.apply_retail(retail(f"r{i}", 1.0, 1, "Food"))
    assert len(s.seen_event_ids) == MAX_SEEN and len(s.timeline) <= 200


def test_watermark_advances_even_on_resent_records():
    s = MemberState("u1")
    s.apply_ticket(TicketPurchased("t1", "p", "x", "2026-09-01T00:00:00.000Z", 30.0, False, "2026-09-01T00:00:00.000Z"))
    assert s.sync_watermark == "2026-09-01T00:00:00.000Z"
    s.apply_ticket(TicketPurchased("t1", "p", "x", "2026-09-01T00:00:00.000Z", 30.0, True, "2026-09-10T00:00:00.000Z"))
    assert s.sync_watermark == "2026-09-10T00:00:00.000Z" and s.matches_attended == 1
    s.apply_retail(RetailOrderPlaced("r1", "s", "Pie", "2026-09-02T00:00:00.000Z", 5.0, 1, "Food", "2026-09-02T00:00:00.000Z"))
    assert s.sync_watermark == "2026-09-10T00:00:00.000Z"  # never goes backwards


def test_profile_applies_once_and_changes_replace():
    from member_replay.models import MemberProfile
    s = MemberState("u1")
    p1 = MemberProfile("Adrian", "Clarke", "Brighton", "GB", "Adam Sandoval", "3000", "fp1")
    assert s.apply_profile(p1) is True
    assert s.apply_profile(MemberProfile("Adrian", "Clarke", "Brighton", "GB", "Adam Sandoval", "3000", "fp1")) is False
    assert s.sync_marks().profile_fingerprint == "fp1"
    assert s.apply_profile(MemberProfile("Adrian", "Clarke", "Reading", "GB", "Adam Sandoval", "3000", "fp2")) is True
    assert s.summary().profile.city == "Reading"
