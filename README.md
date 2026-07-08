# Barcode Scanner Widget for Grist

A lightweight companion server + Grist custom widget that lets [Binary Eye](https://github.com/markusfisch/BinaryEye) write scanned values directly into a Grist table — or jump to matching rows — in real time.

![Screenshot](https://i.ibb.co/YTk0c0YV/Screenshot-From-2026-06-29-17-22-32.png)

```
Phone (Binary Eye)  →  HTTP GET  →  Python server  →  WebSocket  →  Grist widget
```

---

## Requirements

- Python 3.11+
- [`aiohttp`](https://docs.aiohttp.org/) (`pip install aiohttp`)
- The phone running Binary Eye must be on the **same LAN** as the server (or the server must be reachable from the phone)
- Grist

---

## Setup

### 1. Run the server

```bash
pip install aiohttp
python barcode_server.py
```

By default the server listens on `0.0.0.0:8001`. Override with flags:

```bash
python barcode_server.py --host 0.0.0.0 --port 8001
```

On startup it logs the URLs you'll need:

```
Grist widget URL  →  http://192.168.1.x:8001/widget
```

### 2. Add the widget to Grist

1. Open your Grist document.
2. Click Add New, then select Add Widget to Page.
3. Under Select Widget, choose Custom.
4. Set **Widget URL** to `http://<your-ip>:8001/widget`.
5. Grant **Full document access** when prompted.
6. Select your main table, open the Table tab, click Change widget, and change its **Select By** dropdown to the Custom widget.

### 3. Configure the widget

Click the **⚙ Settings** button (top-right of the widget) and:

- Choose the **barcode column** from your linked table.
- Copy the **server URL** or scan the **QR code** to configure Binary Eye.

### 4. Configure Binary Eye


1. Open Binary Eye, tap the three-dot menu (top-right), then Settings.
2. Enable Forward scans.
3. Set URL to the server URL shown above (copy or scan the QR code).
4. Set Request type to GET with complete query string.
5. Enable Scan continuously.

---

## How it works

| Component | Role |
|-----------|------|
| `barcode_server.py` | aiohttp server. Serves the widget HTML, accepts Binary Eye HTTP GET requests, and relays scan results to connected widget(s) over WebSocket. |
| `barcode-widget.html` | Grist custom widget. Opens a WebSocket to the server, displays connection status, and writes/finds rows via the Grist Plugin API. |

**Token security:** Each widget instance generates a random 128-bit token. The scan URL and WebSocket path both include this token, so only the correct widget receives a scan. Regenerating the token (Settings → **New token**) instantly invalidates the old Binary Eye URL.

---

## Modes

| Mode | What happens when a barcode is scanned |
|------|----------------------------------------|
| **Write to row** | Writes the scanned value into the barcode column of the currently selected row. |
| **Find row** | Searches the table for a row whose barcode column matches the scanned value and jumps to it. |

---

## Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/widget` | Serves `barcode-widget.html` with correct headers for Grist iframe embedding. |
| `GET` | `/scan/{token}` | Receives Binary Eye scan results (`?content=…&format=…&timestamp=…`) and forwards them over WebSocket. |
| `GET` | `/ws/{token}` | Widget WebSocket endpoint. |
| `GET` | `/health` | JSON liveness check: `{"status":"ok","active_tokens":N,"clients":N}`. |