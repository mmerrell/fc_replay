"""Mock of the Cortex (cortextech.io) Fan Data Platform + public REST APIs. Stdlib only.

Routes (shapes taken from developer.cortextech.io; see README for what is inferred):
  GET  /v2/public/clients/{c}/events[/{id}]          events.cortextech.io
  GET  /v1/clients/{c}/players[/{id}|/slug/{slug}]   players.cortextech.io
  GET  /v1/clients/{c}/teams[/{id}]                  players.cortextech.io
  POST /**/clients/{c}/query                         Single Fan View (GraphQL)
  GET  /_mock/fans, /_mock/health                    helpers, not part of Cortex
"""
import base64
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import data as D

API_KEY = os.environ.get("API_KEY", "")  # if set, SFV + admin routes require X-API-Key


# ======================= minimal GraphQL =======================
TOK = re.compile(r'\s*(?:,|#[^\n]*)*\s*("(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?|[A-Za-z_]\w*|[{}()\[\]:!$=@])')


def tokenize(src):
    out, pos = [], 0
    while pos < len(src):
        m = TOK.match(src, pos)
        if not m:
            if src[pos:].strip(" \t\r\n,") == "":
                break
            raise ValueError(f"Syntax error near: {src[pos:pos+20]!r}")
        out.append(m.group(1))
        pos = m.end()
    return out


class Parser:
    def __init__(self, src, variables):
        self.t, self.i, self.vars = tokenize(src), 0, variables or {}

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, tok):
        if self.next() != tok:
            raise ValueError(f"Expected {tok}")

    def document(self):
        if self.peek() in ("query", "mutation"):
            if self.next() == "mutation":
                raise ValueError("Mutations are not supported")
            if self.peek() not in ("{", "("):
                self.next()  # operation name
            if self.peek() == "(":  # variable definitions: skip
                depth = 0
                while True:
                    tok = self.next()
                    depth += tok == "("
                    depth -= tok == ")"
                    if depth == 0:
                        break
        return self.selection_set()

    def selection_set(self):
        self.expect("{")
        fields = []
        while self.peek() != "}":
            fields.append(self.field())
        self.expect("}")
        return fields

    def field(self):
        name = self.next()
        alias = None
        if self.peek() == ":":
            self.next()
            alias, name = name, self.next()
        args = {}
        if self.peek() == "(":
            self.next()
            while self.peek() != ")":
                k = self.next()
                self.expect(":")
                args[k] = self.value()
            self.expect(")")
        sub = self.selection_set() if self.peek() == "{" else None
        return {"name": name, "alias": alias or name, "args": args, "sub": sub}

    def value(self):
        tok = self.next()
        if tok == "$":
            return self.vars.get(self.next())
        if tok == "[":
            items = []
            while self.peek() != "]":
                items.append(self.value())
            self.next()
            return items
        if tok.startswith('"'):
            return json.loads(tok)
        if re.fullmatch(r"-?\d+", tok):
            return int(tok)
        if re.fullmatch(r"-?\d+\.\d+", tok):
            return float(tok)
        return {"true": True, "false": False, "null": None}.get(tok, tok)


def project(obj, sub):
    if obj is None or sub is None:
        return obj
    if isinstance(obj, list):
        return [project(o, sub) for o in obj]
    out = {}
    for f in sub:
        if f["name"] == "__typename":
            out[f["alias"]] = "Object"
        else:
            out[f["alias"]] = project(obj.get(f["name"]), f["sub"])
    return out


def paginate(rows, args, user_key="scvUserId"):
    uid = args.get(user_key)
    if uid is None:
        raise ValueError(f"{user_key} is required")
    rows = [r for r in rows if r["scvUserId"] == uid]
    for key in reversed(args.get("sort") or ["-updatedAt"]):
        rows.sort(key=lambda r, k=key.lstrip("-"): (r.get(k) is None, r.get(k)), reverse=key.startswith("-"))
    size = int(args.get("size", 50))
    start = int(base64.b64decode(args["cursor"]).decode()) if args.get("cursor") else 0
    nxt = base64.b64encode(str(start + size).encode()).decode() if start + size < len(rows) else None
    return {"items": rows[start:start + size], "next": nxt}


