"""chess.com `/pubsub` websocket: presence + notifications (seek tickets etc.). Protocol per docs/chesscom-protocol.md."""
import asyncio
import base64
import gzip
import json
import random
import string

from websockets.asyncio.client import connect

URL = "wss://www.chess.com/pubsub"
CLIENT_VERSION = "1.6.0"


class PubSub:
    def __init__(self, ws):
        self.ws = ws
        self.events: asyncio.Queue = asyncio.Queue()  # (channel, payload list)
        self._task = asyncio.create_task(self._loop())

    @classmethod
    async def open(cls, cookies: dict, user_agent: str, user_id: str, channels: list[str]) -> "PubSub":
        cid = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        ws = await connect(f"{URL}?uid={user_id}&client_type=web&client_version={CLIENT_VERSION}&client_id={cid}",
                           additional_headers={"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
                                               "Origin": "https://www.chess.com"},
                           user_agent_header=user_agent, max_size=None)
        self = cls(ws)
        self._pending_channels = channels
        return self

    async def _loop(self) -> None:
        try:
            async for raw in self.ws:
                if raw == "2":
                    await self.ws.send("3")
                elif raw.startswith("0["):  # hello: echo, then subscribe
                    hello = json.loads(raw[1:])
                    await self.ws.send("0" + json.dumps(hello[:3], separators=(",", ":")))
                    for ch in self._pending_channels:
                        await self.ws.send("41" + json.dumps([ch]))
                elif raw.startswith("2["):  # numbered ping
                    await self.ws.send("3" + raw[1:])
                elif raw.startswith(("45[", "47[")):
                    msg = json.loads(raw[2:])
                    await self.ws.send(f"43[{msg[0]}]")
                    self.events.put_nowait((msg[1], [self._unpack(x) for x in msg[2:]]))
                else:
                    self.events.put_nowait(("?raw", [raw]))
        except Exception as e:
            self.events.put_nowait(("?closed", [repr(e)]))

    @staticmethod
    def _unpack(x):
        """Payloads are base64(gzip(json)) strings."""
        if isinstance(x, str) and x.startswith("H4sI"):
            try:
                return json.loads(gzip.decompress(base64.b64decode(x)))
            except Exception:
                return x
        return x

    async def close(self) -> None:
        self._task.cancel()
        try:
            await self.ws.close()
        except Exception:
            pass
