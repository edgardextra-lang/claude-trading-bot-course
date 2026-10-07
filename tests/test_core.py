"""Tests written before the code: strategy signals, fee math, drawdown math, no look-ahead, dry-run safety."""
import json, math, pytest
from bot import data, strategy, backtest, metrics, runner, monitor, breakout, rsi_dip


def candle(t, o, h, l, c): return {"t": t * 3600_000, "o": o, "h": h, "l": l, "c": c, "v": 1.0}
def flat(n, px=100.0, t0=0): return [candle(t0 + i, px, px, px, px) for i in range(n)]
def ramp(n, a, b, t0=0):
    out = []
    for i in range(n):
        o = a + (b - a) * i / n; c = a + (b - a) * (i + 1) / n; out.append(candle(t0 + i, o, max(o, c), min(o, c), c))
    return out


# ---- data ----
def test_parse_converts_strings_and_sorts():
    raw = [{"t": 2, "o": "2", "h": "3", "l": "1", "c": "2.5", "v": "9"}, {"t": 1, "o": "1", "h": "2", "l": "0.5", "c": "1.5", "v": "4"}]
    out = data.parse(raw); assert [c["t"] for c in out] == [1, 2] and out[0]["c"] == 1.5 and isinstance(out[1]["h"], float)

def test_parse_drops_duplicates():
    raw = [{"t": 1, "o": "1", "h": "1", "l": "1", "c": "1", "v": "1"}] * 3; assert len(data.parse(raw)) == 1

def test_fetch_uses_cache_and_never_refetches(tmp_path):
    calls = []
    def fake(coin, interval, start, end): calls.append(1); return [{"t": 5, "o": "1", "h": "1", "l": "1", "c": "1", "v": "1"}]
    a = data.candles("BTC", "1h", 0, 10, cache_dir=tmp_path, fetch=fake); b = data.candles("BTC", "1h", 0, 10, cache_dir=tmp_path, fetch=fake)
    assert a == b and len(calls) == 1


# ---- indicators and strategy ----
def test_ema_of_constant_is_constant():
    assert strategy.ema([5.0] * 50, 20)[-1] == pytest.approx(5.0)

def test_atr_of_flat_market_is_zero():
    assert strategy.atr(flat(30), 14)[-1] == pytest.approx(0.0)

def test_no_signal_without_enough_history():
    assert strategy.signal(flat(50), None) is None

def test_no_buy_in_a_downtrend():
    cs = ramp(300, 200, 100); last = cs[-1]["c"]
    cs.append(candle(300, last, last + 20, last, last + 18))      # a sharp bounce back above the fast average, but the trend is down
    assert cs[-1]["c"] > strategy.indicators(cs)["fast"][-1] and strategy.signal(cs, None) is None

def test_buy_on_pullback_recovery_in_an_uptrend():
    cs = ramp(260, 100, 200)                       # steady uptrend
    last = cs[-1]["c"]; t = 260
    for k in range(6): cs.append(candle(t + k, last - k * 2.0, last - k * 2.0, last - (k + 1) * 2.0 - 0.5, last - (k + 1) * 2.0))   # pullback below the fast average
    assert strategy.signal(cs, None) is None       # still falling: no entry
    low = cs[-1]["c"]; cs.append(candle(t + 6, low, low + 14, low, low + 13))                                                      # closes back above the fast average
    s = strategy.signal(cs, None); assert s and s["action"] == "buy" and s["stop"] < cs[-1]["c"]

def test_sell_when_trend_breaks():
    cs = ramp(260, 100, 200) + ramp(80, 200, 120, t0=260)
    pos = {"entry": 190.0, "stop": 150.0}
    s = strategy.signal(cs, pos); assert s and s["action"] == "sell"