def by_id(rows, key, val):
    return next((r for r in rows if r[key] == val), None)


def resolve(field):
    n, a = field["name"], field["args"]
    if n == "user":
        return by_id(D.USERS, "scvUserId", a.get("scvUserId"))
    if n == "retail":
        return by_id(D.RETAILS, "scvUserRetailId", a.get("scvUserRetailId"))
    if n == "ticket":
        return by_id(D.TICKETS, "scvUserTicketId", a.get("scvUserTicketId"))
    if n == "structuredEvent":
        return by_id(D.STRUCTURED, "scvUserStructuredEventId", a.get("scvUserStructuredEventId"))
    if n == "retails":
        return paginate(D.RETAILS, a)
    if n == "tickets":
        return paginate(D.TICKETS, a)
    if n == "structuredEvents":
        return paginate(D.STRUCTURED, a)
    raise ValueError(f"Cannot query field '{n}' on type 'Query'")


def run_graphql(body):
    try:
        ast = Parser(body.get("query", ""), body.get("variables")).document()
        data = {f["alias"]: project(resolve(f), f["sub"]) for f in ast}
        return {"data": data}
    except Exception as e:  # GraphQL returns 200 with an errors array
        return {"errors": [{"message": str(e)}], "data": None}


# ======================= REST filters =======================
def parse_dt(s):
    from datetime import datetime
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


STATUS_GROUPS = {"Fixture": {"PreMatch", "Postponed", "Fixture"}, "Result": {"FullTime", "Result", "Abandoned"},
                 "Live": {"FirstHalf", "HalfTime", "SecondHalf", "ExtraTime", "PenaltyShootout", "InPlay"}}


def filter_events(q):
    g = lambda k: q.get(k, [None])[0]
    out = []
    for e in D.FIXTURES:
        d = parse_dt(e["date"])
        tid = {e["homeTeam"]["id"], e["awayTeam"]["id"]}
        checks = [
            not g("startDate") or d >= parse_dt(g("startDate")),
            not g("endDate") or d < parse_dt(g("endDate")),
            not g("upcoming") or d >= parse_dt(g("upcoming")),
            not g("previous") or (d < parse_dt(g("previous")) and e["status"] != "Postponed"),
            not g("teamId") or g("teamId") in tid,
            not g("homeTeamId") or e["homeTeam"]["id"] == g("homeTeamId"),
            not g("awayTeamId") or e["awayTeam"]["id"] == g("awayTeamId"),
            not g("venueId") or e["venue"]["id"] == g("venueId"),
            not g("competitionId") or e["competition"]["id"] == g("competitionId"),
            not g("excludeCompetitionId") or e["competition"]["id"] != g("excludeCompetitionId"),
            not g("seasonId") or e["season"]["id"] == g("seasonId"),
            not g("status") or e["status"] == g("status"),
            not g("statusGroup") or e["status"] in STATUS_GROUPS.get(g("statusGroup"), set()),
            not g("teamNameSearch") or g("teamNameSearch").lower() in (e["homeTeam"]["name"] + e["awayTeam"]["name"]).lower(),
            not g("sport") or e["sport"].lower() == g("sport").lower(),
        ]
        if all(checks):
            out.append(e)
    return out


def filter_players(q):
    g = lambda k: q.get(k, [None])[0]
    out = []
    for p in D.PLAYERS:
        a = p["attributes"]
        if g("teamSlug") and a["team"]["slug"] != g("teamSlug"):
            continue
        if g("teamIds") and D.HOME["id"] not in g("teamIds").split(","):
            continue
        if g("positionSlug") and a["position"]["slug"] != g("positionSlug"):
            continue
        if g("positionIds") and not any(D.POSITION_IDS[a["position"]["slug"]] == i for i in g("positionIds").split(",")):
            continue
        if g("query") and g("query").lower() not in f"{p['forename']} {p['surname']}".lower():
            continue
        out.append(p)
    return out


