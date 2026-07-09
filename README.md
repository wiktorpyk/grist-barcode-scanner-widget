# Barcode Scanner Widget for Grist

A lightweight Python server + Grist custom widget that lets [Binary Eye](https://github.com/markusfisch/BinaryEye) stream scanned values directly into a Grist table in real time.

![Screenshot](https://i.ibb.co/FS04MJr/Screenshot-From-2026-07-09-20-16-15.png)


```

Phone (Binary Eye) → HTTP GET → Python Server → WebSocket → Grist Widget

```

## Requirements
- Python 3.11+
- Phone and server must be on the same local network (LAN)

## Quick Start

### 1. Run the Server
```bash
pip install aiohttp
python barcode-widget.py

```

*Runs on `0.0.0.0:8001` by default. Override using flags: `--host 0.0.0.0 --port 8001`.*

### 2. Add the Widget to Grist

1. In your Grist document, click **Add New** → **Add Widget to Page**.
2. Choose **Custom** and set the Widget URL to `http://<your-server-ip>:8001/widget`.
3. Grant **Full document access** when prompted.
4. Select the target table. In the right panel under the **Table** tab, set **Select By** to the Custom widget.

### 3. Configure the Widget & Phone

Open the widget settings (⚙ icon) and follow the Binary Eye setup instructions.

---

## Operation Modes

Adjust these behavioral settings directly inside the widget UI:

* **Write to row:** Inserts the barcode into the active row and moves down.
* **Append row:** Creates a new row with the scanned value at the bottom of the table.
* **Find row:** Searches your table for a matching barcode and instantly jumps to that row.

---

## Security & Architecture

* **Token-based routing:** Each widget instance generates a unique, random 128-bit token included in both the scan URL and the WebSocket handshake path.
* **Revocation:** Clicking **New token** inside the settings instantly invalidates older device configurations.

### HTTP Endpoints

* `GET /widget` — Serves the widget UI.
* `GET /scan/{token}` — Receives scan results (`?content=…&format=…`) from Binary Eye.
* `GET /ws/{token}` — WebSocket connection endpoint for the widget.
* `GET /health` — Liveness check: `{"status":"ok","active_tokens":N,"clients":N}`.