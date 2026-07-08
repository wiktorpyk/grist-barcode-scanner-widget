#!/usr/bin/env python3
"""
Barcode companion server for the Grist barcode scanner widget.

Routes:
  GET /widget          — serve the widget HTML (use this URL in Grist)
  GET /scan/{token}    — Binary Eye sends scan results here
  GET /ws/{token}      — widget WebSocket connection
  GET /health          — liveness check

Usage:
  pip install aiohttp
  python barcode-widget.py [--host 0.0.0.0] [--port 8001]

Then in Grist → Custom Widget URL: http://<your-lan-ip>:8001/widget
"""

import asyncio
import json
import logging
import argparse
import socket
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from aiohttp import web, WSMsgType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("barcode")

# token -> set of open WebSocket connections
_connections: dict[str, set[web.WebSocketResponse]] = defaultdict(set)

WIDGET_HTML_PATH = Path(__file__).parent / "barcode-widget.html"


# ── Widget HTML ────────────────────────────────────────────────────────────────

async def widget_handler(request: web.Request) -> web.Response:
    """Serve the widget HTML. Grist's Custom Widget URL points here."""
    if not WIDGET_HTML_PATH.exists():
        return web.Response(status=404, text="barcode-widget.html not found next to server script")
    html = WIDGET_HTML_PATH.read_text(encoding="utf-8")
    return web.Response(
        text=html,
        content_type="text/html",
        headers={
            # Allow Grist to embed the widget in an iframe
            "X-Frame-Options": "ALLOWALL",
            # Permissive CSP so the widget can open a WebSocket back to us
            "Content-Security-Policy": (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' "
                "https://docs.getgrist.com https://cdnjs.cloudflare.com; "
                "connect-src *;"
            ),
        },
    )


# ── WebSocket handler ──────────────────────────────────────────────────────────

async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    token = request.match_info["token"]
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)

    _connections[token].add(ws)
    log.info("WS  connected   token=%.8s…  clients=%d", token, len(_connections[token]))

    await ws.send_str(json.dumps({"type": "connected", "token": token}))

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get("type") == "ping":
                        await ws.send_str(json.dumps({"type": "pong"}))
                except Exception:
                    pass
            elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break
    finally:
        _connections[token].discard(ws)
        if not _connections[token]:
            del _connections[token]
        log.info(
            "WS  disconnected token=%.8s…  clients=%d",
            token,
            len(_connections.get(token, set())),
        )

    return ws


# ── Binary Eye HTTP handler ────────────────────────────────────────────────────

async def scan_handler(request: web.Request) -> web.Response:
    """
    Receives scan results from Binary Eye.

    Binary Eye URL template (set in Binary Eye → Settings → URL):
      http://<host>:8001/scan/<token>?content={content}&format={format}&timestamp={timestamp}

    Request type must be set to: GET with complete query string
    """
    token = request.match_info["token"]
    q = request.rel_url.query

    content   = q.get("content", "").strip()
    fmt       = q.get("format", "unknown")
    timestamp = q.get("timestamp", datetime.now().isoformat())

    log.info("SCAN token=%.8s…  content=%r  format=%s", token, content, fmt)

    if not content:
        log.warning("SCAN  missing 'content' param — check your Binary Eye URL template")
        return web.Response(text="OK (no content)")  # Binary Eye treats non-200 as error

    if token not in _connections or not _connections[token]:
        log.warning("SCAN  no widgets listening on token=%.8s…", token)
        return web.Response(text="OK (no listeners)")

    payload = json.dumps({
        "type":      "scan",
        "content":   content,
        "format":    fmt,
        "timestamp": timestamp,
    })

    dead: set[web.WebSocketResponse] = set()
    sent = 0
    for ws in list(_connections[token]):
        try:
            await ws.send_str(payload)
            sent += 1
        except Exception:
            dead.add(ws)
    _connections[token] -= dead

    log.info("SCAN  forwarded to %d widget(s)", sent)
    return web.Response(text="OK")


# ── Health ─────────────────────────────────────────────────────────────────────

async def health_handler(request: web.Request) -> web.Response:
    total = sum(len(v) for v in _connections.values())
    return web.Response(
        content_type="application/json",
        text=json.dumps({
            "status":        "ok",
            "active_tokens": len(_connections),
            "clients":       total,
        }),
    )


# ── CORS middleware ────────────────────────────────────────────────────────────

@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return web.Response(headers={
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        })
    resp = await handler(request)
    resp.headers.setdefault("Access-Control-Allow-Origin", "*")
    return resp


# ── App factory ────────────────────────────────────────────────────────────────

def make_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/widget",       widget_handler)
    app.router.add_get("/scan/{token}", scan_handler)
    app.router.add_get("/ws/{token}",   ws_handler)
    app.router.add_get("/health",       health_handler)
    return app


# ── Entry point ────────────────────────────────────────────────────────────────

def _lan_ip() -> str:
    """Best-effort guess at the LAN IP for display purposes."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    parser = argparse.ArgumentParser(description="Barcode companion server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    ip = _lan_ip()

    log.info("━" * 56)
    log.info("Barcode server  →  port %d", args.port)
    log.info("")
    log.info("  Grist widget URL  →  http://%s:%d/widget", ip, args.port)
    log.info("  Binary Eye URL    →  http://%s:%d/scan/<token>", ip, args.port)
    log.info("                        ?content={content}&format={format}&timestamp={timestamp}")
    log.info("  WebSocket         →  ws://%s:%d/ws/<token>", ip, args.port)
    log.info("  Health check      →  http://%s:%d/health", ip, args.port)
    log.info("")
    log.info("  Token is generated by the widget — copy the URL from the widget Settings panel.")
    log.info("━" * 56)

    web.run_app(make_app(), host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()