# ======================= HTTP =======================
ROUTES = [
    (r"^/v2/public/clients/([^/]+)/events$", "events"),
    (r"^/v2/public/clients/([^/]+)/events/([^/]+)$", "event"),
    (r"^/v1/clients/([^/]+)/players$", "players"),
    (r"^/v1/clients/([^/]+)/players/slug/([^/]+)$", "player_slug"),
    (r"^/v1/clients/([^/]+)/players/([^/]+)$", "player"),
    (r"^/v1/clients/([^/]+)/teams$", "teams"),
    (r"^/v1/clients/([^/]+)/teams/([^/]+)$", "team"),
]


class H(BaseHTTPRequestHandler):
    server_version = "CortexMock/0.1"

    def send(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send(204, {})

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/_mock/health":
            return self.send(200, {"ok": True, "fans": len(D.USERS), "events": len(D.FIXTURES), "tickets": len(D.TICKETS),
                                   "retail": len(D.RETAILS), "structuredEvents": len(D.STRUCTURED)})
        if u.path == "/_mock/fans":
            active = {r["scvUserId"] for r in D.TICKETS + D.RETAILS + D.STRUCTURED}
            return self.send(200, {"data": [{**{k: f[k] for k in ("scvUserId", "fullName", "emailAddress")},
                                             "hasActivity": f["scvUserId"] in active} for f in D.USERS]})
        for pat, name in ROUTES:
            m = re.match(pat, u.path)
            if m:
                if m.group(1) != D.CLIENT_ID:
                    return self.send(404, {"error": f"Unknown client {m.group(1)}; this mock serves {D.CLIENT_ID}"})
                return self.send(*getattr(self, "r_" + name)(q, *m.groups()[1:]))
        self.send(404, {"error": "Not found", "path": u.path})

    def do_POST(self):
        u = urlparse(self.path)
        m = re.search(r"/clients/([^/]+)/query/?$", u.path)
        if not m:
            return self.send(404, {"error": "Not found", "path": u.path})
        if API_KEY and self.headers.get("X-API-Key") != API_KEY:
            return self.send(401, {"error": "Missing or invalid X-API-Key"})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self.send(400, {"error": "Body must be JSON: {\"query\": \"...\", \"variables\": {...}}"})
        self.send(200, run_graphql(body))

    # --- handlers return (status, body) ---
    def r_events(self, q):
        return 200, {"data": filter_events(q)}

    def r_event(self, q, eid):
        e = by_id(D.FIXTURES, "id", eid)
        return (200, {"data": e}) if e else (404, {"error": "Event not found"})

    def r_players(self, q):
        return 200, {"data": filter_players(q)}

    def r_player(self, q, pid):
        p = by_id(D.PLAYERS, "id", pid)
        return (200, {"data": p}) if p else (404, {"error": "Player not found"})

    def r_player_slug(self, q, slug):
        p = by_id(D.PLAYERS, "slug", slug)
        return (200, {"data": p}) if p else (404, {"error": "Player not found"})

    def r_teams(self, q):
        return 200, {"data": D.TEAMS}

    def r_team(self, q, tid):
        t = by_id(D.TEAMS, "id", tid)
        return (200, {"data": t}) if t else (404, {"error": "Team not found"})

    def log_message(self, fmt, *args):
        print("%s %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"Cortex mock on :{port}  client={D.CLIENT_ID} fans={len(D.USERS)} events={len(D.FIXTURES)} "
          f"tickets={len(D.TICKETS)} retail={len(D.RETAILS)} structured={len(D.STRUCTURED)}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
