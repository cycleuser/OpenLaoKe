"""Local OpenAI-compatible proxy that injects browser-like headers upstream.

Some clients (pi, curl, plain httpx) get a Cloudflare challenge from
llm.cycleuser.com even with a valid key, while a browser User-Agent over
HTTP/1.1 is let through. This proxy forwards every request to the upstream
with those headers, so any client can talk to the same model for a fair
comparison.

Usage:
    python bench/ua_proxy.py --port 8799 --upstream https://llm.cycleuser.com
"""

from __future__ import annotations

import argparse

from aiohttp import ClientSession, web

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HOP_HEADERS = {
    "host",
    "content-length",
    "connection",
    "accept-encoding",
    "user-agent",
    "accept",
    "transfer-encoding",
}


def make_app(upstream: str) -> web.Application:
    app = web.Application(client_max_size=64 * 1024 * 1024)

    async def forward(request: web.Request) -> web.StreamResponse:
        session: ClientSession = request.app["session"]
        url = upstream.rstrip("/") + "/" + request.match_info.get("tail", "")
        if request.query_string:
            url += "?" + request.query_string
        body = await request.read()
        headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}
        headers["User-Agent"] = BROWSER_UA
        headers["Accept"] = request.headers.get("Accept", "application/json")
        resp = await session.request(request.method, url, headers=headers, data=body)
        out = web.StreamResponse(status=resp.status)
        for key, value in resp.headers.items():
            if key.lower() not in HOP_HEADERS:
                out.headers[key] = value
        await out.prepare(request)
        async for chunk in resp.content.iter_any():
            await out.write(chunk)
        await out.write_eof()
        return out

    async def start_session(app: web.Application) -> None:
        app["session"] = ClientSession()

    async def cleanup(app: web.Application) -> None:
        await app["session"].close()

    app.router.add_route("*", "/{tail:.*}", forward)
    app.on_startup.append(start_session)
    app.on_cleanup.append(cleanup)
    return app


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--upstream", default="https://llm.cycleuser.com")
    args = ap.parse_args()
    web.run_app(make_app(args.upstream), host="127.0.0.1", port=args.port, print=None)


if __name__ == "__main__":
    main()