def test_results_do_not_change_when_later_candles_are_added():
    cs = ramp(260, 100, 200) + ramp(40, 200, 170, t0=260) + ramp(60, 170, 230, t0=300) + ramp(60, 230, 150, t0=360)
    full = backtest.run(cs)["equity"]
    for k in (270, 310, 380):
        assert backtest.run(cs[:k])["equity"] == pytest.approx(full[:k])      # the past cannot depend on the future


# ---- backtest ----
def test_fee_math_on_one_round_trip():
    # buy 1000 of notional at 100, sell at 110: gross +100, fees 0.05% on each side
    pnl = backtest.trade_pnl(entry=100.0, exit=110.0, notional=1000.0, fee=0.0005)
    assert pnl == pytest.approx(100.0 - 1000.0 * 0.0005 - 1100.0 * 0.0005)

def test_flat_market_makes_no_trades():
    r = backtest.run(flat(400)); assert r["trades"] == [] and r["equity"][-1] == pytest.approx(r["start"])

def test_fees_reduce_the_result():
    cs = ramp(260, 100, 200)
    last = cs[-1]["c"]
    for k in range(6): cs.append(candle(260 + k, last - k * 2.0, last - k * 2.0, last - (k + 1) * 2.0 - 0.5, last - (k + 1) * 2.0))
    low = cs[-1]["c"]; cs.append(candle(266, low, low + 14, low, low + 13)); cs += ramp(120, cs[-1]["c"], cs[-1]["c"] + 60, t0=267) + ramp(120, cs[-1]["c"] + 60, 120, t0=387)
    free = backtest.run(cs, fee=0.0, slippage=0.0); paid = backtest.run(cs, fee=0.001, slippage=0.0005)
    assert len(free["trades"]) >= 1 and paid["equity"][-1] < free["equity"][-1]

def test_entry_fills_on_the_next_candle_open_not_the_signal_close():
    cs = ramp(260, 100, 200); last = cs[-1]["c"]
    for k in range(6): cs.append(candle(260 + k, last - k * 2.0, last - k * 2.0, last - (k + 1) * 2.0 - 0.5, last - (k + 1) * 2.0))
    low = cs[-1]["c"]; cs.append(candle(266, low, low + 14, low, low + 13)); nxt = cs[-1]["c"] + 3.0; cs.append(candle(267, nxt, nxt + 1, nxt - 1, nxt)); cs += flat(5, nxt, t0=268)
    r = backtest.run(cs, fee=0.0, slippage=0.0, close_at_end=True); assert r["trades"][0]["entry"] == pytest.approx(nxt)

def test_stop_exits_inside_the_candle():
    cs = ramp(260, 100, 200); last = cs[-1]["c"]
    for k in range(6): cs.append(candle(260 + k, last - k * 2.0, last - k * 2.0, last - (k + 1) * 2.0 - 0.5, last - (k + 1) * 2.0))
    low = cs[-1]["c"]; cs.append(candle(266, low, low + 14, low, low + 13)); e = cs[-1]["c"]; cs.append(candle(267, e, e, e, e)); cs.append(candle(268, e, e, e - 80, e - 70))
    r = backtest.run(cs, fee=0.0, slippage=0.0); t = r["trades"][0]; assert t["reason"] == "stop" and t["exit"] == pytest.approx(t["stop"])


# ---- metrics ----
def test_max_drawdown():
    assert metrics.max_drawdown([100, 120, 90, 110, 130, 104]) == pytest.approx(-0.25)

def test_max_drawdown_of_rising_curve_is_zero():
    assert metrics.max_drawdown([1, 2, 3]) == 0.0

def test_average_daily_return_is_total_over_days():
    assert metrics.avg_daily_return(total_return=0.10, days=50) == pytest.approx(0.002)

def test_capital_needed_for_a_daily_target():
    assert metrics.capital_for_target(target_per_day=100, avg_daily_return=0.002) == pytest.approx(50_000)
    assert metrics.capital_for_target(100, 0.0) is None and metrics.capital_for_target(100, -0.001) is None

