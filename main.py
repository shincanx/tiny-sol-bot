"""Tiny SOL trend bot — make.fun bounty u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1.

Strategy (written for this bounty, hourly bars, 7 symbols, long-only).
Two legs, switched by the broad market (SOL's own trend), because the
final window is unseen and the dev window fell -8.7% while the final
one could rise instead:

  * MOMENTUM leg (SOL in a clear uptrend: fast EMA(8h) above a rising
    slow EMA(26h) and 24h return above +1%): ride the trend. Enter when
    a symbol's fast EMA is above its rising slow EMA, its close is above
    the slow EMA and its 24h return is above +1.5%; rank candidates by
    12h momentum and hold the top 4 at 25% of equity each (the harness
    cap), so the bot concentrates in the strongest names. Exit when the
    fast EMA crosses back below the slow EMA, the close falls under the
    slow EMA, 12h momentum turns below -2%, or the close drops 4% below
    the peak since entry.
  * SCALP leg (SOL flat or falling): mean-revert the chop instead of
    chasing bounces. Enter only when RSI(14) is below 30 AND the close
    ticked up from the previous bar — the first green bar after an
    oversold washout, not while the knife is still falling — at 20% of
    equity; exit at +1.5% from entry, at -2% (stop), when RSI rises
    above 55, or after 12 bars. In the falling dev window that entry
    averaged +0.57% over the next 6h (74% win) while plain RSI<32
    averaged +0.20% and momentum signals averaged -0.4% to -1.1% — so
    in a down market this leg keeps the bot near cash and slightly
    positive instead of bleeding like buy-and-hold (-869 USDC on dev).
  * Trades only on signal changes, so fees stay low (10 bps fee +
    5 bps slippage per fill, ~0.15% per round trip). Fully
    deterministic: no clock, no environment, no randomness; the only
    state is the close history and per-symbol entry peaks/prices.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

FAST = 8            # fast EMA span, hours
SLOW = 26           # slow EMA span, hours
MOM_WINDOW = 12     # momentum lookback, hours
TREND_WINDOW = 24   # entry momentum lookback, hours
RSI_LEN = 14
RSI_SELL = 55       # scalp exit: bounce faded / momentum back
MAX_HOLD = 4        # most symbols held at once
TARGET_BPS = 2500   # 25% of equity per symbol, momentum leg (harness cap)
SCALP_BPS = 2000    # 20% of equity per symbol, scalp leg
STOP_PCT = 0.04     # momentum trailing stop: 4% below peak since entry
SCALP_TP = 0.015    # scalp take profit: +1.5% from entry
SCALP_SL = 0.02     # scalp stop loss: -2% from entry
SCALP_MAX_BARS = 12  # scalp time stop
ENTRY_MOM = 0.015   # momentum entry: 24h return above 1.5%
EXIT_MOM = -0.02    # momentum exit: 12h momentum below -2%
SLIPPAGE_BPS = 100

closes = {}   # symbol -> list of closes (raw price units, ratios are scale-free)
peaks = {}    # symbol -> highest close seen while holding it (momentum leg)
entries = {}  # symbol -> (entry close, entry seq) for the scalp leg


def ema(values, span):
    k = 2.0 / (span + 1)
    out = float(values[0])
    for v in values[1:]:
        out = v * k + out * (1.0 - k)
    return out


def rsi(hist):
    if len(hist) < RSI_LEN + 1:
        return 50.0
    gains = 0.0
    losses = 0.0
    for i in range(1, RSI_LEN + 1):
        ch = hist[-i] - hist[-i - 1]
        if ch > 0:
            gains += ch
        else:
            losses -= ch
    if losses == 0:
        return 100.0
    if gains == 0:
        return 0.0
    return 100.0 - 100.0 / (1.0 + (gains / RSI_LEN) / (losses / RSI_LEN))


def slow_rising(hist):
    return len(hist) >= SLOW + 7 and ema(hist, SLOW) > ema(hist[:-6], SLOW)


def trend_up(sym):
    """A real uptrend, not a dead-cat bounce: fast EMA above a *rising*
    slow EMA, close above the slow EMA, and a 24h return above 1.5%."""
    hist = closes[sym]
    if len(hist) < SLOW + 7:
        return False
    fast = ema(hist, FAST)
    slow = ema(hist, SLOW)
    ret24 = hist[-1] / hist[-1 - TREND_WINDOW] - 1.0
    mom = hist[-1] / hist[-1 - MOM_WINDOW] - 1.0
    return fast > slow and slow_rising(hist) and hist[-1] > slow and ret24 > ENTRY_MOM and mom > 0


def trend_broken(sym):
    hist = closes[sym]
    if len(hist) < SLOW + 1:
        return True
    fast = ema(hist, FAST)
    slow = ema(hist, SLOW)
    mom = hist[-1] / hist[-1 - MOM_WINDOW] - 1.0
    return fast < slow or hist[-1] < slow or mom < EXIT_MOM


def momentum(sym):
    hist = closes[sym]
    if len(hist) <= MOM_WINDOW:
        return -1.0
    return hist[-1] / hist[-1 - MOM_WINDOW] - 1.0


def market_up():
    """Broad-market switch: SOL in a clear uptrend."""
    hist = closes.get("SOL", [])
    if len(hist) < SLOW + 7:
        return False
    fast = ema(hist, FAST)
    slow = ema(hist, SLOW)
    ret24 = hist[-1] / hist[-1 - TREND_WINDOW] - 1.0
    return fast > slow and slow_rising(hist) and ret24 > 0.01


def scalp_entry(sym):
    """First green bar after an oversold washout: RSI below 30 and the
    close ticked up from the previous bar."""
    hist = closes[sym]
    if len(hist) < RSI_LEN + 2:
        return False
    return rsi(hist) < 30 and hist[-1] > hist[-2]


def on_batch(state, batch):
    if state.warming_up:
        return []
    for bar in batch["bars"]:
        sym = bar["symbol"]
        closes.setdefault(sym, []).append(int(bar["c"]))
    orders = []
    cash = state.cash
    up = market_up()
    # Sells first: free cash and cut losers before any new buy.
    for sym, hold in list(state.positions.items()):
        hist = closes.get(sym, [])
        if not hist:
            continue
        close = hist[-1]
        if up:
            peaks[sym] = max(peaks.get(sym, close), close)
            if not trend_up(sym) or trend_broken(sym) or close < peaks[sym] * (1.0 - STOP_PCT):
                orders.append({"side": "sell", "symbol": sym, "qty": hold.qty,
                               "max_slippage_bps": SLIPPAGE_BPS})
                peaks.pop(sym, None)
                entries.pop(sym, None)
        else:
            entry = entries.get(sym)
            if entry is None:
                # Holding from the momentum leg while the market turned:
                # exit on the momentum rules, not the scalp ones.
                peaks[sym] = max(peaks.get(sym, close), close)
                if trend_broken(sym) or close < peaks[sym] * (1.0 - STOP_PCT):
                    orders.append({"side": "sell", "symbol": sym, "qty": hold.qty,
                                   "max_slippage_bps": SLIPPAGE_BPS})
                    peaks.pop(sym, None)
            else:
                price, seq = entry
                if (close >= price * (1.0 + SCALP_TP) or close <= price * (1.0 - SCALP_SL)
                        or rsi(hist) > RSI_SELL or state.seq - seq >= SCALP_MAX_BARS):
                    orders.append({"side": "sell", "symbol": sym, "qty": hold.qty,
                                   "max_slippage_bps": SLIPPAGE_BPS})
                    entries.pop(sym, None)
                    peaks.pop(sym, None)
    sold = {o["symbol"] for o in orders if o["side"] == "sell"}
    held = set(state.positions) - sold
    if up:
        # Momentum leg: rank fresh candidates by momentum, take the best.
        cands = [s for s in closes if s not in held and trend_up(s)]
        cands.sort(key=momentum, reverse=True)
        for sym in cands[:MAX_HOLD]:
            target = state.equity * TARGET_BPS // 10000
            spend = min(target, state.weight_room(sym), cash)
            if spend <= 0:
                continue
            orders.append({"side": "buy", "symbol": sym,
                           "notional_quote_units": spend,
                           "max_slippage_bps": SLIPPAGE_BPS})
            cash -= spend
            peaks[sym] = closes[sym][-1]
    else:
        # Scalp leg: buy oversold names on the first green bar, small size, quick exits.
        cands = [s for s in closes if s not in held and scalp_entry(s)]
        cands.sort(key=lambda s: rsi(closes[s]))
        for sym in cands[:MAX_HOLD]:
            target = state.equity * SCALP_BPS // 10000
            spend = min(target, state.weight_room(sym), cash)
            if spend <= 0:
                continue
            orders.append({"side": "buy", "symbol": sym,
                           "notional_quote_units": spend,
                           "max_slippage_bps": SLIPPAGE_BPS})
            cash -= spend
            entries[sym] = (closes[sym][-1], state.seq)
    return orders


makefun_bars.run(on_batch)
