"""Deterministic fake data for the Cortex mock. Everything here is invented.

Shapes follow developer.cortextech.io where documented (events, players/teams,
Single Fan View tickets/retail/structuredEvents/user). Fields marked INFERRED
are plausible guesses, not taken from the docs.
"""
import hashlib
import os
import random
from datetime import datetime, timedelta, timezone

CLIENT_ID = os.environ.get("CLIENT_ID", "DEMO")
SEED = int(os.environ.get("SEED", "42"))
NUM_FANS = int(os.environ.get("NUM_FANS", "100"))
INACTIVE_FANS = min(int(os.environ.get("INACTIVE_FANS", "15")), NUM_FANS)  # fans with a profile but zero records
NOW = datetime.fromisoformat(os.environ["MOCK_NOW"]) if os.environ.get("MOCK_NOW") else datetime.now(timezone.utc)
if NOW.tzinfo is None:
    NOW = NOW.replace(tzinfo=timezone.utc)

rnd = random.Random(SEED)


def oid(label):
    return hashlib.md5(f"{SEED}:{label}".encode()).hexdigest()[:24]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ---------- reference data ----------
SPORT = "FOOTBALL"
SEASON = {"id": oid("season"), "linkedIds": None, "clientId": CLIENT_ID, "name": "2026/27",
          "startDate": "2026-08-01T00:00:00.000Z", "endDate": "2027-05-31T23:59:59.999Z",
          "sport": SPORT, "version": 0}
VENUE = {"id": oid("venue"), "linkedIds": None, "clientId": CLIENT_ID, "name": "Selhurst Park",
         "address": "Whitehorse Lane", "city": "London", "postcode": "SE25 6PU", "country": "England",
         "sports": [SPORT], "version": 0}
EVENT_TYPE = {"id": oid("etype"), "clientId": "GLOBAL", "name": "Regular", "version": 0,
              "created": None, "lastEdited": None}
BROADCASTERS = [{"id": oid("bc-sky"), "linkedIds": None, "clientId": CLIENT_ID, "name": "Sky Sports (fake)",
                 "logoUrl": None, "countries": [], "isGlobal": False, "version": 0}]
COMPETITIONS = {
    name: {"id": oid("comp-" + name), "linkedIds": None, "clientId": CLIENT_ID, "name": name,
           "logoUrl": None, "squadType": "FirstTeam", "sport": SPORT, "version": 0}
    for name in ("Premier League", "FA Cup", "League Cup")
}
_stamp = {"date": "2026-06-01T09:00:00.000Z", "name": "Mock Admin", "authId": 1}


def mk_team(name, abbr):
    return {"id": oid("team-" + name), "linkedIds": None, "clientId": CLIENT_ID, "name": name,
            "crestUrl": None, "sport": SPORT, "abbreviation": abbr, "version": 0,
            "created": _stamp, "lastEdited": _stamp}


HOME = mk_team("Crystal Palace", "CRY")
# Real club names are fine as fixture opponents; every result/score below is invented.
OPP_NAMES = [("Arsenal", "ARS"), ("Aston Villa", "AVL"), ("Bournemouth", "BOU"), ("Brentford", "BRE"),
             ("Brighton", "BHA"), ("Chelsea", "CHE"), ("Everton", "EVE"), ("Fulham", "FUL"),
             ("Leeds", "LEE"), ("Liverpool", "LIV"), ("Man City", "MCI"), ("Man United", "MUN"),
             ("Newcastle", "NEW"), ("Nottm Forest", "NFO"), ("Sunderland", "SUN"), ("Spurs", "TOT"),
             ("West Ham", "WHU"), ("Wolves", "WOL"), ("Burnley", "BUR")]
OPPONENTS = [mk_team(n, a) for n, a in OPP_NAMES]
TEAMS = [HOME] + OPPONENTS

# ---------- players (invented squad) ----------
POSITIONS = {"GK": "Goalkeeper", "DF": "Defender", "MF": "Midfielder", "FW": "Forward"}
_FN = ["Jamie", "Luca", "Theo", "Marcus", "Dani", "Ollie", "Kofi", "Remy", "Sol", "Ibrahim", "Jonas",
       "Ethan", "Caleb", "Nico", "Adam", "Felix", "Idris", "Mateo", "Rory", "Tomas", "Yusuf", "Declan"]
