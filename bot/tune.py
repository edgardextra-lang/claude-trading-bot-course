"""The overfitting experiment. Try many settings of the pullback rule on the FIRST half of the history,
keep the best, then see what that "best" does on the SECOND half, which it has never seen.

  python -m bot.tune 1h 205
"""
import itertools, json, sys, time
from pathlib import Path
from types import SimpleNamespace
from . import data, backtest, strategy
from .robustness import COINS, WARM


def pullback(fast, mid, mult, slow=200):
    """The pullback rule with other settings. Same logic as strategy.py."""
    def indicators(candles):
        closes = [c["c"] for c in candles]
        return {"fast": strategy.ema(closes, fast), "mid": strategy.ema(closes, mid), "slow": strategy.ema(closes, slow), "atr": strategy.atr(candles, 14)}
    def decide(i, candles, ind, position):
        if i < WARM: return None
        c, prev = candles[i]["c"], candles[i - 1]["c"]
        if position: return {"action": "sell", "reason": "trend"} if c < ind["mid"][i] else None
        if c > ind["slow"][i] and ind["mid"][i] > ind["slow"][i] and prev < ind["fast"][i - 1] and c > ind["fast"][i]:
            return {"action": "buy", "stop": c - (mult * ind["atr"][i] or c * 0.02)}
        return None
    return SimpleNamespace(indicators=indicators, decide=decide, WARM=WARM)


def ret(candles, rule):
    r = backtest.run(candles, close_at_end=True, rule=rule); return r["equity"][-1] / r["start"] - 1


GRID = list(itertools.product([10, 20, 30], [30, 50, 80], [1.5, 2.0, 3.0]))        # 27 combinations of fast, middle, stop


def experiment(interval="1h", days=205, coins=COINS, end_ms=None):
    end = end_ms or int(time.time() // 86400 * 86400 * 1000) - 1; start = end - days * 86_400_000; sets = {}
    for coin in coins:
        cs = data.candles(coin, interval, start, end); half = (len(cs) + WARM) // 2; sets[coin] = (cs[:half], cs[half - WARM:])
    avg = lambda vals: sum(vals) / len(vals); rows = []
    for g in GRID:
        rule = pullback(*g); rows.append({"params": g, "first": avg([ret(a, rule) for a, _ in sets.values()]), "second": avg([ret(b, rule) for _, b in sets.values()])})
    rows.sort(key=lambda r: -r["first"]); default = next(r for r in rows if r["params"] == (20, 50, 2.0))
    return {"interval": interval, "tested": len(rows), "best_on_first_half": rows[0], "default": default, "rank_of_best_on_second_half": 1 + sorted(rows, key=lambda r: -r["second"]).index(rows[0]),
            "profitable_first": sum(1 for r in rows if r["first"] > 0), "profitable_second": sum(1 for r in rows if r["second"] > 0), "rows": rows}


if __name__ == "__main__":
    t = experiment(sys.argv[1] if len(sys.argv) > 1 else "1h", int(sys.argv[2]) if len(sys.argv) > 2 else 205)
    Path("runs").mkdir(exist_ok=True); Path(f"runs/tune_{t['interval']}.json").write_text(json.dumps(t, indent=1)); b, d = t["best_on_first_half"], t["default"]
    print(f"{t['tested']} settings tried, average over 8 coins")
    print(f"best on the first half: fast {b['params'][0]}, middle {b['params'][1]}, stop {b['params'][2]}  ->  first half {b['first']:+.1%}, second half {b['second']:+.1%} (rank {t['rank_of_best_on_second_half']} of {t['tested']} on the second half)")
    print(f"our original settings:  first half {d['first']:+.1%}, second half {d['second']:+.1%}")
    print(f"settings profitable on the first half: {t['profitable_first']} of {t['tested']} | on the second half: {t['profitable_second']} of {t['tested']}")
