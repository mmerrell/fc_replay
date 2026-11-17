"""Payloads and the pure state logic for a Member. No Temporal imports: this module is unit-testable on its own
and deterministic, so it is safe to call from workflow code."""
from dataclasses import dataclass, field
from typing import Optional

MAX_TIMELINE = 200  # newest entries kept on the Member's timeline
MAX_SEEN = 5000     # dedupe ids kept (state rides through Continue-as-New; payload limit is 2 MB)


@dataclass
class TicketPurchased:
    event_id: str  # Cortex scvUserTicketId
    product_id: str
    product_name: str
    transaction_date: str
    transaction_value: float
    has_attended: bool = False
    updated_at: str = ""  # Cortex updatedAt; drives the sync watermark


@dataclass
class RetailOrderPlaced:
    event_id: str  # Cortex scvUserRetailId
    product_id: str
    product_name: str
    transaction_date: str
    transaction_value: float
    transaction_quantity: int = 1
    category: str = ""
    updated_at: str = ""


@dataclass
class MemberProfile:
    """The small slice of PII the Replay needs (deliberately not email, phone or birth date)."""
    first_name: str = ""
    last_name: str = ""
    city: str = ""
    country_code: str = ""
    favourite_player: str = ""
    favourite_player_source_id: str = ""  # Cortex linkedIds.sourceSystemId (e.g. an Opta player id)
    fingerprint: str = ""                 # hash of the fields above; lets sync skip unchanged profiles


@dataclass
class SyncMarks:
    """What a MemberWorkflow has already applied; sync uses it to fetch and send only what is new."""
    activity_watermark: Optional[str] = None
    profile_fingerprint: Optional[str] = None


@dataclass
class EventsBatch:
    """Used for backfill / sync: one Signal carries many records (Temporal advises few Signals per second)."""
    tickets: list[TicketPurchased] = field(default_factory=list)
    retails: list[RetailOrderPlaced] = field(default_factory=list)


@dataclass
class TimelineEntry:
    kind: str  # "ticket" | "retail"
    event_id: str
    date: str
    description: str
    value: float


@dataclass
class ReplaySummary:
    scv_user_id: str
    matches_attended: int
    tickets_purchased: int
    ticket_spend: float
    retail_orders: int
    retail_items: int
    retail_spend: float
    total_spend: float
    spend_by_category: dict[str, float]
    first_activity: Optional[str]
    last_activity: Optional[str]
    profile: Optional[MemberProfile] = None


@dataclass
class SyncParams:
    chunk_size: int = 25
    concurrency: int = 4


@dataclass
class SyncResult:
    members: int = 0
    tickets: int = 0
    retails: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class MemberState:
    """Everything MemberWorkflow knows about a Member. Carried across Continue-as-New."""
    scv_user_id: str
    tickets_purchased: int = 0
    matches_attended: int = 0
    ticket_spend: float = 0.0
    retail_orders: int = 0
    retail_items: int = 0
    retail_spend: float = 0.0
    spend_by_category: dict[str, float] = field(default_factory=dict)
    first_activity: Optional[str] = None
    last_activity: Optional[str] = None
    sync_watermark: Optional[str] = None  # max Cortex updatedAt applied; sync only fetches newer records
    profile: Optional[MemberProfile] = None
    timeline: list[TimelineEntry] = field(default_factory=list)
    seen_event_ids: list[str] = field(default_factory=list)      # "ticket:<id>" / "retail:<id>"
    attended_event_ids: list[str] = field(default_factory=list)  # tickets already counted as attended

    # --- mutation (idempotent: Signals are delivered at least once) ---
    def apply_ticket(self, e: TicketPurchased) -> bool:
        """Returns True if state changed. A re-sent ticket still counts if it newly flips to attended
        (tickets are bought days before the match, so attendance arrives later)."""
        self._advance(e.updated_at)
        key = f"ticket:{e.event_id}"
        changed = False
        if key not in self.seen_event_ids:
            self.seen_event_ids.append(key)
            self.tickets_purchased += 1
            self.ticket_spend += e.transaction_value
            self._touch(e.transaction_date)
            self._add_timeline("ticket", e.event_id, e.transaction_date, e.product_name, e.transaction_value)
            changed = True
        if e.has_attended and key not in self.attended_event_ids:
            self.attended_event_ids.append(key)
            self.matches_attended += 1
            changed = True
        self._trim()
        return changed

    def apply_retail(self, e: RetailOrderPlaced) -> bool:
        self._advance(e.updated_at)
        key = f"retail:{e.event_id}"
        if key in self.seen_event_ids:
            return False
        self.seen_event_ids.append(key)
        self.retail_orders += 1
        self.retail_items += e.transaction_quantity
        self.retail_spend += e.transaction_value
        cat = e.category or "Other"
        self.spend_by_category[cat] = self.spend_by_category.get(cat, 0.0) + e.transaction_value
        self._touch(e.transaction_date)
        self._add_timeline("retail", e.event_id, e.transaction_date, e.product_name, e.transaction_value)
        self._trim()
        return True

    def apply_profile(self, p: MemberProfile) -> bool:
        if self.profile is not None and self.profile.fingerprint == p.fingerprint:
            return False
        self.profile = p
        return True

    def sync_marks(self) -> SyncMarks:
        return SyncMarks(self.sync_watermark, self.profile.fingerprint if self.profile else None)

    def apply_batch(self, batch: EventsBatch) -> int:
        changed = sum(self.apply_ticket(t) for t in batch.tickets)
        changed += sum(self.apply_retail(r) for r in batch.retails)
        return changed

    # --- read ---
    def summary(self) -> ReplaySummary:
        return ReplaySummary(
            scv_user_id=self.scv_user_id,
            matches_attended=self.matches_attended,
            tickets_purchased=self.tickets_purchased,
            ticket_spend=round(self.ticket_spend, 2),
            retail_orders=self.retail_orders,
            retail_items=self.retail_items,
            retail_spend=round(self.retail_spend, 2),
            total_spend=round(self.ticket_spend + self.retail_spend, 2),
            spend_by_category={k: round(v, 2) for k, v in sorted(self.spend_by_category.items())},
            first_activity=self.first_activity,
            last_activity=self.last_activity,
            profile=self.profile,
        )

    def sorted_timeline(self) -> list[TimelineEntry]:
        return sorted(self.timeline, key=lambda t: (t.date, t.event_id))

    # --- internals ---
    def _advance(self, updated_at: str) -> None:
        if updated_at and (self.sync_watermark is None or updated_at > self.sync_watermark):
            self.sync_watermark = updated_at

    def _touch(self, date: str) -> None:
        if date:  # ISO-8601 strings compare correctly as text
            if self.first_activity is None or date < self.first_activity:
                self.first_activity = date
            if self.last_activity is None or date > self.last_activity:
                self.last_activity = date

    def _add_timeline(self, kind: str, event_id: str, date: str, description: str, value: float) -> None:
        self.timeline.append(TimelineEntry(kind, event_id, date, description, value))

    def _trim(self) -> None:
        if len(self.timeline) > MAX_TIMELINE:
            del self.timeline[: len(self.timeline) - MAX_TIMELINE]
        if len(self.seen_event_ids) > MAX_SEEN:
            del self.seen_event_ids[: len(self.seen_event_ids) - MAX_SEEN]
        if len(self.attended_event_ids) > MAX_SEEN:
            del self.attended_event_ids[: len(self.attended_event_ids) - MAX_SEEN]
