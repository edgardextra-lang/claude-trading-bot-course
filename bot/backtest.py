"""Replays the rule over history. Fees and slippage are charged on every fill. Orders fill on the NEXT candle's open."""
from . import strategy

FEE, SLIPPAGE = 0.00045, 0.0002      # Hyperliquid taker fee per side, plus an allowance for slippage


def trade_pnl(entry, exit, notional, fee):
    qty = notional / entry
    return qty * (exit - entry) - notional * fee - qty * exit * fee


def run(candles, fee=FEE, slippage=SLIPPAGE, start=1000.0, close_at_end=False, rule=strategy):
    ind = rule.indicators(candles); cash, pos, pending = start, None, None; equity, trades = [], []

    def close(price, t, reason):
        nonlocal cash, pos
        px = price * (1 - slippage); pnl = trade_pnl(pos["entry"], px, pos["notional"], fee); cash += pnl
        trades.append({"t_in": pos["t"], "t_out": t, "entry": pos["entry"], "exit": px, "stop": pos["stop"], "pnl": pnl, "reason": reason}); pos = None

    for i, c in enumerate(candles):
        if pending:                                   # yesterday's decision fills at today's open
            if pending["action"] == "buy" and not pos:
                pos = {"entry": c["o"] * (1 + slippage), "stop": pending["stop"], "notional": cash, "t": c["t"]}
            elif pending["action"] == "sell" and pos:
                close(c["o"], c["t"], pending.get("reason", "trend"))
            pending = None
        if pos and c["l"] <= pos["stop"]:              # stop is hit inside the candle
            close(min(pos["stop"], c["o"]), c["t"], "stop")      # a gap below the stop fills at the open
        pending = rule.decide(i, candles, ind, pos)
        equity.append(cash + (trade_pnl(pos["entry"], c["c"], pos["notional"], 0.0) if pos else 0.0))
    if close_at_end and pos:
        close(candles[-1]["c"], candles[-1]["t"], "end"); equity[-1] = cash
    return {"start": start, "equity": equity, "trades": trades}
