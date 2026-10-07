"""A third rule for the course, in plain words:

BUY  when the 14-candle RSI closes below 30 (the market looks oversold).
STOP three average candle ranges (ATR) below the entry.
SELL when the RSI closes back above 55.

Long only. One position at a time. Decisions use closed candles only.
"""
from .strategy import atr

RSI_N, BUY_BELOW, SELL_ABOVE, ATR_N, ATR_MULT = 14, 30.0, 55.0, 14, 3.0
WARM = 205


def rsi(closes, n):
    out, up, dn = [50.0], None, None
    for a, b in zip(closes, closes[1:]):
        g, l = max(b - a, 0.0), max(a - b, 0.0)
        up = g if up is None else (up * (n - 1) + g) / n; dn = l if dn is None else (dn * (n - 1) + l) / n
        out.append(100.0 if dn == 0 and up > 0 else 50.0 if dn == 0 else 100 - 100 / (1 + up / dn))
    return out


def indicators(candles):
    return {"rsi": rsi([c["c"] for c in candles], RSI_N), "atr": atr(candles, ATR_N)}


def decide(i, candles, ind, position):
    if i < WARM: return None
    c, r = candles[i]["c"], ind["rsi"][i]
    if position: return {"action": "sell", "reason": "target"} if r > SELL_ABOVE else None
    if r < BUY_BELOW: return {"action": "buy", "stop": c - (ATR_MULT * ind["atr"][i] or c * 0.02)}
    return None
