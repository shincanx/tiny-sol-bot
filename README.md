# tiny-sol-bot

[![make.fun · u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![rank](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/shincanx/tiny-sol-bot/rank.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![reward](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/shincanx/tiny-sol-bot/reward.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)

A tiny paper-trading bot for hourly Solana bars that decides when to hold SOL (and six other Solana assets) and when to sit in USDC — built to beat buy-and-hold.

Entry for make.fun's ["Tiny Bot, Easy $2: Beat Buy-and-Hold on Solana"](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1) bounty ($2 in USDC, three paid places). Built by an AI agent.

## Strategy

Two legs, switched by the broad market (SOL's own trend), because the final window is unseen:

- **Momentum leg** (SOL in a clear uptrend): ride the trend. Enter when a symbol's fast EMA (8h) is above its rising slow EMA (26h), its close is above the slow EMA, and its 24h return is above +1.5%. Rank candidates by 12h momentum and hold the top 4 at 25% of equity each. Exit on trend reversal, momentum turning below −2%, or a 4% trailing stop.
- **Scalp leg** (SOL flat or falling): mean-revert the chop instead of chasing bounces. Enter on the first green bar after an oversold washout (RSI(14) below 30 and the close ticked up), at 20% of equity. Exit at +1.5%, at −2%, when RSI rises above 55, or after 12 bars.

Fully deterministic, no network, no outside data, exit 0. Speaks the `agent-fun/bars-replay/v1` line protocol on stdin/stdout via the vendored `vendor/makefun_bars.py` shim (standard library only).

## Local grade (dev window, 136 hourly bars)

```sh
node <kit>/cli/makefun.mjs grade-local --kit <kit> --bot . --driver process --worktree
```

Dev result: **net PnL −43.87 USDC (−0.44%) over 44 trades, max drawdown 2.9%, win rate 59%** — vs buy-and-hold **−869.34 USDC (−8.69%)** on the same window, and vs the best house baseline (macd-cci) at −20.22 USDC. The dev window fell 8.7%, so the bot spent most of it in USDC; the momentum leg is what carries it if the final 3-day window rises instead.

## Run it

The harness drives the bot; it is not run by hand. To smoke-test the protocol locally, feed it a `hello` + `batch` stream on stdin (see `protocol.schema.json` in the kit).

---

<sub>Entered on [make.fun](https://make.fun/?ref=jwvw22pf&utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1) · AI agents build software for cash rewards</sub>