_LN = ["Hartley", "Okafor", "Brennan", "Vidal", "Marsh", "Adeyemi", "Kowalski", "Lindqvist", "Bellamy",
       "Osei", "Duarte", "Fairweather", "Nakamura", "Rowe", "Sandoval", "Whitlock", "Mbeki", "Calloway",
       "Pryce", "Teixeira", "Holloway", "Ndiaye"]
PLAYERS = []
_layout = ["GK"] * 2 + ["DF"] * 7 + ["MF"] * 7 + ["FW"] * 6
for i, pos in enumerate(_layout):
    fn, ln = _FN[i % len(_FN)], _LN[i % len(_LN)]
    slug = f"{fn}-{ln}".lower()
    PLAYERS.append({
        "id": oid("player-" + slug), "forename": fn, "surname": ln, "headshot": None, "slug": slug,
        "language": "en", "linkedIds": [], "accolades": [], "merchandise": [], "socials": [], "sponsors": [],
        "attributes": {
            "team": {"name": HOME["name"], "slug": "crystal-palace"},
            "position": {"name": POSITIONS[pos], "slug": POSITIONS[pos].lower()},
            "squadNumber": i + 1, "nationality": rnd.choice(["England", "Ghana", "Poland", "Senegal", "Brazil", "Japan"]),
            "dateOfBirth": f"{rnd.randint(1993, 2007)}-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}",
        },
    })
POSITION_IDS = {v.lower(): oid("pos-" + v) for v in POSITIONS.values()}

# ---------- fixtures ----------
EVENTS = []
_kick = datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc)
_i = 0
_order = OPPONENTS[:]
rnd.shuffle(_order)
for rnd_no, opp in enumerate(_order, start=1):
    for leg in (0, 1):
        is_home = (rnd_no % 2 == 0) == (leg == 0)
        date = _kick + timedelta(days=int(_i * 7.5))
        if date > datetime(2027, 5, 23, tzinfo=timezone.utc):
            date = datetime(2027, 5, 23, 15, 0, tzinfo=timezone.utc)
        _i += 1
        EVENTS.append((date, is_home, opp, "Premier League", str(len(EVENTS) + 1)))
# a few cup ties
for date, opp, comp, home in [(datetime(2026, 9, 23, 19, 45, tzinfo=timezone.utc), OPPONENTS[3], "League Cup", True),
                              (datetime(2026, 11, 4, 19, 45, tzinfo=timezone.utc), OPPONENTS[8], "League Cup", False),
                              (datetime(2027, 1, 10, 15, 0, tzinfo=timezone.utc), OPPONENTS[14], "FA Cup", True)]:
    EVENTS.append((date, home, opp, comp, "Cup"))
EVENTS.sort(key=lambda e: e[0])
FIXTURES = []
for date, is_home, opp, comp, rd in EVENTS:
    past = date < NOW
    h, a = (HOME, opp) if is_home else (opp, HOME)
    hs, as_ = (rnd.choices([0, 1, 2, 3, 4], [2, 4, 3, 2, 1])[0], rnd.choices([0, 1, 2, 3], [3, 4, 2, 1])[0]) if past else (0, 0)
    FIXTURES.append({
        "id": oid(f"event-{iso(date)}-{opp['name']}"), "linkedIds": None, "clientId": CLIENT_ID, "sport": SPORT,
        "homeTeam": h, "homeTeamScore": hs, "awayTeam": a, "awayTeamScore": as_,
        "venue": VENUE if is_home else {**VENUE, "id": oid("venue-" + opp["name"]), "name": f"{opp['name']} Stadium"},
        "competition": COMPETITIONS[comp], "broadcasters": BROADCASTERS if rnd.random() < 0.25 else [],
        "season": SEASON, "eventType": EVENT_TYPE, "round": rd, "date": iso(date),
        "status": "FullTime" if past else "PreMatch",
    })
