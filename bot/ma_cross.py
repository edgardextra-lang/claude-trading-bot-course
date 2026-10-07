"""A fourth rule for the course, the famous one, in plain words:

BUY  when the 50-candle average crosses above the 200-candle average (the "golden cross").
STOP three average candle ranges (ATR) below the entry.
SELL when the 50 crosses back below the 200.

Long only. One position at a time. Decisions use closed candles only.
"""
from .strategy import ema, atr

FAST, SLOW, ATR_N, ATR_MULT = 50, 200, 14, 3.0
WARM = 205


def indicators(candles):
    closes = [c["c"] for c in candles]
    return {"fast": ema(closes, FAST), "slow": ema(closes, SLOW), "atr": atr(candles, ATR_N)}


def decide(i, candles, ind, position):
    if i < WARM: return None
    above, was_above = ind["fast"][i] > ind["slow"][i], ind["fast"][i - 1] > ind["slow"][i - 1]
    if position: return {"action": "sell", "reason": "trend"} if not above else None
    if above and not was_above: return {"action": "buy", "stop": candles[i]["c"] - (ATR_MULT * ind["atr"][i] or candles[i]["c"] * 0.02)}
    return None