def test_summary_counts_wins_and_profit_factor():
    s = metrics.summary(start=1000.0, equity=[1000, 1010, 1005, 1030], trades=[{"pnl": 10}, {"pnl": -5}, {"pnl": 25}], days=10)
    assert s["trades"] == 3 and s["wins"] == 2 and s["profit_factor"] == pytest.approx(35 / 5) and s["total_return"] == pytest.approx(0.03)


# ---- runner and monitor ----
def test_dry_run_never_sends_an_order(tmp_path):
    sent = []
    cs = ramp(260, 100, 200); last = cs[-1]["c"]
    for k in range(6): cs.append(candle(260 + k, last - k * 2.0, last - k * 2.0, last - (k + 1) * 2.0 - 0.5, last - (k + 1) * 2.0))
    low = cs[-1]["c"]; cs.append(candle(266, low, low + 14, low, low + 13))
    out = runner.step(cs, state={}, coin="BTC", size_usd=50.0, live=False, send=lambda *a, **k: sent.append(a), log=tmp_path / "log.jsonl")
    assert out["action"] == "buy" and out["sent"] is False and sent == []
    assert json.loads((tmp_path / "log.jsonl").read_text().splitlines()[-1])["mode"] == "dry-run"

def test_live_needs_an_explicit_flag_and_a_key(monkeypatch):
    monkeypatch.delenv("HL_PRIVATE_KEY", raising=False)
    with pytest.raises(SystemExit): runner.require_key(live=True)
    assert runner.require_key(live=False) is None

def test_monitor_reads_the_log(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in [{"ts": 0, "equity": 1000.0}, {"ts": 86400, "equity": 1100.0}, {"ts": 172800, "equity": 990.0}, {"ts": 259200, "equity": 1050.0}]))
    s = monitor.stats(p); assert s["days"] == pytest.approx(3.0) and s["total_return"] == pytest.approx(0.05) and s["max_drawdown"] == pytest.approx(-0.1) and s["avg_daily_return"] == pytest.approx(0.05 / 3)


def setup_long(extra):
    cs = ramp(260, 100, 200); last = cs[-1]["c"]
    for k in range(6): cs.append(candle(260 + k, last - k * 2.0, last - k * 2.0, last - (k + 1) * 2.0 - 0.5, last - (k + 1) * 2.0))
    low = cs[-1]["c"]; cs.append(candle(266, low, low + 14, low, low + 13)); return cs + extra(cs[-1]["c"])

def test_a_gap_below_the_stop_fills_at_the_open_not_the_stop():
    cs = setup_long(lambda e: [candle(267, e, e, e, e), candle(268, e - 60, e - 60, e - 70, e - 65)])
    t = backtest.run(cs, fee=0.0, slippage=0.0)["trades"][0]; assert t["reason"] == "stop" and t["exit"] == pytest.approx(cs[-1]["o"]) and t["exit"] < t["stop"]

def test_slippage_makes_entries_dearer_and_exits_cheaper():
    cs = setup_long(lambda e: [candle(267, e, e, e, e)] + flat(5, e, t0=268))
    t = backtest.run(cs, fee=0.0, slippage=0.01, close_at_end=True)["trades"][0]; assert t["entry"] == pytest.approx(cs[267]["o"] * 1.01) and t["exit"] == pytest.approx(cs[-1]["c"] * 0.99)

def test_runner_sells_at_the_stop_and_books_the_loss(tmp_path):
    cs = setup_long(lambda e: []); state = {}; log = tmp_path / "l.jsonl"
    runner.step(cs, state, "BTC", 100.0, False, None, log); entry = state["pos"]["entry"]; stop = state["pos"]["stop"]
    cs.append(candle(267, entry, entry, stop - 5, stop - 4)); out = runner.step(cs, state, "BTC", 100.0, False, None, log)
    assert out["action"] == "sell" and state["pos"] is None and state["equity"] == pytest.approx(100.0 * (1 + (stop - 4) / entry - 1))

