"""Price history from Hyperliquid's public API. No key needed. Results are cached on disk."""
import json, time, urllib.request
from pathlib import Path

API = "https://api.hyperliquid.xyz/info"
STEP_MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def parse(raw):
    """Turn the API's string fields into numbers, drop duplicates, sort by time."""
    seen = {}
    for c in raw:
        seen[int(c["t"])] = {"t": int(c["t"]), "o": float(c["o"]), "h": float(c["h"]), "l": float(c["l"]), "c": float(c["c"]), "v": float(c["v"])}
    return [seen[t] for t in sorted(seen)]


def fetch_remote(coin, interval, start_ms, end_ms):
    """One request returns at most about 5,000 candles, so walk backwards from the end."""
    out, end = [], end_ms
    while end > start_ms:
        body = json.dumps({"type": "candleSnapshot", "req": {"coin": coin, "interval": interval, "startTime": start_ms, "endTime": end}}).encode()
        req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
        chunk = json.loads(urllib.request.urlopen(req, timeout=30).read())
        if not chunk: break
        out += chunk
        first = min(int(c["t"]) for c in chunk)
        if first <= start_ms or first >= end: break
        end = first - 1
        time.sleep(0.2)
    return out


def candles(coin, interval, start_ms, end_ms, cache_dir="data", fetch=fetch_remote):
    if not coin.isalnum(): raise ValueError("coin must be letters and digits only")
    path = Path(cache_dir) / f"{coin}_{interval}_{start_ms}_{end_ms}.json"
    if path.exists(): return json.loads(path.read_text())
    out = [c for c in parse(fetch(coin, interval, start_ms, end_ms)) if start_ms <= c["t"] and c["t"] + STEP_MS.get(interval, 0) <= end_ms + 1]      # closed candles only
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(".tmp"); tmp.write_text(json.dumps(out)); tmp.replace(path)
    return out


def recent(coin, interval, n=400):
    """The latest n closed candles, for the live runner. Not cached."""
    end = int(time.time() * 1000); out = parse(fetch_remote(coin, interval, end - (n + 2) * STEP_MS[interval], end))
    return [c for c in out if c["t"] + STEP_MS[interval] <= end][-n:]
