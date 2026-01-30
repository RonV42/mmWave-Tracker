import os
import json
import time
import threading
import traceback
import requests

from flask import Flask, render_template
from flask_socketio import SocketIO


# -----------------------------
# Config via environment vars
# -----------------------------
HUBITAT_HOST = os.getenv("HUBITAT_HOST", "192.168.1.101")  # IP or hostname
MAKERAPI_APP_ID = os.getenv("MAKERAPI_APP_ID", "")
MAKERAPI_TOKEN = os.getenv("MAKERAPI_TOKEN", "")
POLL_HZ = float(os.getenv("POLL_HZ", "10"))  # 10Hz default

BASE_URL = f"http://{HUBITAT_HOST}/apps/api/{MAKERAPI_APP_ID}"
DEVICES_URL = f"{BASE_URL}/devices?access_token={MAKERAPI_TOKEN}"

if not MAKERAPI_APP_ID or not MAKERAPI_TOKEN:
    print("WARNING: Missing MAKERAPI_APP_ID / MAKERAPI_TOKEN env vars", flush=True)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Global state
device_cache = {}        # deviceId -> {id, label, ...}
current_device_id = None
last_emit_ts = 0
last_targetinfo_raw = None


def makerapi_get_json(url: str):
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return r.json()


def parse_target_info(target_info_raw: str):
    """
    Example:
    {"ts":1769711060106,"count":1,"targets":[{"i":0,"id":1,"x":139,"y":76,"z":3,"dop":-400}]}
    """
    if not target_info_raw:
        return None

    s = str(target_info_raw).strip()

    # Normalize Hubitat escaping variants
    s = s.replace("\\,", ",")
    s = s.replace('\\"', '"')

    try:
        obj = json.loads(s)
        if isinstance(obj, dict) and "targets" in obj:
            return obj
    except Exception:
        return None

    return None


def refresh_devices():
    """
    Pull MakerAPI device list and filter to devices that have targetInfo attribute.
    """
    global device_cache

    try:
        devices = makerapi_get_json(DEVICES_URL)

        # MakerAPI /devices returns list like:
        # [{"id":"123","name":"Kitchen mmWave"}, ...]
        new_cache = {}
        for d in devices:
            dev_id = str(d.get("id"))
            label = d.get("label") or d.get("name") or f"Device {dev_id}"

            # We don't know which are mmWave until we query attributes.
            # But we can lazy-check later. For now include all.
            new_cache[dev_id] = {"id": dev_id, "label": label}

        device_cache = new_cache
        socketio.emit("device_list", list(device_cache.values()))
        return True

    except Exception as e:
        print(f"[refresh_devices] error: {e}", flush=True)
        traceback.print_exc()
        socketio.emit("backend_error", {"error": str(e)})
        return False


def fetch_device_state(device_id: str):
    url = f"{BASE_URL}/devices/{device_id}?access_token={MAKERAPI_TOKEN}"
    data = makerapi_get_json(url)

    attrs = {a.get("name"): a.get("currentValue") for a in data.get("attributes", [])}
    return {
        "deviceId": str(device_id),
        "deviceLabel": data.get("label") or data.get("name") or device_id,
        "attributes": attrs,
    }


def poll_loop():
    """
    Polls selected device and emits mmwave_update.
    """
    global last_emit_ts, last_targetinfo_raw

    interval = 1.0 / max(POLL_HZ, 0.5)

    while True:
        try:
            if not current_device_id:
                time.sleep(0.25)
                continue

            state = fetch_device_state(current_device_id)
            attrs = state["attributes"]

            target_info_raw = attrs.get("targetInfo")
            target_count = attrs.get("targetCount")

            print(f"[poll_loop] polling device {current_device_id} targetInfo={target_info_raw}")

            now = time.time()
            changed = target_info_raw != last_targetinfo_raw

            # emit if changed OR heartbeat every second
            if changed or (now - last_emit_ts) > 1.0:
                last_emit_ts = now
                last_targetinfo_raw = target_info_raw

                parsed = parse_target_info(target_info_raw)

                socketio.emit("mmwave_update", {
                    "deviceId": state["deviceId"],
                    "deviceLabel": state["deviceLabel"],
                    "targetCount": target_count,
                    "raw": target_info_raw,
                    "parsed": parsed,
                    "ts_client": int(now * 1000),
                })

        except Exception as e:
            print(f"[poll_loop] error: {e}", flush=True)
            traceback.print_exc()
            socketio.emit("backend_error", {"error": str(e)})

        time.sleep(interval)


@app.route("/")
def index():
    return render_template("index.html")


# -----------------------------
# Websocket handlers
# -----------------------------
@socketio.on("connect")
def on_connect():
    socketio.emit("backend_status", {"status": "connected"})
    refresh_devices()


@socketio.on("request_devices")
def on_request_devices():
    refresh_devices()


@socketio.on("change_device")
def on_change_device(device_id):
    global current_device_id, last_targetinfo_raw
    current_device_id = str(device_id)
    last_targetinfo_raw = None
    print(f"[change_device] monitoring device {current_device_id}", flush=True)
    socketio.emit("device_changed", {"deviceId": current_device_id})


if __name__ == "__main__":
    # Startup: refresh device list once
    refresh_devices()
    if device_cache:
        first_device_id = list(device_cache.keys())[0]
        current_device_id = first_device_id
        print(f"[startup] defaulting to device {current_device_id}")


    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()

    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