def test_a_rejected_live_order_changes_nothing(tmp_path):
    cs = setup_long(lambda e: []); state = {}
    out = runner.step(cs, state, "BTC", 100.0, True, lambda *a: {"status": "ok", "response": {"data": {"statuses": [{"error": "too small"}]}}}, tmp_path / "l.jsonl")
    assert out == {"action": "hold", "sent": False} and not state.get("pos")
    out = runner.step(cs, state, "BTC", 100.0, True, lambda *a: {"status": "ok", "response": {"data": {"statuses": [{"filled": {}}]}}}, tmp_path / "l.jsonl")
    assert out == {"action": "buy", "sent": True} and state["pos"]

def test_mainnet_needs_its_own_confirmation(monkeypatch):
    monkeypatch.setenv("HL_PRIVATE_KEY", "x"); monkeypatch.delenv("HL_ALLOW_MAINNET", raising=False)
    with pytest.raises(SystemExit): runner.require_key(live=True, mainnet=True)
    monkeypatch.setenv("HL_ALLOW_MAINNET", "1"); assert runner.require_key(live=True, mainnet=True) == "x"

def test_state_survives_a_restart(tmp_path):
    runner.save_state(tmp_path / "s.json", {"pos": {"entry": 1.0, "stop": 0.9, "size_usd": 5.0}, "equity": 5.0}); assert runner.load_state(tmp_path / "s.json")["pos"]["stop"] == 0.9

def test_cache_refuses_odd_coin_names(tmp_path):
    with pytest.raises(ValueError): data.candles("../x", "1h", 0, 10, cache_dir=tmp_path, fetch=lambda *a: [])


# ---- the two extra rules ----
def test_breakout_buys_a_new_high_and_ignores_a_range():
    cs = flat(260, 100.0); assert breakout.decide(259, cs, breakout.indicators(cs), None) is None
    cs.append(candle(260, 100, 106, 100, 105)); s = breakout.decide(260, cs, breakout.indicators(cs), None); assert s["action"] == "buy" and s["stop"] < 105

def test_breakout_window_does_not_include_the_current_candle():
    cs = flat(260, 100.0) + [candle(260, 100, 106, 100, 105)]; assert breakout.indicators(cs)["hi"][260] == 100.0

def test_breakout_sells_a_new_low():
    cs = flat(260, 100.0) + [candle(260, 100, 100, 93, 94)]; assert breakout.decide(260, cs, breakout.indicators(cs), {"entry": 100, "stop": 80})["action"] == "sell"

def test_rsi_is_high_after_gains_and_low_after_losses():
    assert rsi_dip.rsi([float(x) for x in range(1, 40)], 14)[-1] == 100.0 and rsi_dip.rsi([float(x) for x in range(40, 1, -1)], 14)[-1] == pytest.approx(0.0)

def test_rsi_rule_buys_oversold_and_sells_the_bounce():
    cs = flat(220, 100.0) + ramp(20, 100, 70, t0=220); i = len(cs) - 1; s = rsi_dip.decide(i, cs, rsi_dip.indicators(cs), None); assert s["action"] == "buy"
    cs += ramp(20, 70, 95, t0=240); i = len(cs) - 1; assert rsi_dip.decide(i, cs, rsi_dip.indicators(cs), {"entry": 70, "stop": 50})["action"] == "sell"

def test_every_rule_is_free_of_look_ahead():
    cs = ramp(260, 100, 200) + ramp(40, 200, 150, t0=260) + ramp(60, 150, 240, t0=300) + ramp(60, 240, 140, t0=360)
    for rule in (strategy, breakout, rsi_dip):
        full = backtest.run(cs, rule=rule)["equity"]
        for k in (270, 320, 390): assert backtest.run(cs[:k], rule=rule)["equity"] == pytest.approx(full[:k])
