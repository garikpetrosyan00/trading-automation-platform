# Dashboard Manual Browser QA Checklist

Use this checklist to validate `/dashboard` after frontend changes. Mark each item as pass/fail and note the browser, viewport, and test data used.

## Setup

- [ ] Open `/dashboard` in a normal browser window.
- [ ] Hard refresh the page:
  - Chrome/Edge/Linux/Windows: `Ctrl+Shift+R`
  - Chrome/Edge/macOS: `Cmd+Shift+R`
- [ ] Confirm the page loads without a blank screen.
- [ ] Open DevTools Network and confirm `styles.css?v=frontend-consistency-polish` loads successfully.
- [ ] Open DevTools Console and confirm there are no uncaught JavaScript errors on initial load.

## Language Switching

- [ ] Click `AM`; confirm visible labels, helper text, buttons, empty states, and status messages switch to Armenian.
- [ ] Click `EN`; confirm the same areas switch back to English.
- [ ] Refresh the page; confirm the selected language persists.
- [ ] Confirm language switching does not clear selected bot, entered form values unexpectedly, or create console errors.

## Bot List And Selection

- [ ] Confirm loading, empty, and error states are readable if those states are available.
- [ ] Confirm bot count matches the visible list.
- [ ] Search for a bot by name or symbol; confirm matching and no-match states are clear.
- [ ] Select a bot; confirm the selected row highlight moves to the selected bot.
- [ ] Switch between bots; confirm details, actions, Strategy Parameters, Risk Settings, Recent Activity, and Backtest default strategy update.

## Selected Bot Summary

- [ ] Confirm bot name, symbol, status, mode, strategy, cooldown, last price, and updated time render without overlap.
- [ ] Confirm draft, active, paused, and unavailable states show sensible labels when available.
- [ ] Confirm helper text under the action buttons explains the current action state.

## Bot Actions

- [ ] For a draft bot, confirm the main lifecycle button shows `Activate bot`.
- [ ] Activate a draft bot with valid execution settings; confirm button loading state and success/error message are clear.
- [ ] Pause an active bot; confirm loading state, status update, and success/error message.
- [ ] Resume a paused bot; confirm loading state, status update, and success/error message.
- [ ] Run an active, unpaused bot; confirm loading state, Decision Explanation update, Recent Activity update, and no duplicate submission.
- [ ] Confirm disabled action buttons have a clear contextual reason in nearby helper text.
- [ ] Start delete flow; confirm confirmation prompt appears and canceling leaves the bot unchanged.

## Market Price Actions

- [ ] Set a valid manual price; confirm success message and selected bot price update.
- [ ] Try invalid price input; confirm validation/error message is visible.
- [ ] Fetch Binance price for a bot with a symbol; confirm loading state and result message.
- [ ] Confirm fetch is disabled or clearly explained when no bot/symbol is selected.

## Strategy Parameters Editor

- [ ] Confirm Strategy Parameters summary shows expected labels for the selected strategy type.
- [ ] Open the editor; confirm fields and helper text match the strategy type.
- [ ] Save valid parameters; confirm loading state, success message, summary refresh, and Backtest defaults update where applicable.
- [ ] Try invalid parameters; confirm validation message is clear.
- [ ] Cancel editing; confirm the form closes without unintended changes.

## Execution Settings Setup

- [ ] Select a draft bot without execution settings; confirm the setup form appears.
- [ ] Confirm required fields, optional risk fields, and Paper mode checkbox are visible and readable.
- [ ] Submit with missing or invalid values; confirm validation message.
- [ ] Submit valid values; confirm loading state, success message, form hiding, and bot action availability.

## Risk Settings Editor

- [ ] Confirm Risk Settings appears only when an execution profile exists.
- [ ] Confirm active/disabled badges reflect current risk rule values.
- [ ] Save valid risk settings; confirm success message and badge refresh.
- [ ] Clear optional risk fields; confirm badges show disabled.
- [ ] Try invalid risk values; confirm validation message.

## Decision Explanation

