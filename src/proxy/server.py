"""Reverse proxy that lets external LAN devices use FapTap through us.

Strategy
========
Other devices on the LAN open ``http://<our-ip>:<port>``. The proxy fetches
content from ``https://faptap.net`` server-side, rewrites every reference to
``handyfeeling.com`` so it points to the proxy itself, then serves the result.

That way no DNS hijacking, no client-side cert install, and no JS injection
on the client are needed. The Handy API endpoints are routed to the same
``FakeHandyServer`` instance that the local FapTap path already uses.
"""

from __future__ import annotations

import asyncio
import re
import threading
from typing import Optional

import aiohttp
from aiohttp import web


# Hosts that point at "The Handy" cloud — rewritten to local proxy paths.
HANDY_HOSTS = {
    "https://www.handyfeeling.com": "",
    "https://staging.handyfeeling.com": "",
    "https://scripts01.handyfeeling.com": "/scripts-api",
}

# Headers we strip from upstream responses so the proxy can deliver them
# cleanly to a browser that is *not* on faptap.net's origin.
STRIPPED_RESPONSE_HEADERS = {
    "content-encoding",        # we already decoded
    "content-length",          # body length changes after rewriting
    "transfer-encoding",
    "content-security-policy",
    "content-security-policy-report-only",
    "x-frame-options",
    "strict-transport-security",
    "alt-svc",
    "report-to",
    "nel",
}

# Headers we strip from the client request before forwarding upstream.
STRIPPED_REQUEST_HEADERS = {
    "host",
    "connection",
    "accept-encoding",
    "content-length",
}

DEFAULT_UPSTREAM = "https://faptap.net"

# Browser-like UA so Cloudflare bot detection has less to grab onto.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
)

_HANDY_HOST_RE = re.compile(
    r"https://(?:www|staging|scripts01)\.handyfeeling\.com",
)


def _rewrite_text(body: str) -> str:
    """Rewrite handyfeeling.com URLs to proxy-relative URLs."""
    def sub(match: re.Match) -> str:
        host = match.group(0)
        return HANDY_HOSTS.get(host, "")
    return _HANDY_HOST_RE.sub(sub, body)


