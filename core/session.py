"""Track app session start so we can show 'new since session start' signals."""
import os, time
from datetime import datetime, timezone

SESSION_FILE = "/tmp/freeform_session_start.txt"

def _read() -> float:
    try:
        with open(SESSION_FILE) as f: return float(f.read().strip())
    except Exception:
        return 0.0

def _write(ts: float):
    with open(SESSION_FILE, "w") as f: f.write(str(ts))

def start_if_missing():
    if _read() == 0.0:
        _write(time.time())

def start_timestamp() -> datetime:
    ts = _read()
    if ts == 0.0:
        ts = time.time(); _write(ts)
    return datetime.fromtimestamp(ts, tz=timezone.utc)

def reset():
    _write(time.time())
