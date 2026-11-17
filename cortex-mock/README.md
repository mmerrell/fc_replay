# Cortex mock (Fan Data Platform + public REST)

Stdlib-only Python mock of the Cortex (cortextech.io) APIs, with fake Crystal Palace 2026/27 data, for the
"Your Crystal Palace Replay" prototype. All fans, scores, tickets and spend are invented.

    docker compose up --build        # http://localhost:8080
    curl localhost:8080/_mock/health
    curl localhost:8080/_mock/fans   # grab an scvUserId

## Endpoints
| Cortex API | Route | Notes |
|---|---|---|
| Events | `GET /v2/public/clients/DEMO/events[/{id}]` | all documented filters (startDate, statusGroup, teamId, teamNameSearch, ...) |
| Players | `GET /v1/clients/DEMO/players[/{id}\|/slug/{slug}]` | filters: teamSlug, positionSlug, query, ... |
| Teams | `GET /v1/clients/DEMO/teams[/{id}]` | |
| Single Fan View | `POST /clients/DEMO/query` (any prefix, e.g. `/v5.0/clients/DEMO/query`) | GraphQL: user, ticket(s), retail(s), structuredEvent(s) |

SFV example:

    curl -s localhost:8080/clients/DEMO/query -d '{"query":"{ tickets(scvUserId:\"<id>\", size:50){ items{productName transactionValue hasAttended} next } }"}'

Pagination: pass `next` back as `cursor`. `sort` defaults to `["-updatedAt"]`. Variables are supported.

## Env
`CLIENT_ID` (DEMO), `SEED` (42), `NUM_FANS` (100), `INACTIVE_FANS` (15; profile only, zero tickets/retail/events; `/_mock/fans` flags them `hasActivity:false`), `API_KEY` (require X-API-Key on SFV), `MOCK_NOW` (freeze "today"), `PORT` (8080).

## Verified vs inferred
Taken from the Cortex docs: event/team/venue/competition/season shapes, player fields, event + player query params,
SFV query names/arguments/pagination, and a subset of SFV field names (e.g. scvUserId, fullName, postcode, productName,
venueName, transactionValue, seatRow, hasAttended, sourceSystemName, category, action, label, value).
Guessed (marked INFERRED in data.py): ticket `stand`/`seatNumber`, retail `productName`/`category`, ID field names
on structured events, the `{"data": ...}` wrapper on REST lists, the SFV route path, and SFV auth (the docs don't say).
Swap in real responses from Cortex's Postman collection when you get access.

## Members' profiles and favourite player (added)
All PII is invented. SFV `user` now has firstName, lastName, postcodeTown (home city), age, birthDate, countryCode,
distanceToClub, mobileNumber (Ofcom drama range, not real) and an empty `metadata`. Tickets/retail use the real SFV field
names (homeTeamName, awayTeamName, standName, blockName, productDescription, productCategory, ...).

Favourite player is a Preferences Centre preference, as Cortex's docs model it (players are options with `linkedIds`):
`GET /v1/clients/DEMO/client-preferences/favouritePlayer`. Without a token you get the definition and options; with
`Authorization: Bearer <scvUserId>` (MOCK: real Cortex wants the fan's JWT) you also get `selectedOptionIds`
(INFERRED field name; about 90% of Members have picked one).