class ProxyServer:
    """Network-accessible reverse proxy for an upstream adult-content site.

    Upstream is configurable at runtime so the same proxy can serve different
    sites (FapTap, SexLikeReal, ...) without a restart.
    """

    def __init__(self, host: str, port: int,
                 handy_host: str, handy_port: int,
                 upstream: str = DEFAULT_UPSTREAM,
                 on_log=None):
        self.host = host
        self.port = port
        self._handy_url = f"http://{handy_host}:{handy_port}"
        self._upstream = upstream.rstrip("/")
        self._on_log = on_log or (lambda msg: None)
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._runner: Optional[web.AppRunner] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._running = False

    @property
    def upstream(self) -> str:
        return self._upstream

    def set_upstream(self, upstream: str):
        """Change the proxied site at runtime. Resets the cookie session."""
        new_upstream = upstream.rstrip("/")
        if new_upstream == self._upstream:
            return
        self._upstream = new_upstream
        # Drop cached cookies — they belong to the old upstream's domain.
        if self._loop and self._session:
            asyncio.run_coroutine_threadsafe(self._reset_session(), self._loop)
        self._on_log(f"Proxy upstream switched: {new_upstream}")

    async def _reset_session(self):
        try:
            await self._session.close()
        except Exception:
            pass
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        connector = aiohttp.TCPConnector(ssl=False)
        self._session = aiohttp.ClientSession(
            cookie_jar=cookie_jar,
            connector=connector,
        )

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._running or not self._loop:
            return
        self._running = False
        try:
            asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        except Exception:
            pass

    def _run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            self._on_log(f"Proxy error: {e}")
        finally:
            self._running = False

    async def _serve(self):
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        connector = aiohttp.TCPConnector(ssl=False)
        self._session = aiohttp.ClientSession(
            cookie_jar=cookie_jar,
            connector=connector,
        )
        self._stop_event = asyncio.Event()

        app = web.Application(client_max_size=64 * 1024 * 1024)
        # Handy API gets routed to the local fake server.
        app.router.add_route("*", "/api/handy/{tail:.*}", self._handle_handy)
        app.router.add_route("*", "/api/handy-rest/{tail:.*}", self._handle_handy)
        # Script hosting gets fetched live from the real CDN.
        app.router.add_route("*", "/scripts-api/{tail:.*}", self._handle_scripts)
        # Anything else is proxied to faptap.net.
        app.router.add_route("*", "/{tail:.*}", self._handle_proxy)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        self._on_log(f"Proxy running on {self.host}:{self.port}")

        try:
            await self._stop_event.wait()
        finally:
            await self._session.close()
            await self._runner.cleanup()

    async def _shutdown(self):
        if self._stop_event:
            self._stop_event.set()

    # ── Handy API routing ──────────────────────────────────────────

    async def _handle_handy(self, request: web.Request) -> web.StreamResponse:
        """Forward /api/handy/* and /api/handy-rest/* to the fake handy server."""
        target = f"{self._handy_url}{request.rel_url.path}"
        if request.query_string:
            target += f"?{request.query_string}"
        body = await request.read() if request.body_exists else None
        try:
            async with self._session.request(
                request.method,
                target,
                data=body,
                headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
                allow_redirects=False,
            ) as up:
                data = await up.read()
                resp = web.Response(
                    body=data,
                    status=up.status,
                    headers={"Content-Type": up.headers.get("Content-Type", "application/json")},
                )
        except Exception as e:
            self._on_log(f"Handy proxy error: {e}")
            return web.json_response({"error": str(e)}, status=502)

        _add_cors(resp, request)
        return resp

    # ── Script hosting passthrough ─────────────────────────────────

    async def _handle_scripts(self, request: web.Request) -> web.StreamResponse:
        """Forward /scripts-api/* to scripts01.handyfeeling.com."""
        tail = request.match_info.get("tail", "")
        target = f"https://scripts01.handyfeeling.com/{tail}"
        if request.query_string:
            target += f"?{request.query_string}"
        body = await request.read() if request.body_exists else None
        headers = _filter_request_headers(request.headers)
        try:
            async with self._session.request(
                request.method,
                target,
                data=body,
                headers=headers,
                allow_redirects=False,
            ) as up:
                data = await up.read()
                resp = web.Response(
                    body=data,
                    status=up.status,
                    headers=_filter_response_headers(up.headers),
                )
        except Exception as e:
            self._on_log(f"Scripts proxy error: {e}")
            return web.json_response({"error": str(e)}, status=502)

        _add_cors(resp, request)
        return resp

    # ── Generic FapTap proxy ───────────────────────────────────────

    async def _handle_proxy(self, request: web.Request) -> web.StreamResponse:
        upstream = self._upstream
        upstream_host = upstream.split("://", 1)[-1].split("/", 1)[0]
        tail = request.match_info.get("tail", "")
        target = f"{upstream}/{tail}"
        if request.query_string:
            target += f"?{request.query_string}"

        body = await request.read() if request.body_exists else None
        headers = _filter_request_headers(request.headers)
        headers["Host"] = upstream_host
        headers["User-Agent"] = BROWSER_UA
        headers.setdefault("Accept-Language", "en-US,en;q=0.9")
        # Pretend the request originated from the upstream so anti-CSRF and
        # referer checks don't reject us.
        headers["Referer"] = upstream + "/"
        headers["Origin"] = upstream

        try:
            async with self._session.request(
                request.method,
                target,
                data=body,
                headers=headers,
                allow_redirects=False,
            ) as up:
                data = await up.read()
                content_type = up.headers.get("Content-Type", "")

                # Rewrite text responses so handyfeeling.com URLs point to us.
                rewriteable = any(
                    ct in content_type
                    for ct in ("text/html", "text/css", "javascript",
                               "application/json", "application/xml", "text/xml")
                )
                if rewriteable and data:
                    try:
                        text = data.decode("utf-8", errors="replace")
                        text = _rewrite_text(text)
                        data = text.encode("utf-8")
                    except Exception:
                        pass

                resp_headers = _filter_response_headers(up.headers)
                # Rewrite Set-Cookie domains so the cookie sticks on our host.
                set_cookies = up.headers.getall("Set-Cookie", [])
                if set_cookies:
                    resp_headers.popall("Set-Cookie", None) if hasattr(resp_headers, "popall") else None
                    for raw in set_cookies:
                        rewritten = _rewrite_cookie(raw)
                        resp_headers.add("Set-Cookie", rewritten)

                # Handle 30x by rewriting the Location header to a proxy-local one.
                if "Location" in up.headers:
                    loc = up.headers["Location"]
                    if loc.startswith(upstream):
                        loc = loc[len(upstream):] or "/"
                    elif _HANDY_HOST_RE.match(loc):
                        loc = _rewrite_text(loc)
                    resp_headers["Location"] = loc

                resp = web.Response(
                    body=data,
                    status=up.status,
                    headers=resp_headers,
                )
        except Exception as e:
            self._on_log(f"Proxy error for {tail}: {e}")
            return web.Response(status=502, text=f"Proxy error: {e}")

        return resp


# ── Helpers ────────────────────────────────────────────────────────

def _filter_request_headers(headers) -> dict:
    out = {}
    for k, v in headers.items():
        if k.lower() in STRIPPED_REQUEST_HEADERS:
            continue
        out[k] = v
    return out


def _filter_response_headers(headers):
    """Return a CIMultiDict with security/encoding headers removed."""
    from multidict import CIMultiDict
    out = CIMultiDict()
    for k, v in headers.items():
        if k.lower() in STRIPPED_RESPONSE_HEADERS:
            continue
        out.add(k, v)
    return out


def _add_cors(resp, request):
    origin = request.headers.get("Origin", "*")
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Allow-Methods"] = "GET, PUT, POST, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = (
        "X-Connection-Key, Content-Type, Authorization, Accept"
    )


def _rewrite_cookie(raw: str) -> str:
    """Strip Domain= and Secure attributes so cookies stick on our host."""
    parts = [p.strip() for p in raw.split(";")]
    out = []
    for p in parts:
        low = p.lower()
        if low.startswith("domain="):
            continue
        if low == "secure":
            continue
        if low.startswith("samesite=none"):
            p = "SameSite=Lax"
        out.append(p)
    return "; ".join(out)
