# Claude Code trading bot (course repo)

A small, readable trading bot built step by step with Claude Code, for the CryptoEddy course video.
It is a teaching project. **The rule in this repo does not have an edge, and the results below show it.** That is the point of the course: build it, test it honestly, and learn to tell a working strategy from a story.

Not financial advice. Past results predict nothing. Leverage can lose everything.

## The rule

- **Buy** when the market is in an uptrend (price above its 200-candle average, and the 50 above the 200), price dips below its 20-candle average, then closes back above it.
- **Stop** two average candle ranges (ATR) below the entry.
- **Sell** when price closes below its 50-candle average.

Long only, one position at a time, decisions on closed candles, fills on the next candle's open.

## What the test says

Same rule, untouched, on eight coins. Hyperliquid candles, fees 0.045% per side plus 0.02% slippage, run on 7 Oct 2026. The first 205 candles only warm up the averages; results and buy-and-hold are both measured after them.

**1-hour candles, 196 days measured**

| Coin | Return | Without fees | Max drawdown | Trades | Buy and hold |
|---|---|---|---|---|---|
| BTC | -4.5% | +8.5% | -21.7% | 98 | +22.1% |
| ETH | -21.2% | -7.6% | -29.0% | 123 | +26.2% |
| SOL | +8.3% | +23.0% | -14.6% | 98 | +34.3% |
| HYPE | +26.9% | +44.1% | -30.3% | 98 | +139.0% |
| XRP | -26.5% | -19.1% | -31.8% | 74 | +6.7% |
| DOGE | -25.0% | -17.1% | -27.7% | 76 | +0.1% |
| SUI | +6.9% | +17.0% | -36.0% | 70 | +25.4% |
| AVAX | -29.0% | -21.2% | -32.8% | 80 | +22.8% |

Profitable on 3 of 8 coins, average -8.0%. It lost to simply holding on all 8.

**4-hour candles, 786 days measured (HYPE: 636 days, it has less history):** profitable on 6 of 8, average +11.8%, with drawdowns between -23% and -70%. On 4 of the 8 coins the first and second half of the period point in opposite directions.

## Two more rules, same test

The course then tests two more popular ideas with the same command (`python -m bot.robustness 1h 205 breakout`, or `rsi`).

| Rule | 1-hour: profitable coins, average | 4-hour: profitable coins, average | What breaks it |
|---|---|---|---|
| Pullback (above) | 3 of 8, -8.0% | 6 of 8, +11.8% | Loses to holding on all 8 at 1h; drawdowns to -70% at 4h |
| Breakout (20-candle high) | 5 of 8, +21.2% | 3 of 8, +27.5% | 7 of 8 coins flat or negative in the first half at 1h; at 4h one coin (XRP +264%) carries the average, which is -6.2% without it |
| RSI dip-buy (below 30) | 4 of 8, +2.7% | 3 of 8, +10.9% | Wins about 60% of trades yet loses to holding on 6 of 8; at 4h the two halves flip on 7 of 8 coins |
| Golden cross (50 over 200) | 5 of 8, +12.9% | 8 of 8, +159.0% | Only 7 to 17 trades per coin (97 in all); two trades make 66% to 97% of each coin's gains; alpha score 0.9 to 1.9, below the 2 that would separate skill from simply being long in a rising market |

The first three fail. The golden cross is the only one worth studying further, and it is **not proven**: the sample is small, the eight coins moved together, and its drawdowns reach -64%. Each rule has one table, coin or number that would make a convincing advert (`python -m bot.robustness 4h 820 cross`).

## The overfitting experiment

`python -m bot.tune 4h 820` tries 27 settings of the pullback rule on the first half of the history and then runs them on the second half.

- 4-hour candles: all 27 settings made money on the first half (best +67.2%). On the second half, 0 of 27 did, and the "best" one returned -7.2%.
- 1-hour candles: 9 of 27 were profitable on the first half, 2 of 27 on the second. The first-half winner ranked 20th of 27 afterwards.

Tuning found the settings that best described the past, not a better strategy.

What to take from it:
1. Fees turn a small gain into a loss (BTC 1h: +8.5% before fees, -4.5% after).
2. A result on one coin or one timeframe means little. Run the same rule everywhere before believing it.
3. A drawdown of -30% to -70% is not survivable for most people, whatever the final number.

Reproduce it: `python -m bot.robustness 1h 205` and `python -m bot.robustness 4h 820`. Your numbers will differ as new candles arrive.

## Run it

```bash
python -m pytest -q                      # 39 tests
python -m bot.robustness                 # the table above
python -m bot.runner --coin BTC --once   # dry-run: logs what it would do, sends nothing
python -m bot.monitor runs/log_BTC_dry.jsonl
```

Live modes exist for the course and are off by default. Copy `.env.example` to `.env` and fill it in; the runner reads that file, so the key never passes through your shell history.

```bash
pip install -r requirements.txt                   # only needed for --live, in a virtual environment
python -m bot.runner --coin BTC --live            # Hyperliquid TESTNET
python -m bot.runner --coin BTC --live --mainnet  # real money; also needs HL_ALLOW_MAINNET=1 in .env
```

Before real money, know what this bot does not do:
- **No stop order sits on the exchange.** The stop is checked once per closed candle. A fast move between candles is not protected.
- **Signals come from mainnet prices,** also in testnet mode.
- **Paper equity in the log ignores fees** and fills at the candle close, so the monitor flatters the result a little compared with the backtest.
- Use a trade-only API wallet as `HL_PRIVATE_KEY` and your main account as `HL_ACCOUNT_ADDRESS`, so the key on your machine cannot withdraw. Order size is capped at $1,000.
- And the rule has not passed the test above. Going live with it is paying to learn.

## Layout

`bot/data.py` price history · `bot/strategy.py` the rule · `bot/breakout.py`, `bot/rsi_dip.py`, `bot/ma_cross.py` three more rules · `bot/tune.py` the overfitting experiment · `bot/backtest.py` replay with fees · `bot/metrics.py` return, drawdown, capital for a daily target · `bot/robustness.py` the honest test · `bot/runner.py` dry-run and live · `bot/monitor.py` the two numbers to watch · `tests/` 39 tests.

MIT licence.
