"""TypeRacer /api/action binary encoding (reverse-engineered from the web client)."""
import base64
import struct

ACTIONS = {
    "match-automatic": 1, "match-practice": 2, "match-qotd": 3, "match-ghost": 4, "match-room": 5,
    "poll": 16, "start-race": 17, "progress": 18, "finish": 19, "challenge": 20, "save": 21,
    "refresh-text": 22, "leave-race": 23, "fail": 24,
    "chat": 32, "join-race": 33, "end-race": 34, "update-room": 35, "leave-room": 36, "close-room": 37,
}
FIELDS = {
    "match-practice": [("category", "str8")],
    "match-room": [("textUniverseId", "str8"), ("roomId", "str8")],
    "progress": [("wordsTyped", "u16")],
    "finish": [("keylog", "str32")],
    "chat": [("body", "str16")],
    "refresh-text": [("textUniverseId", "str8")],
}
_LEN = {"str8": 1, "str16": 2, "str32": 4}
CONTENT_TYPE = "application/x-typeracer-action-v1"


def _crc8(data: bytes) -> int:
    t = 0
    for b in data:
        t ^= b
        for _ in range(8):
            t = ((t << 1) ^ 7) & 255 if t & 128 else (t << 1) & 255
    return t


def _str(s: str, kind: str) -> bytes:
    raw = s.encode()
    return len(raw).to_bytes(_LEN[kind], "big") + raw


def encode(action: dict) -> str:
    name = action["action"]
    code = ACTIONS[name]
    is_race = 16 <= code < 32
    is_room = code >= 32
    body = bytearray([code])
    # "since" only applies to race/room-scoped actions (not entry, leave-room, close-room)
    scoped = code >= 16 and code not in (36, 37)
    since = action.get("since") if scoped and isinstance(action.get("since"), int) else 0
    body += since.to_bytes(6, "big")
    if is_race:
        if "gameId" in action:
            body += b"\x00" + _str(action["gameId"], "str8")
        elif "roomId" in action:
            body += b"\x01" + _str(action["roomId"], "str8")
        else:
            raise ValueError(f"{name} needs gameId or roomId")
    elif is_room:
        if "roomId" not in action:
            raise ValueError(f"{name} needs roomId")
        body += _str(action["roomId"], "str8")
    for key, kind in FIELDS.get(name, []):
        v = action.get(key)
        if kind == "u16":
            body += struct.pack(">H", v or 0)
        else:
            body += _str(v or "", kind)
    raw = bytes([1]) + bytes(body) + bytes([_crc8(bytes(body))])
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
