"""Payload shapes. Event ids come from Cortex (scvUserTicketId / scvUserRetailId) and double as dedupe keys:
Signals are delivered at least once, so MemberWorkflow must ignore ids it has already seen."""
from dataclasses import dataclass, field


@dataclass
class TicketPurchased:
    event_id: str  # scvUserTicketId
    product_id: str
    product_name: str
    transaction_date: str
    transaction_value: float
    has_attended: bool = False


@dataclass
class RetailOrderPlaced:
    event_id: str  # scvUserRetailId
    product_id: str
    product_name: str
    transaction_date: str
    transaction_value: float
    transaction_quantity: int = 1


@dataclass
class MemberState:
    """Carried across Continue-as-New. Keep it small (payload limit is 2 MB)."""
    scv_user_id: str
    # TODO: running aggregates for the Replay, bounded recent timeline, seen event ids, sync watermark
    seen_event_ids: list[str] = field(default_factory=list)
