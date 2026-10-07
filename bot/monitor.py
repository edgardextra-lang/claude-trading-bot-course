"""Reads the runner's log and reports the two numbers to watch: average daily return and biggest drawdown."""
import json, sys
from pathlib import Path
from . import metrics


def stats(path):
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]; rows = [r for r in rows if "equity" in r]
    eq = [r["equity"] for r in rows]; days = (rows[-1]["ts"] - rows[0]["ts"]) / 86400; total = eq[-1] / eq[0] - 1
    return {"days": days, "total_return": total, "max_drawdown": metrics.max_drawdown(eq), "avg_daily_return": metrics.avg_daily_return(total, days)}


if __name__ == "__main__":
    s = stats(sys.argv[1] if len(sys.argv) > 1 else "runs/log.jsonl")
    print(f"days {s['days']:.1f} | return {s['total_return']:+.2%} | avg per day {s['avg_daily_return']:+.3%} | max drawdown {s['max_drawdown']:.2%}")
