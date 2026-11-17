"""Tiny stdlib client for the Cortex Single Fan View GraphQL endpoint (works against cortex-mock).
Blocking; activities call it via asyncio.to_thread. Field names marked INFERRED in cortex-mock/data.py
(favourite-player read auth, member listing) may not match on the real API; check against Cortex's schema."""
import hashlib
import json
import urllib.request
from dataclasses import dataclass, field

from member_replay.models import MemberProfile, RetailOrderPlaced, TicketPurchased

PAGE_SIZE = 50

TICKETS_Q = """query($u:String!,$c:String){ tickets(scvUserId:$u,size:%d,cursor:$c){
  items{ scvUserTicketId productId productName transactionDate transactionValue hasAttended updatedAt } next } }""" % PAGE_SIZE
RETAILS_Q = """query($u:String!,$c:String){ retails(scvUserId:$u,size:%d,cursor:$c){
  items{ scvUserRetailId productId productDescription productCategory transactionDate transactionValue transactionQuantity isRefunded updatedAt } next } }""" % PAGE_SIZE


USER_Q = """query($u:ID!){ user(scvUserId:$u){ firstName lastName fullName postcodeTown countryCode } }"""


@dataclass
class MemberActivity:
    tickets: list[TicketPurchased] = field(default_factory=list)
    retails: list[RetailOrderPlaced] = field(default_factory=list)


class CortexClient:
    def __init__(self, base_url: str, client_id: str, api_key: str = "", timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None) -> dict:
        headers = {"Content-Type": "application/json", **(headers or {})}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    def _query(self, query: str, variables: dict) -> dict:
        out = self._request("POST", f"/clients/{self.client_id}/query", {"query": query, "variables": variables})
        if out.get("errors"):
            raise RuntimeError(f"Cortex GraphQL error: {out['errors']}")
        return out["data"]

    def _pages(self, query: str, root: str, scv_user_id: str, since: str | None = None):
        """Pages are sorted -updatedAt (the default), so stop as soon as a record is not newer than `since`."""
        cursor = None
        while True:
            page = self._query(query, {"u": scv_user_id, "c": cursor})[root]
            for item in page["items"]:
                if since and item["updatedAt"] <= since:
                    return
                yield item
            cursor = page["next"]
            if not cursor:
                return

    def fetch_profile(self, scv_user_id: str) -> MemberProfile:
        """Name + home city from the SFV `user` query; favourite player from the Preferences Centre.
        MOCK: the preferences read takes the fan's JWT in real Cortex; the mock accepts Bearer <scvUserId>."""
        user = self._query(USER_Q, {"u": scv_user_id})["user"] or {}
        pref = self._request("GET", f"/v1/clients/{self.client_id}/client-preferences/favouritePlayer",
                             headers={"Authorization": f"Bearer {scv_user_id}"})["data"]
        picked = set(pref.get("selectedOptionIds") or [])
        option = next((o for o in pref.get("options", []) if o["id"] in picked), None)
        linked = (option or {}).get("linkedIds") or [{}]
        fields = {
            "first_name": user.get("firstName") or (user.get("fullName") or "").split(" ")[0],
            "last_name": user.get("lastName") or "",
            "city": user.get("postcodeTown") or "",
            "country_code": user.get("countryCode") or "",
            "favourite_player": (option or {}).get("value", ""),
            "favourite_player_source_id": linked[0].get("sourceSystemId", ""),
        }
        fp = hashlib.md5(json.dumps(fields, sort_keys=True).encode()).hexdigest()
        return MemberProfile(**fields, fingerprint=fp)

    def list_member_ids(self) -> list[str]:
        """MOCK ONLY: Cortex's documented query API is per-user, so the real source of Member ids is TBD
        (exports?). The mock exposes /_mock/fans."""
        return [f["scvUserId"] for f in self._request("GET", "/_mock/fans")["data"]]

    def fetch_activity(self, scv_user_id: str, since: str | None = None) -> MemberActivity:
        """All of a Member's tickets/retail, or only those updated after `since` (an ISO updatedAt)."""
        act = MemberActivity()
        for t in self._pages(TICKETS_Q, "tickets", scv_user_id, since):
            act.tickets.append(TicketPurchased(
                event_id=t["scvUserTicketId"], product_id=t["productId"], product_name=t.get("productName") or "",
                transaction_date=t["transactionDate"], transaction_value=float(t["transactionValue"] or 0),
                has_attended=bool(t.get("hasAttended")), updated_at=t["updatedAt"]))
        for r in self._pages(RETAILS_Q, "retails", scv_user_id, since):
            if r.get("isRefunded"):
                continue
            act.retails.append(RetailOrderPlaced(
                event_id=r["scvUserRetailId"], product_id=r["productId"], product_name=r.get("productDescription") or "",
                transaction_date=r["transactionDate"], transaction_value=float(r["transactionValue"] or 0),
                transaction_quantity=int(r.get("transactionQuantity") or 1), category=r.get("productCategory") or "", updated_at=r["updatedAt"]))
        return act
