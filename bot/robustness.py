"""The honest test: the SAME rule, untouched, on other coins and on two halves of the history.

  python -m bot.robustness                 prints the table and writes runs/robustness.json
"""
import json, sys, time
from pathlib import Path
from . import data, backtest, metrics, strategy

COINS = ["BTC", "ETH", "SOL", "HYPE", "XRP", "DOGE", "SUI", "AVAX"]


WARM = strategy.SLOW + 5          # the rule cannot trade before this candle, so nothing is measured before it


def one(candles, fee=backtest.FEE, slippage=backtest.SLIPPAGE):
    """Result over candles[WARM:]. The first WARM candles only warm up the averages."""
    r = backtest.run(candles, fee=fee, slippage=slippage, close_at_end=True); days = (candles[-1]["t"] - candles[WARM]["t"]) / 86_400_000
    s = metrics.summary(r["start"], r["equity"][WARM:], r["trades"], days); s["buy_hold"] = candles[-1]["c"] / candles[WARM]["c"] - 1; return s


def table(interval="1h", days=205, coins=COINS, end_ms=None):
    if interval not in data.STEP_MS: raise SystemExit(f"interval must be one of {sorted(data.STEP_MS)}")
    end = end_ms or int(time.time() // 86400 * 86400 * 1000) - 1; start = end - days * 86_400_000; rows = []
    for coin in coins:
        cs = data.candles(coin, interval, start, end)
        if len(cs) < 600: continue
        half = (len(cs) + WARM) // 2     # split the measured part in two; the second half gets its own warm-up from the candles before it
        rows.append({"coin": coin, "candles": len(cs), "days": round((cs[-1]["t"] - cs[WARM]["t"]) / 86_400_000), "all": one(cs), "no_fees": one(cs, 0.0, 0.0), "first_half": one(cs[:half]), "second_half": one(cs[half - WARM:])})
    return {"interval": interval, "start_ms": start, "end_ms": end, "rows": rows}


if __name__ == "__main__":
    t = table(interval=sys.argv[1] if len(sys.argv) > 1 else "1h", days=int(sys.argv[2]) if len(sys.argv) > 2 else 205)
    Path("runs").mkdir(exist_ok=True); Path(f"runs/robustness_{t['interval']}.json").write_text(json.dumps(t, indent=1))
    p = lambda v: f"{v:+7.1%}"
    print(f"{'coin':5} {'days':>5} {'return':>8} {'no fees':>8} {'max dd':>8} {'trades':>6} {'wins':>5} {'1st half':>9} {'2nd half':>9} {'buy+hold':>9}")
    for r in t["rows"]:
        a = r["all"]; print(f"{r['coin']:5} {r['days']:>5} {p(a['total_return']):>8} {p(r['no_fees']['total_return']):>8} {p(a['max_drawdown']):>8} {a['trades']:>6} {a['wins']:>5} {p(r['first_half']['total_return']):>9} {p(r['second_half']['total_return']):>9} {p(a['buy_hold']):>9}")
    tot = [r["all"]["total_return"] for r in t["rows"]]; print(f"profitable on {sum(1 for v in tot if v > 0)} of {len(tot)} coins | average {sum(tot) / len(tot):+.1%}")
