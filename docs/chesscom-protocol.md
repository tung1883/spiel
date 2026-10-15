# chess.com live-play protocol notes (reverse-engineered, 2026-10, client 2026.10.2)

Unofficial and subject to change. Observed from a logged-in browser session; no secrets recorded here.

## Auth
Cookie session (PHPSESSID, ACCESS_TOKEN, CHESSCOM_REMEMBERME, plus Cloudflare cf_clearance/__cf_bm).
Password login needs a Cloudflare Turnstile token, so the user logs in in their own browser once. The long-lived
`CHESSCOM_REMEMBERME` cookie alone is enough: `GET /home` with only that cookie returns fresh PHPSESSID/ACCESS_TOKEN
(Set-Cookie) and `"uuid"`/`"username"` in the page. Bot games (`/play/computer`) make no game traffic: the bot runs in the page.
A plain `httpx` client
with the session cookies and the browser's reduced User-Agent
(`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/<major>.0.0.0 Safari/537.36`)
gets 200s from `/service/*` endpoints (checked: matcher/seeks, play/games).
Headers seen on XHRs: `x-chesscom-no-csrf: 1`, `x-chesscom-client`, `x-chesscom-play-client`, `Referer`.

## HTTP
- `GET /service/matcher/seeks`, `GET /service/matcher/challenges`, `GET /service/play/games` (list of my active games;
  game objects carry `transports.rsocket.{url,routes}` per the site JS).
- Create seek: `POST /service/matcher/seeks/chess`, JSON:
  `{"capabilities":["rated"],"rated":true,"gameType":"chess","timeControl":{"base":"PT600S","increment":"PT0S"},"ratingRange":{"upper":null,"lower":-25}}`

## Game socket: RSocket over WebSocket
`wss://www.chess.com/service/play-as-1-3/rsocket` (auth by cookies on the upgrade). Binary frames, no length prefix:
`streamId u32 | type(6 bits)+flags(10 bits) u16 | body`. Types: SETUP 1, KEEPALIVE 3, REQUEST_RESPONSE 4,
FNF 5, REQUEST_STREAM 6, PAYLOAD 10. Flags: METADATA 0x100, NEXT 0x20, COMPLETE 0x40, KEEPALIVE respond 0x80.

1. SETUP (v1.0, keepalive 2000ms, maxlife 5000ms, metadata mime `message/x.rsocket.composite-metadata.v0`,
   data mime `application/json`), data `{"acknowledgements":true,"authentication":"strict","client":"<client string>","userId":"<my uuid>"}`.
2. REQUEST_STREAM (client stream ids are odd), initial n=2^30, composite metadata routing `games.<gameId>.events` ->
   server sends PAYLOAD per state: `{id, clocks:[w,b] ms, moves:[[code,clockMs],...], playersScores, actions, timeouts,
   connectivity, createdAt, updatedAt, startedAt, config, precalculatedRatings}`; game end adds `results:[..]`, `ratings`, `finishedAt`
   (e.g. `["aborted","aborted"]`) and the stream completes.
3. FNF `games.<gameId>.acknowledgments` `{"eventUpdatedAt":..,"receivedAt":..}` after each event (optional but the site does it).
4. Move: REQUEST_RESPONSE `games.<gameId>.moves`
   `{"clock":<ms left>,"gameId":..,"index":<ply, 0-based>,"metadata":{"clockms":..,"toggledMove":false,"changeOfHeartMove":false,"moveHoldTime":0,...},"move":"mC"}`
   reply `{"updatedAt":..}`.
5. Action: REQUEST_RESPONSE `games.<gameId>.actions` `{"index":<my player index 0=white,1=black>,"type":"abort"}`
   (abort observed; resign/draw presumably the same with another `type`, unverified).
6. Server REQUEST_RESPONSE route `echo` (data = timestamp): reply PAYLOAD (NEXT|COMPLETE) with the same data.
   KEEPALIVE frames with the RESPOND flag must be answered with a KEEPALIVE (no flag).

Composite metadata entry for routing: byte 0xFE (well-known id 126 | 0x80), u24 length, then length-prefixed route strings.

## Move encoding
Each move is 2 chars from the alphabet
`abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?{~}(^)[_]@#$,*+=-;:.` (square index 0=a1..63=h8
`file + 8*rank`): `mC` = e2e4 (m=12=e2, C=28=e4). Promotions use an extended index for the target (not verified).

## Verified end to end (2026-10, unrated games)
- **Presence**: a seek only goes `active` while a `wss://www.chess.com/pubsub?uid=<uuid>&client_type=web&client_version=1.6.0&client_id=<8 chars>`
  socket is connected (cookies on upgrade). Frames: server `0["<sid>",20,45,{..}]` -> client echoes `0["<sid>",20,45]`, then
  `41["matcher/tickets/users/:me"]` per channel; server `45[n,channel,lastId]` / `47[n,channel,id,"<base64 gzip json>"]`, ack `43[n]`;
  `2` -> `3`, `2[n]` -> `3[n]`. Seek tickets arrive on `matcher/tickets/users/:me`.
- Seek: `POST /service/matcher/seeks/chess` (201, body has `href`; `DELETE <href>` cancels, 204). Matched in ~10 s.
- `GET /service/play/games` -> `{"games":[{id, rated, players:[whiteUuid, blackUuid], playersDetails:[{id, username, rating,..}],
  timeControl, transports.rsocket.{url:"/service/play-1/rsocket", routes}}]}`. Use that rsocket URL. My colour = index in `players`.
- Events stream (`games.<id>.events`) -> state incl. `actions:[["abort","draw"],["abort","draw"]]`; ends with `results`.
- Verified: abort before first move (`{"index":<me>,"type":"abort"}` -> `{"updatedAt"}`), a move (`e7e5` as black), resign
  (`type:"resign"`, game finished).
- A seek started from the website itself defaults to **rated**; the API body's `rated` flag is honoured.

- Draw: `{"index":<me>,"type":"draw"}` offers (verified). Event `actions` per player then shows the receiver
  `["draw-ignore","draw-reject","abort","draw"]` (`draw` = accept, `draw-reject` = decline) and an extra `draws` field; the offerer only has `["abort"]`.
  So "opponent offered a draw" <=> `draw-reject` in my own actions. Accept/decline themselves not exercised yet.
- Promotion: target char 64..75 = `64 + 3*"qnrb".index(piece) + (file delta + 1)`; checked by decoding 6 real games' `moveList`
  (https://www.chess.com/callback/live/game/<id>) into legal moves with exact round trip. Not yet sent live.

## Unknown
Whether missing move telemetry affects fair-play checks; accept/decline draw live; sending a promotion live.