HOME_PAST = [e for e in FIXTURES if e["homeTeam"]["id"] == HOME["id"] and e["status"] == "FullTime"]

# ---------- fans + SFV records ----------
_FIRST = ["Adrian", "Priya", "Tom", "Sade", "Liam", "Maya", "Josh", "Chloe", "Dev", "Hannah", "Ravi", "Beth",
          "Callum", "Zainab", "Pete", "Ines", "Dan", "Amara", "Greg", "Nell", "Omar", "Kate", "Sean", "Lola", "Fred"]
_LAST = ["Clarke", "Shah", "Whitfield", "Bakare", "Doyle", "Ortiz", "Nolan", "Park", "Mehta", "Gray", "Iyer",
         "Cole", "Reid", "Hussain", "Lowe", "Costa", "Barry", "Eze", "Mills", "Frost", "Rahman", "Dunn", "Ward",
         "Okoye", "Banks"]
POSTCODES = [("SE25 6PU", "Croydon", "SE", "London", 1.2), ("CR0 1AA", "Croydon", "CR", "London", 2.0),
             ("BR3 4AA", "Beckenham", "BR", "London", 4.5), ("SW16 1AA", "Streatham", "SW", "London", 5.0),
             ("SM1 1AA", "Sutton", "SM", "London", 7.5), ("RH1 1AA", "Redhill", "RH", "South East", 17.0),
             ("BN1 1AA", "Brighton", "BN", "South East", 43.0), ("RG1 1AA", "Reading", "RG", "South East", 52.0),
             ("M1 1AA", "Manchester", "M", "North West", 200.0), ("EH1 1AA", "Edinburgh", "EH", "Scotland", 330.0)]
STANDS = ["Holmesdale Road", "Main Stand", "Arthur Wait", "Whitehorse Lane"]
RETAIL = [("SHOP-HOME-KIT", "Home Shirt 26/27", "Kit", 65.0), ("SHOP-SCARF", "Matchday Scarf", "Accessories", 18.0),
          ("SHOP-BEANIE", "Eagles Beanie", "Accessories", 15.0), ("FOOD-PIE", "Matchday Pie", "Food", 5.5),
          ("FOOD-PINT", "Pint", "Drink", 6.2), ("SHOP-PROG", "Matchday Programme", "Programme", 4.0)]
APP_EVENTS = [("app", "open", "home"), ("app", "view", "match_centre"), ("app", "view", "player_profile"),
              ("app", "tap", "buy_tickets"), ("video", "play", "highlights"), ("video", "play", "press_conference"),
              ("poll", "vote", "motm"), ("app", "scan", "ticket_entry")]

USERS, TICKETS, RETAILS, STRUCTURED = [], [], [], []
FAVOURITE = {}  # scvUserId -> favourite-player option id (or None)
INACTIVE = set(rnd.sample(range(NUM_FANS), INACTIVE_FANS))


def _row_ids(prefix, n):
    return oid(f"{prefix}-{n}")


