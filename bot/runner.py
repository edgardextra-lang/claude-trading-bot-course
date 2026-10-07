"""Runs the rule on live prices. DRY-RUN BY DEFAULT: it only logs what it would do.

  python -m bot.runner --coin BTC                      dry-run, no key, no orders
  python -m bot.runner --coin BTC --live               real orders on TESTNET (key from .env)
  python -m bot.runner --coin BTC --live --mainnet     real money; also needs HL_ALLOW_MAINNET=1 in .env

Know the limits before going live:
- The stop is checked once per closed candle. No stop order sits on the exchange between candles.
- Signals always come from mainnet prices, also in testnet mode.
- Paper equity in the log ignores fees and fills at the candle close, so it flatters the result a little.
"""
import argparse, json, os, re, sys, time
from pathlib import Path
from . import data, strategy

MAX_SIZE_USD = 1000.0


def load_env(path=".env"):
    """Read KEY=value lines from .env so the key never has to be typed into the shell (and its history)."""
    p = Path(path)
    if not p.exists(): return
    for line in p.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())


def require_key(live, mainnet=False):
    if not live: return None
    key = os.environ.get("HL_PRIVATE_KEY")
    if not key: raise SystemExit("--live needs HL_PRIVATE_KEY in .env. Never commit that file.")
    if mainnet and os.environ.get("HL_ALLOW_MAINNET") != "1": raise SystemExit("--mainnet also needs HL_ALLOW_MAINNET=1 in .env. That line is your confirmation that this is real money.")
    return key


def filled(resp):
    """True only when the exchange accepted the order. The SDK reports rejections in the response instead of raising."""
    if not isinstance(resp, dict) or resp.get("status") != "ok": return False
    statuses = (((resp.get("response") or {}).get("data") or {}).get("statuses")) or []
    return not any(isinstance(s, dict) and "error" in s for s in statuses)


def step(candles, state, coin, size_usd, live, send, log):
    """One decision at the last closed candle. Sends an order only when live is True; always writes a log line."""
    last = candles[-1]; price = last["c"]; pos = state.get("pos"); sent = False
    sig = strategy.signal(candles, pos)
    if pos and last["l"] <= pos["stop"]: sig = {"action": "sell", "reason": "stop"}        # the stop, checked at the candle close
    if sig and live:
        sent = filled(send(coin, sig["action"], size_usd, price))
        if not sent: sig = None                                                              # rejected: nothing changed on the exchange
    eq = state.setdefault("equity", size_usd)
    if sig and sig["action"] == "sell" and pos: state["equity"] = eq = eq + pos["size_usd"] * (price / pos["entry"] - 1); state["pos"] = pos = None
    elif sig and sig["action"] == "buy": state["pos"] = pos = {"entry": price, "stop": sig["stop"], "size_usd": size_usd}
    paper = eq + (pos["size_usd"] * (price / pos["entry"] - 1) if pos else 0.0)
    row = {"ts": int(time.time()), "coin": coin, "price": price, "action": sig["action"] if sig else "hold", "reason": (sig or {}).get("reason", ""), "mode": "live" if live else "dry-run", "sent": sent, "equity": round(paper, 4)}
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as f: f.write(json.dumps(row) + "\n")
    return {"action": row["action"], "sent": sent}


def load_state(path):
    p = Path(path); return json.loads(p.read_text()) if p.exists() else {}

def save_state(path, state):
    tmp = Path(str(path) + ".tmp"); tmp.parent.mkdir(parents=True, exist_ok=True); tmp.write_text(json.dumps(state)); os.replace(tmp, path)


def exchange(key, mainnet):
    """Imported only for live runs, so a dry-run needs no extra packages."""
    import eth_account
    from hyperliquid.exchange import Exchange
    from hyperliquid.utils import constants
    account = os.environ.get("HL_ACCOUNT_ADDRESS") or None      # set this when HL_PRIVATE_KEY is a trade-only API wallet acting for your main account
    ex = Exchange(eth_account.Account.from_key(key), constants.MAINNET_API_URL if mainnet else constants.TESTNET_API_URL, account_address=account, timeout=15)
    return lambda coin, action, size_usd, price: ex.market_open(coin, True, round(size_usd / price, 4)) if action == "buy" else ex.market_close(coin)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--coin", default="BTC"); ap.add_argument("--interval", default="1h", choices=sorted(data.STEP_MS)); ap.add_argument("--size-usd", type=float, default=50.0)
    ap.add_argument("--live", action="store_true"); ap.add_argument("--mainnet", action="store_true"); ap.add_argument("--once", action="store_true"); a = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9]{1,12}", a.coin): sys.exit("--coin must be letters and digits only")
    if not 0 < a.size_usd <= MAX_SIZE_USD: sys.exit(f"--size-usd must be between 0 and {MAX_SIZE_USD:.0f}")
    if a.mainnet and not a.live: sys.exit("--mainnet only makes sense with --live")
    load_env(); key = require_key(a.live, a.mainnet); send = exchange(key, a.mainnet) if a.live else (lambda *x: None)
    mode = ("mainnet" if a.mainnet else "testnet") if a.live else "dry"; spath = f"runs/state_{a.coin}_{mode}.json"; log = f"runs/log_{a.coin}_{mode}.jsonl"; state = load_state(spath)
    print("mode:", "LIVE on " + ("MAINNET" if a.mainnet else "testnet") if a.live else "dry-run (no orders are sent)", "| position:", state.get("pos"))
    step_s = data.STEP_MS[a.interval] / 1000
    while True:
        try:
            out = step(data.recent(a.coin, a.interval), state, a.coin, a.size_usd, a.live, send, log); save_state(spath, state); print(time.strftime("%Y-%m-%d %H:%M"), a.coin, out)
        except Exception as e:                                   # a network error must not kill a bot that holds a position
            print(time.strftime("%Y-%m-%d %H:%M"), "error, will retry:", type(e).__name__, str(e)[:120])
        if a.once: break
        time.sleep(step_s - time.time() % step_s + 5)            # wake just after each candle closes


if __name__ == "__main__":
    main()
