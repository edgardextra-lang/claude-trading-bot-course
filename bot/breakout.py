"""A second rule for the course, in plain words:

BUY  when price closes above the highest high of the previous 20 candles (a breakout).
STOP two average candle ranges (ATR) below the entry.
SELL when price closes below the lowest low of the previous 10 candles.

Long only. One position at a time. Decisions use closed candles only.
"""
from .strategy import atr

ENTRY_N, EXIT_N, ATR_N, ATR_MULT = 20, 10, 14, 2.0
WARM = 205           # same warm-up as the first rule, so every rule is measured over the same days


def indicators(candles):
    hi, lo = [], []
    for i in range(len(candles)):
        hi.append(max(c["h"] for c in candles[max(0, i - ENTRY_N):i]) if i else candles[0]["h"])      # the window ends BEFORE candle i
        lo.append(min(c["l"] for c in candles[max(0, i - EXIT_N):i]) if i else candles[0]["l"])
    return {"hi": hi, "lo": lo, "atr": atr(candles, ATR_N)}


def decide(i, candles, ind, position):
    if i < WARM: return None
    c = candles[i]["c"]
    if position: return {"action": "sell", "reason": "trend"} if c < ind["lo"][i] else None
    if c > ind["hi"][i]: return {"action": "buy", "stop": c - (ATR_MULT * ind["atr"][i] or c * 0.02)}
    return None
