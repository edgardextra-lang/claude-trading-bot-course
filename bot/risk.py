"""The risk chapter: the same golden-cross trades, changing only how much is bet, then a kill switch, then funding.

  python -m bot.risk 4h 820
"""
import json, sys, time
from pathlib import Path
from . import data, backtest, metrics, ma_cross
from .robustness import COINS, WARM


def run_all(sets, **kw):
    rows = []
    for coin, (cs, fund) in sets.items():
        r = backtest.run(cs, close_at_end=True, rule=ma_cross, funding=fund if kw.pop("use_funding", False) else None, **kw); eq = r["equity"][WARM:]
        rows.append({"coin": coin, "ret": eq[-1] / r["start"] - 1, "dd": metrics.max_drawdown(eq), "halted": r["halted"], "funding": r["funding_paid"] / r["start"]}); kw = dict(kw)
    return rows


def experiment(interval="4h", days=820, coins=COINS, end_ms=None):
    end = end_ms or int(time.time() // 86400 * 86400 * 1000) - 1; start = end - days * 86_400_000; sets = {}
    for coin in coins:
        cs = data.candles(coin, interval, start, end); rates = data.funding(coin, cs[0]["t"], end); sets[coin] = (cs, data.funding_per_candle(cs, rates, data.STEP_MS[interval]))
    avg = lambda rows, k: sum(r[k] for r in rows) / len(rows); worst = lambda rows: min(r["dd"] for r in rows)
    out = {"interval": interval, "variants": []}
    for name, kw in [("whole account", {}), ("risk 2%", {"risk": 0.02}), ("risk 1%", {"risk": 0.01}), ("risk 0.5%", {"risk": 0.005}), ("whole account + kill switch at -25%", {"halt_dd": 0.25}), ("risk 1% + kill switch at -10%", {"risk": 0.01, "halt_dd": 0.10})]:
        rows = run_all(sets, **kw); out["variants"].append({"name": name, "avg_return": avg(rows, "ret"), "avg_dd": avg(rows, "dd"), "worst_dd": worst(rows), "halted_on": sum(1 for r in rows if r["halted"]), "rows": rows})
    base = run_all(sets); withf = []
    for coin, (cs, fund) in sets.items():
        r = backtest.run(cs, close_at_end=True, rule=ma_cross, funding=fund); withf.append({"coin": coin, "ret": r["equity"][-1] / r["start"] - 1, "funding": r["funding_paid"] / r["start"]})
    out["funding"] = {"avg_without": avg(base, "ret"), "avg_with": avg(withf, "ret"), "rows": [{"coin": a["coin"], "without": a["ret"], "with": b["ret"], "paid": b["funding"]} for a, b in zip(base, withf)]}
    return out


if __name__ == "__main__":
    t = experiment(sys.argv[1] if len(sys.argv) > 1 else "4h", int(sys.argv[2]) if len(sys.argv) > 2 else 820); Path("runs").mkdir(exist_ok=True); Path(f"runs/risk_{t['interval']}.json").write_text(json.dumps(t, indent=1))
    print(f"{'variant':40} {'avg return':>11} {'avg drawdown':>13} {'worst drawdown':>15} {'switched off on':>16}")
    for v in t["variants"]: print(f"{v['name']:40} {v['avg_return']:>+11.1%} {v['avg_dd']:>13.1%} {v['worst_dd']:>15.1%} {v['halted_on']:>12} of 8")
    f = t["funding"]; print(f"\nfunding: average return {f['avg_without']:+.1%} without, {f['avg_with']:+.1%} with")
    for r in f["rows"]: print(f"  {r['coin']:5} {r['without']:+8.1%} -> {r['with']:+8.1%}   funding paid {r['paid']:+.1%} of the starting account")