- [ ] Run a bot or load a bot with a recent decision; confirm the card appears.
- [ ] Confirm decision badge, reason, price, thresholds, and position quantity render clearly.
- [ ] Confirm risk reason chip appears when risk blocked/skipped a trade.
- [ ] Confirm the card hides cleanly when no decision explanation is available.

## Recent Activity

- [ ] Confirm loading, empty, and error states are readable.
- [ ] Confirm activity status badges, type badges, message, details, bot name, and time render without overlap.
- [ ] Trigger an action such as run/pause/resume; confirm Recent Activity refreshes.
- [ ] Check DevTools Console after activity refresh for errors.

## Backtest Form And Results

- [ ] Confirm Backtest strategy defaults to the selected bot strategy when available.
- [ ] Run a valid backtest; confirm loading state, success/error message, result notes, metrics, and trades list.
- [ ] Try invalid initial balance; confirm validation message.
- [ ] Import Binance candles with a valid limit; confirm loading state and result message.
- [ ] Try invalid candle limit; confirm validation message.
- [ ] Confirm no-trade/no-candle hints appear clearly when those result states occur.

## Recent Backtests

- [ ] Confirm loading, empty, and error states are readable.
- [ ] Confirm visible summary bar shows visible runs, best return, average return, profitable runs, and closed-trade count.
- [ ] Toggle `Selected strategy`; confirm only selected strategy runs are shown when available.
- [ ] Toggle `All recent runs`; confirm all loaded recent runs are shown.
- [ ] Confirm selected scope is disabled with a helpful title when no selected strategy exists.
- [ ] Open and close details for a recent run; confirm `aria-expanded` behavior visually matches the button state.
- [ ] Confirm details include strategy, type, balances, returns, trades, source, candles, and updated time when data is available.
- [ ] Confirm summary and best-run callout update when the scope changes.

## Strategy Performance Comparison

- [ ] Confirm loading, empty, and error states are readable.
- [ ] Confirm comparison cards show strategy name, type, recent runs, best/latest return, closed trades, win rate, profit factor, and last backtest.
- [ ] Confirm badges appear appropriately: best performer, needs more runs, no closed trades, selected bot strategy.
- [ ] Click `View latest run`; confirm it scrolls/focuses/highlights the visible recent run.
- [ ] Confirm `Latest run not visible` is disabled and has a helpful title when applicable.
- [ ] Click `Use for new backtest`; confirm Backtest strategy changes, results/optimization reset, and the form scrolls into view.

## Parameter Optimization

- [ ] Confirm labels and helper text change for price threshold, moving average, RSI, Bollinger Bands, and MACD strategies.
- [ ] Click each visible preset for the selected strategy type; confirm values populate and hidden presets stay hidden.
- [ ] Run a valid optimization; confirm loading state, completion message, quality summary, warnings, metrics, and ranked results.
- [ ] Try invalid optimization values; confirm validation message.
- [ ] Toggle display filters; confirm result list and empty filtered state update locally.
- [ ] Click `Apply to Strategy`; confirm the confirmation dialog includes strategy and parameters.
- [ ] Confirm canceling Apply leaves parameters unchanged.
- [ ] Confirm accepting Apply shows loading state, success/error message, Strategy Parameters refresh, Backtest history refresh, and selected strategy remains coherent.

## Responsive Layout

- [ ] Test desktop width around `1180px`; confirm panels and grids align cleanly.
- [ ] Test tablet width around `768px`; confirm grids collapse without clipped buttons or overlapping text.
- [ ] Test mobile width around `375px`; confirm topbar, bot list, action buttons, backtest cards, badges, and optimization controls wrap cleanly.
- [ ] Confirm no horizontal page scrolling appears at mobile width.
- [ ] Confirm compact buttons and badges remain tappable and readable.

## Final Console Check

- [ ] Clear DevTools Console.
- [ ] Switch language, select bots, run at least one action, open/close details, run or validate backtest/optimization, and resize the viewport.
- [ ] Confirm no uncaught errors or repeated warnings appear.
- [ ] Capture any failures with browser, viewport, selected bot/strategy, exact steps, expected result, and actual result.
