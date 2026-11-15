"""Simulator of the HTTP API of an Orca heat pump (Carel terminal), for tests.

Replays the values of a real field dump (tests/fixtures/field_dump_*.txt):
/cgi/login, /cgi/readTags and /cgi/writeTags, with the IDALToken cookie.
"""
from aiohttp import web

TOKEN = "testtoken0123456789"


def load_dump(path):
    values = {}
    for line in open(path, encoding="utf8"):
        line = line.rstrip("\n")
        if ": " in line:
            tag, val = line.rsplit(": ", 1)
            values[tag.strip()] = val.strip()
    return values


class MockPac:
    def __init__(self, values, username="admin", password="admin"):
        self.values = dict(values)
        self.username, self.password = username, password
        self.writes = []          # [(tag, raw)]
        self.read_batches = []    # number of tags per readTags request
        self.max_url_len = 0
        self.logins = 0
        self.runner = None
        self.port = None

    async def start(self):
        app = web.Application()
        app.router.add_get("/cgi/login", self.login)
        app.router.add_get("/cgi/readTags", self.read_tags)
        app.router.add_get("/cgi/writeTags", self.write_tags)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        return f"127.0.0.1:{self.port}"

    async def stop(self):
        await self.runner.cleanup()

    def _authed(self, request):
        return request.cookies.get("IDALToken") == TOKEN

    async def login(self, request):
        q = request.query
        if q.get("username") == self.username and q.get("password") == self.password:
            self.logins += 1
            return web.Response(text=f"IDALToken={TOKEN}\n")
        return web.Response(text="#E_PASS_DONT_MATCH\n")

    async def read_tags(self, request):
        if not self._authed(request):
            return web.Response(text="#E_NEED_LOGIN\n")
        self.max_url_len = max(self.max_url_len, len(str(request.rel_url)))
        n = int(request.query["n"])
        self.read_batches.append(n)
        out = []
        for i in range(1, n + 1):
            tag = request.query[f"t{i}"]
            if tag in self.values:
                out.append(f"#{tag}\tS_OK\n192\t{self.values[tag]}\n")
            else:
                out.append(f"#{tag}\tE_UNKNOWNTAG\n")
        return web.Response(text="".join(out))

    async def write_tags(self, request):
        if not self._authed(request):
            return web.Response(text="#E_NEED_LOGIN\n")
        tag, val = request.query["t1"], request.query["v1"]
        self.writes.append((tag, val))
        self.values[tag] = val
        return web.Response(text=f"#{tag}\tS_OK\n192\t{val}\n")
