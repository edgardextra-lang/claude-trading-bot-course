"""The numbers that matter: what it made, how bad it got, and what a daily target would really take."""


def max_drawdown(equity):
    peak, worst = equity[0], 0.0
    for v in equity:
        peak = max(peak, v); worst = min(worst, v / peak - 1)
    return worst


def avg_daily_return(total_return, days):
    return total_return / days if days else 0.0


def capital_for_target(target_per_day, avg_daily_return):
    """Target divided by average daily return. None when the average is not positive: no amount of capital fixes that."""
    return target_per_day / avg_daily_return if avg_daily_return > 0 else None


def summary(start, equity, trades, days):
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]; losses = [-t["pnl"] for t in trades if t["pnl"] <= 0]
    total = equity[-1] / start - 1
    return {"total_return": total, "max_drawdown": max_drawdown(equity), "avg_daily_return": avg_daily_return(total, days), "days": days,
            "trades": len(trades), "wins": len(wins), "profit_factor": (sum(wins) / sum(losses)) if losses and sum(losses) else None}