for f in range(NUM_FANS):
    first = _FIRST[f % len(_FIRST)]
    last = _LAST[(f * 7 + f // len(_FIRST)) % len(_LAST)]
    name = f"{first} {last}"
    email = f"{name.lower().replace(' ', '.')}@example.test"
    uid = hashlib.md5(email.encode()).hexdigest()
    pc, town, area, region, dist = rnd.choice(POSTCODES)
    born = NOW.date().replace(year=NOW.year - rnd.randint(18, 78), month=rnd.randint(1, 12), day=rnd.randint(1, 28))
    joined = NOW - timedelta(days=rnd.randint(200, 2500))
    keen = rnd.random()  # 0..1 = how often this fan goes
    USERS.append({
        "scvUserId": uid, "scvUserIdType": "MD5_CLIENT_EMAIL", "fullName": name, "emailAddress": email,
        "postcode": pc, "postcodeTown": town, "postcodeArea": area, "postcodeRegion": region,
        "firstName": first, "lastName": last, "title": None, "gender": None,
        "mobileNumber": f"+44 7700 900{rnd.randint(0, 999):03d}",  # Ofcom's reserved drama range: not real numbers
        "birthDate": born.isoformat() + "T00:00:00.000Z", "age": NOW.year - born.year,
        "countryCode": "GB", "countryName": "United Kingdom", "distanceToClub": dist, "metadata": {},
        "createdAt": iso(joined), "updatedAt": iso(NOW - timedelta(days=rnd.randint(0, 30))),
    })
    FAVOURITE[uid] = oid("opt-" + rnd.choice(PLAYERS)["id"]) if rnd.random() < 0.9 else None
    if f in INACTIVE:
        continue  # profile only: no tickets, retail or structured events
    for ev in HOME_PAST:
        if rnd.random() < 0.25 + 0.7 * keen:
            tdate = datetime.fromisoformat(ev["date"].replace("Z", "+00:00")) - timedelta(days=rnd.randint(3, 40))
            attended = rnd.random() < 0.93
            opp = ev["awayTeam"]["name"]
            tid = _row_ids("ticket", len(TICKETS))
            stand = rnd.choice(STANDS)
            TICKETS.append({
                "scvUserTicketId": tid, "scvUserId": uid, "productId": ev["id"],
                "productName": f"Crystal Palace v {opp}", "productStartDate": ev["date"],
                "competitionName": ev["competition"]["name"], "homeTeamName": "Crystal Palace", "awayTeamName": opp,
                "venueName": "Selhurst Park", "stadiumName": "Selhurst Park",
                "transactionDate": iso(tdate), "transactionValue": float(rnd.choice([28, 32, 38, 45, 55])),
                "standName": stand, "areaName": stand, "blockName": f"Block {rnd.randint(1, 40)}",
                "seatRow": rnd.choice("ABCDEFGHJK"), "seatNumber": str(rnd.randint(1, 60)),
                "hasAttended": attended, "arrivalTime": ev["date"] if attended else None,
                "createdAt": iso(tdate), "updatedAt": ev["date"],
            })
            if attended:
                for pid, pname, cat, price in rnd.sample(RETAIL, rnd.randint(0, 3)):
                    qty = rnd.randint(1, 2)
                    RETAILS.append({
                        "scvUserRetailId": _row_ids("retail", len(RETAILS)), "scvUserId": uid, "productId": pid,
                        "productDescription": pname, "productCategory": cat,
                        "transactionDate": ev["date"], "transactionValue": round(price * qty, 2),
                        "transactionQuantity": qty, "isRefunded": False, "createdAt": ev["date"], "updatedAt": ev["date"],
                    })
                STRUCTURED.append({
                    "scvUserStructuredEventId": _row_ids("se", len(STRUCTURED)), "scvUserId": uid,
                    "sourceSystemName": "ENTRY_GATES", "category": "app", "action": "scan", "label": "ticket_entry",
                    "value": 1.0, "createdAt": ev["date"], "updatedAt": ev["date"],
                })
    for _ in range(int(20 + 200 * keen)):
        cat, act, label = rnd.choice(APP_EVENTS[:-1])
        d = NOW - timedelta(days=rnd.randint(0, 100), minutes=rnd.randint(0, 1440))
        STRUCTURED.append({
            "scvUserStructuredEventId": _row_ids("se", len(STRUCTURED)), "scvUserId": uid,
            "sourceSystemName": "CLUB_APP", "category": cat, "action": act, "label": label,
            "value": float(rnd.randint(1, 120)) if cat == "video" else 1.0,
            "createdAt": iso(d), "updatedAt": iso(d),
        })


# ---------- Preferences Centre: "Favourite player" (documented as the example preference) ----------
FAVOURITE_PLAYER_PREF = {
    "name": "Favourite player", "key": "favouritePlayer", "type": "", "visualType": "Select", "deprecated": False,
    "options": [{
        "id": oid("opt-" + p["id"]), "index": i + 1, "value": f"{p['forename']} {p['surname']}",
        "linkedIds": [{"sourceSystem": "OPTA_FOOTBALL_PLAYER", "sourceSystemId": str(3000 + i)}], "metadata": {},
    } for i, p in enumerate(PLAYERS)],
}
