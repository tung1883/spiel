"""Minimal RSocket-over-WebSocket client (just what chess.com's play service uses) + chess.com move codec."""
import asyncio
import json
import struct

import chess

SETUP, KEEPALIVE, REQUEST_RESPONSE, FNF, REQUEST_STREAM, REQUEST_N, CANCEL, PAYLOAD, ERROR = 1, 3, 4, 5, 6, 8, 9, 10, 11
F_METADATA, F_COMPLETE, F_NEXT, F_RESPOND = 0x100, 0x40, 0x20, 0x80

TCN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?{~}(^)[_]@#$,*+=-;:."


class RSocketError(Exception):
    pass


PROMO = "qnrbkp"


def uci_to_code(uci: str) -> str:
    """Move -> 2 chars. Promotions use target chars 64..75: 64 + 3*piece(q,n,r,b) + (file delta + 1)."""
    sq = lambda s: (ord(s[0]) - 97) + 8 * (int(s[1]) - 1)
    frm, to = sq(uci[:2]), sq(uci[2:4])
    if len(uci) > 4:
        to = 64 + 3 * PROMO.index(uci[4]) + (to % 8 - frm % 8 + 1)
    return TCN[frm] + TCN[to]


def code_to_uci(code: str) -> str:
    name = lambda i: "abcdefgh"[i % 8] + str(i // 8 + 1)
    frm, to = TCN.index(code[0]), TCN.index(code[1])
    if to < 64:
        return name(frm) + name(to)
    promo = PROMO[(to - 64) // 3]
    to = frm + (-8 if frm < 16 else 8) + (to - 64) % 3 - 1
    return name(frm) + name(to) + promo


def route_metadata(*routes: str) -> bytes:
    body = b"".join(bytes([len(r)]) + r.encode() for r in routes)
    return b"\xfe" + len(body).to_bytes(3, "big") + body


def _frame(stream: int, ftype: int, flags: int, body: bytes) -> bytes:
    return struct.pack(">IH", stream, (ftype << 10) | flags) + body


def _payload(route: str | None, data: dict | None) -> tuple[int, bytes]:
    meta = route_metadata(route) if route else b""
    raw = json.dumps(data, separators=(",", ":")).encode() if data is not None else b""
    return (F_METADATA if meta else 0), (len(meta).to_bytes(3, "big") + meta if meta else b"") + raw


def _split(flags: int, body: bytes) -> tuple[bytes, bytes]:
    if flags & F_METADATA:
        n = int.from_bytes(body[:3], "big")
        return body[3:3 + n], body[3 + n:]
    return b"", body


def _route_of(meta: bytes) -> str:
    return meta[5:5 + meta[4]].decode(errors="replace") if meta[:1] == b"\xfe" and len(meta) > 5 else ""


class RSocket:
    """Client side. `request_stream` yields decoded JSON payloads; `request` returns the first payload."""

    def __init__(self, ws):
        self.ws = ws
        self._sid = -1
        self._streams: dict[int, asyncio.Queue] = {}
        self._reader = asyncio.create_task(self._read_loop())
        self.closed = asyncio.Event()

    @classmethod
    async def open(cls, ws, setup_data: dict) -> "RSocket":
        self = cls(ws)
        mime = b"message/x.rsocket.composite-metadata.v0"
        data = b"application/json"
        body = struct.pack(">HHII", 1, 0, 2000, 5000) + bytes([len(mime)]) + mime + bytes([len(data)]) + data
        body += json.dumps(setup_data, separators=(",", ":")).encode()
        await ws.send(_frame(0, SETUP, 0, body))
        return self

    def _new_stream(self) -> int:
        self._sid += 2
        q: asyncio.Queue = asyncio.Queue()
        self._streams[self._sid] = q
        return self._sid

    async def _read_loop(self) -> None:
        try:
            async for msg in self.ws:
                sid, tf = struct.unpack(">IH", msg[:6])
                ftype, flags, body = tf >> 10, tf & 0x3FF, msg[6:]
                if ftype == KEEPALIVE:
                    if flags & F_RESPOND:
                        await self.ws.send(_frame(0, KEEPALIVE, 0, body))
                elif ftype == PAYLOAD and sid in self._streams:
                    _, data = _split(flags, body)
                    if flags & F_NEXT:
                        self._streams[sid].put_nowait(json.loads(data) if data else {})
                    if flags & F_COMPLETE:
                        self._streams[sid].put_nowait(None)
                elif ftype == ERROR and sid in self._streams:
                    self._streams[sid].put_nowait(RSocketError(body[4:].decode(errors="replace")))
                elif ftype == REQUEST_RESPONSE and sid % 2 == 0:  # server asks (route "echo"): answer with same data
                    meta, data = _split(flags, body)
                    await self.ws.send(_frame(sid, PAYLOAD, F_NEXT | F_COMPLETE, data))
        except Exception as e:
            err = RSocketError(f"connection lost: {e}")
            for q in self._streams.values():
                q.put_nowait(err)
        finally:
            self.closed.set()

    async def request_stream(self, route: str, data: dict | None = None):
        sid = self._new_stream()
        fl, body = _payload(route, data)
        await self.ws.send(_frame(sid, REQUEST_STREAM, fl, struct.pack(">I", 1 << 30) + body))
        q = self._streams[sid]
        while True:
            item = await q.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item

    async def request(self, route: str, data: dict | None = None, timeout: float = 10) -> dict:
        sid = self._new_stream()
        fl, body = _payload(route, data)
        await self.ws.send(_frame(sid, REQUEST_RESPONSE, fl, body))
        item = await asyncio.wait_for(self._streams[sid].get(), timeout)
        self._streams.pop(sid, None)
        if isinstance(item, Exception):
            raise item
        return item or {}

    async def fire(self, route: str, data: dict | None = None) -> None:
        sid = self._new_stream()
        self._streams.pop(sid, None)
        fl, body = _payload(route, data)
        await self.ws.send(_frame(sid, FNF, fl, body))

    async def close(self) -> None:
        self._reader.cancel()
        try:
            await self.ws.close()
        except Exception:
            pass


def moves_to_uci(moves: list) -> list[str]:
    """chess.com events `moves` ([[code, clockMs], ...]) -> UCI list."""
    return [code_to_uci(m[0]) for m in moves]


def legal_uci(board: chess.Board, uci: str) -> bool:
    return chess.Move.from_uci(uci) in board.legal_moves
