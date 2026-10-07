"""One rule, in plain words:

BUY  when the market is in an uptrend (price above its 200-candle average, and the 50 above the 200)
     and price dips below its 20-candle average, then closes back above it.
STOP two average candle ranges (ATR) below the entry.
SELL when price closes below its 50-candle average.

Long only. One position at a time. Decisions use closed candles only.
"""
FAST, MID, SLOW, ATR_N, ATR_MULT = 20, 50, 200, 14, 2.0
WARM = SLOW + 5       # the rule cannot trade before this candle


def ema(values, n):
    k, out, e = 2 / (n + 1), [], None
    for v in values:
        e = v if e is None else v * k + e * (1 - k); out.append(e)
    return out


def atr(candles, n):
    out, prev, a = [], None, None
    for c in candles:
        tr = c["h"] - c["l"] if prev is None else max(c["h"] - c["l"], abs(c["h"] - prev), abs(c["l"] - prev))
        a = tr if a is None else (a * (n - 1) + tr) / n; out.append(a); prev = c["c"]
    return out


def indicators(candles):
    closes = [c["c"] for c in candles]
    return {"fast": ema(closes, FAST), "mid": ema(closes, MID), "slow": ema(closes, SLOW), "atr": atr(candles, ATR_N)}


def decide(i, candles, ind, position):
    """The decision at the close of candle i. Looks at candles 0..i only."""
    if i < SLOW + 5: return None
    c, prev = candles[i]["c"], candles[i - 1]["c"]
    if position:
        return {"action": "sell", "reason": "trend"} if c < ind["mid"][i] else None
    uptrend = c > ind["slow"][i] and ind["mid"][i] > ind["slow"][i]
    recovered = prev < ind["fast"][i - 1] and c > ind["fast"][i]
    if uptrend and recovered:
        risk = ATR_MULT * ind["atr"][i] or c * 0.02
        return {"action": "buy", "stop": c - risk}
    return None


def signal(candles, position):
    """Convenience for the live runner: the decision at the last closed candle."""
    if len(candles) < SLOW + 6: return None
    return decide(len(candles) - 1, candles, indicators(candles), position)
