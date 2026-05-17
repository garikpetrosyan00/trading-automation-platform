const API_BASE_URL = "";
const AUTO_REFRESH_MS = 10000;
const LANGUAGE_STORAGE_KEY = "dashboard.language";
const DEFAULT_LANGUAGE = "en";
const SUPPORTED_LANGUAGES = new Set(["en", "am"]);

let bots = [];
let strategies = [];
let selectedBotId = null;
let selectedSummary = null;
let latestDecisionExplanation = null;
let isLoadingBots = true;
let isLoadingSummary = false;
let isLoadingStrategies = false;
let isTogglingPause = false;
let isRunningNow = false;
let isUpdatingPrice = false;
let isFetchingBinancePrice = false;
let isRefreshing = false;
let isCreatingBot = false;
let isCreateBotOpen = false;
let isEditBotOpen = false;
let isLoadingEditBot = false;
let isSavingEditBot = false;
let isDeletingBot = false;
let isCreatingExecutionProfile = false;
let isEditingStrategyParameters = false;
let isSavingStrategyParameters = false;
let isSavingRiskSettings = false;
let isRunningBacktest = false;
let isImportingBacktestCandles = false;
let isRunningBacktestOptimization = false;
let isApplyingOptimizationParameters = false;
let isLoadingBacktestHistory = false;
let backtestStrategyTouched = false;
let backtestOptimizationTouched = false;
let showMeaningfulOptimizationOnly = false;
let showPassedOptimizationOnly = false;
let symbolTouched = false;
let botListError = "";
let summaryError = "";
let actionMessage = "";
let actionMessageType = "";
let createBotMessage = "";
let createBotMessageType = "";
let editBotMessage = "";
let editBotMessageType = "";
let executionSettingsMessage = "";
let executionSettingsMessageType = "";
let strategyParametersMessage = "";
let strategyParametersMessageType = "";
let riskSettingsMessage = "";
let riskSettingsMessageType = "";
let backtestMessage = "";
let backtestMessageType = "";
let backtestImportMessage = "";
let backtestImportMessageType = "";
let backtestOptimizationMessage = "";
let backtestOptimizationMessageType = "";
let backtestResult = null;
let backtestOptimizationResult = null;
let backtestHistory = [];
let backtestHistoryError = "";
let backtestHistoryRequestId = 0;
let strategyLoadError = "";
let priceMessage = "";
let priceMessageType = "";
let refreshMessage = "";
let refreshMessageType = "";
let botSearchQuery = "";
let lastRefreshedAt = null;
let autoRefreshTimer = null;
let selectedBotConfig = null;
let selectedExecutionProfile = null;
let hasUserSelectedBot = false;
let currentLanguage = getStoredLanguage();

const translations = {
  en: {
    dashboard_title: "Bots Dashboard",
    topbar_eyebrow: "Local Trading Simulator",
    refresh: "Refresh",
    refreshing: "Refreshing…",
    auto_refresh: "Auto-refresh",
    symbol: "Symbol",
    bots_heading: "Bots",
    create_bot: "Create Bot",
    close: "Close",
    create_bot_defaults:
      "New bots are created as draft paper bots by default. They are saved, selected here, and not live yet.",
    name: "Name",
    strategy: "Strategy",
    exchange: "Exchange",
    notes: "Notes",
    optional_notes: "Optional notes",
    create_draft_bot: "Create draft bot",
    creating: "Creating…",
    search_bots: "Search bots...",
    save_changes: "Save changes",
    saving: "Saving…",
    cancel: "Cancel",
    edit_bot: "Edit Bot",
    edit: "Edit",
    edit_bot_summary:
      "This form updates bot details and the selected Strategy. Status and mode are shown here for context and are not editable in this form.",
    delete_bot: "Delete bot",
    deleting_bot: "Deleting…",
    delete_bot_confirm: 'Delete "{name}"? This cannot be undone.',
    deleted_bot_success: 'Deleted "{name}".',
    selected_strategy_label: "Strategy",
    selected_cooldown_label: "Cooldown",
    selected_price_label: "Last price",
    selected_last_run_label: "Updated",
    bot_settings: "Bot Settings",
    bot_settings_aria: "Bot settings",
    bot_settings_unavailable: "Bot settings unavailable",
    execution_settings: "Execution Settings",
    execution_settings_aria: "Execution settings",
    create_execution_settings_aria: "Create execution settings",
    execution_settings_help: "Create execution settings before activating this draft bot.",
    create_execution_settings: "Create execution settings",
    creating_execution_settings: "Creating…",
    execution_settings_created: "Execution settings created. You can activate this bot now.",
    execution_settings_create_failed: "Could not create execution settings.",
    execution_settings_positive_numbers: "Execution settings must use positive numbers.",
    execution_settings_positive_integers: "Cooldown seconds and max open positions must be positive integers.",
    execution_settings_required_fields: "Fill in all required execution settings.",
    cooldown_seconds_label: "Cooldown seconds",
    max_position_size_usd_label: "Max position size USD",
    max_daily_loss_usd_label: "Max daily loss USD",
    max_open_positions_label: "Max open positions",
    bot_name_label: "Bot name",
    status_label: "Status",
    paper_live_mode_label: "Mode",
    paused_label: "Paused",
    cooldown_active_label: "Cooldown active",
    current_position_qty_label: "Position qty",
    updated_time_label: "Updated",
    yes: "Yes",
    no: "No",
    not_available: "Not available",
    strategy_parameters: "Strategy Parameters",
    strategy_name_label: "Strategy",
    strategy_type_label: "Type",
    timeframe_label: "Timeframe",
    buy_below_label: "Buy below",
    sell_above_label: "Sell above",
    short_window_label: "Short window",
    long_window_label: "Long window",
    no_strategy_selected: "No strategy selected",
    no_strategy_parameters_configured: "No strategy parameters configured",
    strategy_details_unavailable: "Strategy details unavailable",
    edit_strategy_parameters: "Edit",
    edit_strategy_parameters_aria: "Edit strategy parameters",
    save: "Save",
    strategy_parameters_updated: "Strategy parameters updated.",
    strategy_parameters_save_failed: "Could not update Strategy parameters.",
    enter_strategy_parameters: "Enter buy below, sell above, and quantity.",
    enter_moving_average_parameters: "Enter short window and long window.",
    strategy_parameters_must_be_numbers: "Strategy parameters must be positive numbers.",
    moving_average_windows_must_be_integers: "Short window and long window must be positive integers.",
    moving_average_short_less_than_long: "Short window must be smaller than long window.",
    moving_average_parameters_help:
      "Short window must be smaller than long window. Both windows must be positive integers.",
    price_threshold_parameters_help:
      "Buy below is the entry trigger, sell above is the exit trigger, and quantity is the simulated trade amount.",
    strategy_parameters_edit_unavailable: "Editing is not available for this strategy type yet.",
    risk_settings: "Risk Settings",
    risk_settings_aria: "Risk settings",
    risk_settings_help:
      "These limits protect paper/live bot execution decisions. Leave a field empty to disable that rule.",
    risk_rule_status_aria: "Risk rule status",
    risk_rule_active: "Active: {value}",
    risk_rule_disabled: "Disabled",
    max_trade_quantity_label: "Max trade quantity",
    max_position_quantity_label: "Max position quantity",
    stop_loss_percent_label: "Stop loss %",
    max_trade_quantity_help: "Blocks one trade above this quantity.",
    max_position_quantity_help: "Blocks growing the total position above this quantity.",
    stop_loss_percent_help:
      "Protects the position when price moves against the entry by this percentage.",
    risk_settings_updated: "Risk settings updated.",
    risk_settings_save_failed: "Could not update Risk settings.",
    risk_settings_unavailable: "Risk settings unavailable.",
    risk_settings_must_be_positive: "Risk settings must be positive numbers.",
    backtest: "Backtest",
    backtest_aria: "Run backtest",
    backtest_overview:
      "Backtests replay historical candles from the selected source. They are simulated, place no real orders, and depend on the selected Strategy plus available candle data.",
    import_binance_candles: "Import Binance candles",
    importing_binance_candles: "Importing…",
    candle_limit_label: "Candles",
    candle_limit_help: "Import 1-500 recent candles for the selected Strategy.",
    candle_import_completed: "Imported or updated {count} Binance candles for {symbol} {timeframe}.",
    candle_import_failed: "Could not import Binance candles.",
    candle_import_validation_failed: "Enter a candle limit from 1 to 500.",
    candle_import_strategy_missing: "Select a Strategy with symbol and timeframe first.",
    candle_import_invalid_symbol:
      "Binance could not import candles for this symbol. Check the Strategy symbol, for example BTCUSDT.",
    candle_import_invalid_timeframe:
      "Binance could not import candles for this timeframe. Try a supported Binance interval such as 1m, 5m, or 1h.",
    candle_import_network_failed: "Binance candle import failed. Check the symbol/timeframe or try again.",
    parameter_optimization: "Parameter Optimization",
    parameter_optimization_aria: "Parameter Optimization",
    parameter_optimization_help:
      "Test up to 50 parameter combinations against the same candles. Review results before applying parameters.",
    run_optimization: "Run optimization",
    running_optimization: "Optimizing…",
    optimization_completed: "Optimization completed: {count} combinations ranked.",
    optimization_failed: "Could not run optimization.",
    optimization_no_result: "Run optimization to compare parameter combinations.",
    optimization_max_sets: "Use 50 or fewer parameter combinations.",
    optimization_positive_numbers: "Optimization values must be positive numbers.",
    optimization_integer_windows: "Moving average windows must be positive integers.",
    optimization_short_less_than_long: "Each short window must be smaller than each long window.",
    optimization_unsupported_strategy: "Optimization is not available for this strategy type yet.",
    optimization_price_help: "Comma-separated buy/sell thresholds generate every combination with the quantity.",
    optimization_ma_help: "Comma-separated short/long windows generate every combination with the quantity.",
    optimization_min_closed_trades_label: "Minimum closed trades",
    optimization_require_closed_position_label: "Require closed position",
    optimization_quality_filters_invalid: "Minimum closed trades must be a whole number of 0 or more.",
    optimization_effective_parameters_label: "Effective parameters",
    optimization_submitted_overrides_label: "Submitted overrides",
    optimization_base_parameters_label: "Saved strategy parameters",
    optimization_review_note: "Review results before applying parameters.",
    optimization_quality_title: "Optimization quality",
    optimization_quality_note:
      "Optimization is more reliable when parameter sets produce closed trades. Open positions can make results incomplete. Try importing more candles or adjusting buy/sell ranges.",
    optimization_total_combinations: "Total combinations: {count}",
    optimization_closed_trade_results: "With closed trades: {count}",
    optimization_open_position_results: "Ending open: {count}",
    optimization_unique_returns: "Unique returns: {count}",
    optimization_passed_quality_results: "Passed quality filters: {count}",
    optimization_failed_quality_results: "Failed quality filters: {count}",
    optimization_warning_no_closed_trades: "No parameter set produced closed trades, so results are inconclusive.",
    optimization_warning_most_no_closed_trades: "Most parameter sets did not produce closed trades.",
    optimization_warning_similar_returns: "Returns are nearly identical across all parameter sets.",
    optimization_warning_all_open_positions: "Every result ends with an open position.",
    optimization_warning_few_trades: "Results have very few trades; rankings may be fragile.",
    optimization_meaningful_filter: "Show only results with closed trades locally",
    optimization_passed_quality_filter: "Show only results that passed quality filters",
    optimization_no_display_filter_results: "No optimization results match the selected display filters.",
    optimization_no_meaningful_results:
      "No parameter set produced closed trades. Try importing more candles or widening the buy/sell ranges.",
    optimization_quality_passed: "Passed quality filters",
    optimization_quality_failed: "Failed quality filters",
    optimization_result_warnings_label: "Quality warnings",
    optimization_warning_below_min_closed_trades: "Closed trades are below your minimum.",
    optimization_warning_ends_with_open_position: "The run ended with an open position.",
    optimization_warning_requires_closed_position: "Your filter requires the run to end flat.",
    optimization_warning_unknown: "Quality warning: {warning}",
    apply_to_strategy: "Apply to Strategy",
    applying_to_strategy: "Applying…",
    optimization_apply_confirm:
      'Apply these parameters to "{strategy}"?\n\n{parameters}',
    optimization_apply_success: 'Applied optimization parameters to "{strategy}".',
    optimization_apply_failed: "Could not apply optimization parameters to the Strategy.",
    optimization_apply_unavailable: "Strategy details are not available for this optimization result.",
    buy_below_values_label: "Buy below values",
    sell_above_values_label: "Sell above values",
    short_window_values_label: "Short window values",
    long_window_values_label: "Long window values",
    rank_label: "Rank",
    parameters_label: "Parameters",
    run_backtest: "Run Backtest",
    running_backtest: "Running…",
    initial_balance_label: "Initial balance",
    source_label: "Source",
    select_strategy_for_backtest: "Select a Strategy to run a backtest.",
    backtest_uses_selected_bot_strategy: "Uses the selected Bot strategy when available.",
    enter_positive_initial_balance: "Enter a positive initial balance.",
    backtest_completed: "Backtest completed.",
    could_not_run_backtest: "Could not run backtest.",
    backtest_strategy_not_found: "Strategy could not be found.",
    no_backtest_result: "Run a backtest to see simulated results.",
    no_backtest_result_hint: "Use historical candles from the selected source; no real orders are placed.",
    backtest_no_candle_data: "No candle data found for the selected Strategy/source.",
    backtest_not_enough_candle_data: "Not enough candle data for this Strategy yet.",
    backtest_no_trade_hint:
      "No trades were opened. The Strategy may not have found a signal, or it may need more candle data.",
    backtest_simulated_note: "Simulated only: no real orders are placed.",
    backtest_data_note: "Historical candles: {source}",
    backtest_strategy_data_note: "Results depend on this Strategy and available candle data.",
    profit_factor_help: "Gross profit divided by gross loss; above 1.00 means wins outweighed losses.",
    win_rate_help: "Percent of closed trades that ended profitable.",
    total_return_help: "Change from initial balance to final balance.",
    closed_trades_help: "Trades that fully exited a position.",
    open_position_help: "Whether the simulation ended while still holding a position.",
    backtest_trade_actions: "Backtest Trades",
    action_time_label: "Time",
    cash_balance_label: "Cash balance",
    entry_price_label: "Entry price",
    open_position_qty_label: "Open position qty",
    reason_label: "Reason",
    final_balance_label: "Final balance",
    realized_pnl_label: "Realized PnL",
    unrealized_pnl_label: "Unrealized PnL",
    number_of_trades_label: "Trades",
    closed_trades_label: "Closed trades",
    open_position_label: "Open position",
    total_return_label: "Total return",
    return_percent_label: "Return %",
    win_rate_label: "Win rate",
    average_trade_pnl_label: "Avg trade PnL",
    best_trade_pnl_label: "Best trade PnL",
    worst_trade_pnl_label: "Worst trade PnL",
    profit_factor_label: "Profit factor",
    no_backtest_trades: "No trades were executed during this backtest.",
    recent_backtests: "Recent Backtests",
    recent_backtests_aria: "Recent Backtests",
    loading_recent_backtests: "Loading recent backtests...",
    no_backtests_yet: "No recent backtests yet.",
    no_backtests_yet_hint: "Run one for the selected Strategy to build history and compare results.",
    failed_to_load_backtest_history: "Failed to load backtest history.",
    refresh_backtest_history: "Refresh",
    refreshing_backtest_history: "Refreshing…",
    backtest_strategy_fallback: "Strategy #{id}",
    winning_losing_trades_label: "Wins / losses",
    best_recent_run: "Best recent run",
    best_recent_run_help: "Based on recent saved backtests for this strategy.",
    run_more_backtests_to_compare: "Run more backtests to compare recent results.",
    candles_processed_label: "Candles",
    recent_activity: "Recent Activity",
    set_price: "Set price",
    fetch_binance_price: "Fetch Binance price",
    fetching_binance_price: "Fetching…",
    fetched_binance_price: "Fetched {symbol} from Binance: {price}",
    select_bot_for_binance_price: "Select a Bot to fetch its Binance price.",
    missing_symbol_for_binance_price: "Selected Bot has no symbol.",
    binance_symbol_not_found:
      "Binance could not fetch data for this symbol. Use a valid symbol like BTCUSDT, or use Set price for local testing.",
    could_not_fetch_binance_price: "Could not fetch Binance price.",
    updating: "Updating…",
    price: "Price",
    quantity: "Quantity",
    loading_recent_activity: "Loading recent activity...",
    loading_generic: "Loading…",
    no_recent_activity_yet: "No visible activity yet.",
    failed_to_load_recent_activity: "Failed to load recent activity.",
    ready_to_run: "Ready to run",
    paused_state: "Paused",
    not_runnable: "Not runnable",
    loading_actions: "Loading bot actions...",
    activate_draft_before_running: "Activate this draft Bot before running it.",
    activate_bot: "Activate bot",
    activating_bot: "Activating…",
    execution_settings_required_to_activate: "Execution settings are required before this draft Bot can be activated.",
    resume_automatic_checks: "Resume to re-enable automatic checks.",
    paper_mode_orders: "Paper mode uses simulated orders.",
    live_mode_orders: "Live mode places real orders.",
    paper_mode: "Paper mode",
    live_mode: "Live mode",
    mode_loading: "Mode loading…",
    run_now: "Run now",
    running_now: "Running…",
    pause: "Pause",
    resume: "Resume",
    pause_resume: "Pause/Resume",
    select_bot_to_view_actions: "Select a Bot to view its actions.",
    bot_count_one: "{count} Bot",
    bot_count_other: "{count} Bots",
    filtered_bot_count: "{visible}/{total} Bots",
    last_refreshed: "Last refreshed",
    loading_bots: "Loading Bots...",
    no_bots_yet: "No Bots yet. Create a Bot to see it here.",
    no_bots_match_search: "No Bots match your search.",
    details_unavailable: "Details unavailable",
    no_bots_available_yet: "No Bots available yet.",
    select_bot_to_view_details: "Select a Bot to view details.",
    add_bot_to_get_started: "Add a Bot to get started",
    no_bot_activity_yet: "No Bot activity yet",
    loading_details: "Loading details...",
    select_bot_to_view_activity: "Select a Bot to view activity.",
    no_bots_activity_after_create: "No Bots available yet. Recent activity will appear here after a Bot is created.",
    loading_available_strategies: "Loading available strategies…",
    strategies_unavailable: "Strategies unavailable",
    no_strategies_available: "No strategies available",
    could_not_load_strategies: "Could not load strategies. {detail}",
    create_strategy_first_create_bot: "Create a Strategy first, then you can create a Bot.",
    create_strategy_first_edit_bot: "Create a Strategy first, then you can update the Bot strategy.",
    select_strategy: "Select a Strategy.",
    enter_bot_name: "Enter a Bot name.",
    enter_exchange_name: "Enter an exchange name.",
    strategies_still_loading: "Strategies are still loading.",
    create_strategy_first_then_create_bot: "Create a Strategy first, then create a Bot.",
    create_strategy_first_then_edit_bot: "Create a Strategy first, then edit the Bot strategy.",
    check_bot_fields: "Check the Bot form fields and try again.",
    created_bot_success:
      "Created {name}. It is selected now and remains a draft paper Bot until you activate it.",
    updated_bot_success: "Updated {name}.",
    price_updated: "Price updated",
    check_symbol_positive_price: "Check Symbol and positive Price.",
    manual_run_completed: "Manual run completed. {activity}.",
    manual_run_skipped: "Manual run skipped. {activity}.",
    manual_run_checked: "Manual run checked the Bot. {activity}.",
    decision_explanation: "Decision Explanation",
    risk_limit_blocked_message: "Trade was blocked by risk settings.",
    risk_max_trade_quantity_exceeded: "Trade quantity is higher than the allowed limit.",
    risk_max_position_quantity_exceeded: "Position limit would be exceeded.",
    risk_stop_loss_triggered: "Stop-loss rule was triggered.",
    risk_missing_price: "Risk check could not run because the price is missing.",
    decision_reason_label: "Decision / reason",
    risk_reason_label: "Risk reason",
    decision_bought: "Bought",
    decision_sold: "Sold",
    decision_buy: "Buy",
    decision_sell: "Sell",
    decision_hold: "Hold",
    decision_skipped: "Skipped",
    decision_reason_buy_threshold_reached: "Buy signal. Current price is below the buy target.",
    decision_reason_sell_threshold_reached: "Sell signal. Current price is above the sell target.",
    decision_reason_no_buy_signal: "No buy signal. Current price is above the buy target.",
    decision_reason_no_sell_signal: "Holding position. Current price is below the sell target.",
    decision_reason_ma_buy_signal: "Buy signal. Moving averages crossed upward.",
    decision_reason_ma_sell_signal: "Sell signal. Moving averages crossed downward.",
    decision_reason_ma_no_buy_signal: "No buy signal. Moving averages have not crossed upward.",
    decision_reason_ma_no_sell_signal: "Holding position. Moving averages have not crossed downward.",
    decision_reason_insufficient_candles: "Not enough candle data to make a decision.",
    decision_reason_no_latest_price: "No latest price is available.",
    decision_reason_strategy_not_supported: "This strategy type is not supported yet.",
    decision_reason_invalid_strategy_parameter: "Strategy parameters need attention.",
    decision_reason_order_quantity_missing: "Order quantity is not configured.",
    current_price_label: "Current price",
    buy_threshold_label: "Buy below",
    sell_threshold_label: "Sell above",
    position_qty_label: "Position qty",
    decision_label: "Decision",
    request_failed_404: "The requested Bot could not be found.",
    request_failed_422: "Check the submitted values and try again.",
    could_not_update_price: "Could not update price.",
    could_not_create_bot: "Could not create Bot.",
    could_not_update_bot: "Could not update Bot.",
    could_not_delete_bot: "Could not delete Bot.",
    could_not_load_bot_settings: "Could not load Bot settings.",
    could_not_load_bot_details: "Could not load Bot details.",
    could_not_load_bots: "Could not load Bots.",
    could_not_refresh: "Could not refresh.",
    auto_refresh_failed: "Auto-refresh failed. {detail}",
    please_try_again: "Please try again.",
    could_not_run_bot: "Could not run Bot.",
    could_not_pause_bot: "Could not pause Bot.",
    could_not_resume_bot: "Could not resume Bot.",
    could_not_activate_bot: "Could not activate Bot.",
    market_price_update: "Market price update",
    language_switcher: "Language switcher",
    bot_dashboard_aria: "Bot dashboard",
    bots_aria: "Bots",
    create_bot_aria: "Create Bot",
    edit_bot_aria: "Edit Bot",
    recent_activity_aria: "Recent activity",
    loading_strategies: "Loading strategies…",
    create_bot_hint_name: "Momentum Bot",
    mode_ready: "Ready",
    side_label: "Side",
    price_label: "Price",
    quantity_label: "Qty",
    cooldown_until: "Cooldown until",
    activity_success: "Success",
    activity_skipped: "Skipped",
    activity_failed: "Failed",
    activity_running: "Running",
    activity_event: "Event",
    order_filled: "Order filled",
    run_event: "Run event",
    bot_event: "Bot event",
    activity_buy_filled: "Buy order filled",
    activity_sell_filled: "Sell order filled",
    activity_order_filled: "Order filled",
    activity_order_rejected: "Order rejected",
    activity_buy_signal: "Buy signal found",
    activity_sell_signal: "Sell signal found",
    activity_evaluation_skipped: "Check skipped: no trade action",
    activity_evaluation_no_signal: "Checked market: no signal",
    activity_bot_paused: "Bot paused",
    activity_bot_resumed: "Bot resumed",
    activity_bot_resume_requested: "Bot resumed",
    activity_bot_skipped_paused: "Bot is paused; check skipped",
    activity_bot_not_active: "Bot is not active; check skipped",
    activity_execution_profile_missing: "Execution settings are missing; check skipped",
    activity_execution_profile_disabled: "Execution settings are disabled; check skipped",
    activity_cooldown_active: "Waiting for cooldown before the next trade",
    activity_live_mode_not_implemented: "Live mode is not available yet; no order was placed",
    activity_unsupported_strategy_type: "Strategy type is not supported; check skipped",
    activity_strategy_inactive: "Strategy is inactive; check skipped",
    activity_started: "Bot started",
    activity_stopped: "Bot stopped",
    activity_error: "Run error",
    activity_run_requested_system: "Automatic run requested",
    activity_run_requested_manual: "Manual run requested",
    activity_run_started: "Run started",
    activity_run_status_updated: "Run status updated",
    activity_side_buy: "Buy",
    activity_side_sell: "Sell",
    bot_prefix: "Bot",
    active_until: "Active until",
    active: "Active",
    not_active: "Not active",
    configured_seconds: "{value}s configured",
    unnamed_bot: "Unnamed Bot",
    unnamed_strategy: "Unnamed Strategy",
    activity_update: "Activity update",
  },
  am: {
    dashboard_title: "Bots Dashboard",
    topbar_eyebrow: "Local Trading Simulator",
    refresh: "Թարմացնել",
    refreshing: "Թարմացվում է…",
    auto_refresh: "Auto-refresh",
    symbol: "Symbol",
    bots_heading: "Bots",
    create_bot: "Ստեղծել Bot",
    close: "Փակել",
    create_bot_defaults:
      "Նոր Bot-երը ստեղծվում են draft Paper mode-ով։ Դրանք պահպանվում են, ընտրվում այստեղ և դեռ live չեն։",
    name: "Անուն",
    strategy: "Strategy",
    exchange: "Բորսա",
    notes: "Նշումներ",
    optional_notes: "Լրացուցիչ նշումներ",
    create_draft_bot: "Ստեղծել draft Bot",
    creating: "Ստեղծվում է…",
    search_bots: "Որոնել Bot-եր...",
    save_changes: "Պահպանել",
    saving: "Պահպանվում է…",
    cancel: "Չեղարկել",
    edit_bot: "Խմբագրել Bot",
    edit: "Խմբագրել",
    edit_bot_summary:
      "Այս ձևը թարմացնում է Bot-ի դաշտերը և ընտրված Strategy-ն։ Status-ը և mode-ը այստեղ ցուցադրվում են միայն տեղեկության համար և չեն խմբագրվում։",
    delete_bot: "Ջնջել Bot-ը",
    deleting_bot: "Ջնջվում է…",
    delete_bot_confirm: 'Ջնջե՞լ "{name}" Bot-ը։ Այս գործողությունը հնարավոր չէ հետարկել։',
    deleted_bot_success: 'Ջնջվեց "{name}" Bot-ը։',
    selected_strategy_label: "Strategy",
    selected_cooldown_label: "Cooldown",
    selected_price_label: "Վերջին գին",
    selected_last_run_label: "Թարմացվել է",
    bot_settings: "Bot-ի կարգավորումներ",
    bot_settings_aria: "Bot-ի կարգավորումներ",
    bot_settings_unavailable: "Bot-ի կարգավորումները հասանելի չեն",
    execution_settings: "Execution կարգավորումներ",
    execution_settings_aria: "Execution կարգավորումներ",
    create_execution_settings_aria: "Ստեղծել execution կարգավորումներ",
    execution_settings_help: "Ստեղծիր execution կարգավորումներ՝ նախքան այս draft Bot-ը ակտիվացնելը։",
    create_execution_settings: "Ստեղծել execution կարգավորումներ",
    creating_execution_settings: "Ստեղծվում է…",
    execution_settings_created: "Execution կարգավորումները ստեղծվեցին։ Այժմ կարող ես ակտիվացնել այս Bot-ը։",
    execution_settings_create_failed: "Չհաջողվեց ստեղծել execution կարգավորումները։",
    execution_settings_positive_numbers: "Execution կարգավորումները պետք է լինեն դրական թվեր։",
    execution_settings_positive_integers: "Cooldown վայրկյանները և max open positions-ը պետք է լինեն դրական ամբողջ թվեր։",
    execution_settings_required_fields: "Լրացրու բոլոր պարտադիր execution կարգավորումները։",
    cooldown_seconds_label: "Cooldown վայրկյաններ",
    max_position_size_usd_label: "Առավելագույն position size USD",
    max_daily_loss_usd_label: "Առավելագույն daily loss USD",
    max_open_positions_label: "Առավելագույն open positions",
    bot_name_label: "Bot-ի անուն",
    status_label: "Կարգավիճակ",
    paper_live_mode_label: "Ռեժիմ",
    paused_label: "Դադարեցված",
    cooldown_active_label: "Cooldown ակտիվ է",
    current_position_qty_label: "Position-ի քանակ",
    updated_time_label: "Թարմացվել է",
    yes: "Այո",
    no: "Ոչ",
    not_available: "Հասանելի չէ",
    strategy_parameters: "Strategy-ի պարամետրեր",
    strategy_name_label: "Strategy",
    strategy_type_label: "Տեսակ",
    timeframe_label: "Ժամանակային միջակայք",
    buy_below_label: "Գնել՝ ցածր քան",
    sell_above_label: "Վաճառել՝ բարձր քան",
    short_window_label: "Կարճ պատուհան",
    long_window_label: "Երկար պատուհան",
    no_strategy_selected: "Strategy ընտրված չէ",
    no_strategy_parameters_configured: "Strategy-ի parameters-ները կարգավորված չեն",
    strategy_details_unavailable: "Strategy-ի մանրամասները հասանելի չեն",
    edit_strategy_parameters: "Խմբագրել",
    edit_strategy_parameters_aria: "Խմբագրել Strategy-ի parameters-ները",
    save: "Պահպանել",
    strategy_parameters_updated: "Strategy-ի parameters-ները թարմացվեցին։",
    strategy_parameters_save_failed: "Չհաջողվեց թարմացնել Strategy-ի parameters-ները։",
    enter_strategy_parameters: "Մուտքագրիր buy below, sell above և quantity արժեքները։",
    enter_moving_average_parameters: "Մուտքագրիր short window և long window արժեքները։",
    strategy_parameters_must_be_numbers: "Strategy-ի parameters-ները պետք է լինեն դրական թվեր։",
    moving_average_windows_must_be_integers: "Short window-ը և long window-ը պետք է լինեն դրական ամբողջ թվեր։",
    moving_average_short_less_than_long: "Short window-ը պետք է փոքր լինի long window-ից։",
    moving_average_parameters_help:
      "Short window-ը պետք է փոքր լինի long window-ից։ Երկու window-ներն էլ պետք է դրական ամբողջ թվեր լինեն։",
    price_threshold_parameters_help:
      "Buy below-ը մուտքի trigger-ն է, sell above-ը՝ ելքի trigger-ը, իսկ quantity-ն՝ simulated գործարքի քանակը։",
    strategy_parameters_edit_unavailable: "Այս strategy type-ի համար խմբագրումը դեռ հասանելի չէ։",
    risk_settings: "Risk կարգավորումներ",
    risk_settings_aria: "Risk կարգավորումներ",
    risk_settings_help:
      "Այս սահմանափակումները պաշտպանում են paper/live bot-ի գործարքային որոշումները։ Դաշտը դատարկ թող՝ տվյալ կանոնն անջատելու համար։",
    risk_rule_status_aria: "Risk կանոնների status",
    risk_rule_active: "Ակտիվ՝ {value}",
    risk_rule_disabled: "Անջատված",
    max_trade_quantity_label: "Առավելագույն trade quantity",
    max_position_quantity_label: "Առավելագույն position quantity",
    stop_loss_percent_label: "Stop loss %",
    max_trade_quantity_help: "Արգելում է մեկ trade, եթե quantity-ն այս արժեքից մեծ է։",
    max_position_quantity_help: "Արգելում է total position-ը այս արժեքից բարձր մեծացնելը։",
    stop_loss_percent_help:
      "Պաշտպանում է position-ը, երբ գինը entry-ի դեմ շարժվում է այս տոկոսով։",
    risk_settings_updated: "Risk կարգավորումները թարմացվեցին։",
    risk_settings_save_failed: "Չհաջողվեց թարմացնել Risk կարգավորումները։",
    risk_settings_unavailable: "Risk կարգավորումները հասանելի չեն։",
    risk_settings_must_be_positive: "Risk կարգավորումները պետք է լինեն դրական թվեր։",
    backtest: "Backtest",
    backtest_aria: "Գործարկել backtest",
    backtest_overview:
      "Backtest-ը վերարտադրում է ընտրված աղբյուրի historical candle-ները։ Այն simulation է, իրական order-ներ չի տեղադրում և կախված է ընտրված Strategy-ից ու հասանելի candle տվյալներից։",
    import_binance_candles: "Import Binance candles",
    importing_binance_candles: "Ներմուծվում է…",
    candle_limit_label: "Candle-ներ",
    candle_limit_help: "Ներմուծում է ընտրված Strategy-ի վերջին 1-500 candle-ները։",
    candle_import_completed: "{symbol} {timeframe}-ի համար ներմուծվեց կամ թարմացվեց {count} Binance candle։",
    candle_import_failed: "Չհաջողվեց ներմուծել Binance candle-ները։",
    candle_import_validation_failed: "Մուտքագրիր candle limit՝ 1-ից 500։",
    candle_import_strategy_missing: "Նախ ընտրիր symbol և timeframe ունեցող Strategy։",
    candle_import_invalid_symbol:
      "Binance-ը չկարողացավ ներմուծել candle-ներ այս symbol-ի համար։ Ստուգիր Strategy-ի symbol-ը, օրինակ՝ BTCUSDT։",
    candle_import_invalid_timeframe:
      "Binance-ը չկարողացավ ներմուծել candle-ներ այս timeframe-ի համար։ Փորձիր Binance interval՝ 1m, 5m կամ 1h։",
    candle_import_network_failed: "Binance candle import-ը ձախողվեց։ Ստուգիր symbol/timeframe-ը կամ կրկին փորձիր։",
    parameter_optimization: "Parameter Optimization",
    parameter_optimization_aria: "Parameter Optimization",
    parameter_optimization_help:
      "Ստուգում է մինչև 50 parameter combination նույն candle-ների վրա։ Արդյունքները վերանայիր մինչև parameters կիրառելը։",
    run_optimization: "Գործարկել optimization",
    running_optimization: "Optimization է կատարվում…",
    optimization_completed: "Optimization-ը ավարտվեց․ դասակարգվեց {count} combination։",
    optimization_failed: "Չհաջողվեց գործարկել optimization-ը։",
    optimization_no_result: "Գործարկիր optimization՝ parameter combination-ները համեմատելու համար։",
    optimization_max_sets: "Օգտագործիր առավելագույնը 50 parameter combination։",
    optimization_positive_numbers: "Optimization արժեքները պետք է լինեն դրական թվեր։",
    optimization_integer_windows: "Moving average window-ները պետք է լինեն դրական ամբողջ թվեր։",
    optimization_short_less_than_long: "Յուրաքանչյուր short window պետք է փոքր լինի յուրաքանչյուր long window-ից։",
    optimization_unsupported_strategy: "Այս strategy type-ի համար optimization-ը դեռ հասանելի չէ։",
    optimization_price_help: "Ստորակետերով buy/sell շեմերը quantity-ի հետ ստեղծում են բոլոր combination-ները։",
    optimization_ma_help: "Ստորակետերով short/long window-ները quantity-ի հետ ստեղծում են բոլոր combination-ները։",
    optimization_min_closed_trades_label: "Փակված trade-երի նվազագույն քանակ",
    optimization_require_closed_position_label: "Պահանջել փակ position",
    optimization_quality_filters_invalid: "Փակված trade-երի նվազագույնը պետք է լինի 0 կամ մեծ ամբողջ թիվ։",
    optimization_effective_parameters_label: "Կիրառված parameters",
    optimization_submitted_overrides_label: "Ուղարկված փոփոխություններ",
    optimization_base_parameters_label: "Պահված Strategy-ի parameters",
    optimization_review_note: "Վերանայիր արդյունքները՝ parameters կիրառելուց առաջ։",
    optimization_quality_title: "Optimization-ի որակ",
    optimization_quality_note:
      "Optimization-ը ավելի հուսալի է, երբ parameter set-երը ունեն փակված trade-եր։ Բաց position-ները կարող են արդյունքը թերի դարձնել։ Փորձիր ներմուծել ավելի շատ candle կամ փոխել buy/sell միջակայքերը։",
    optimization_total_combinations: "Ընդամենը combination՝ {count}",
    optimization_closed_trade_results: "Փակված trade-երով՝ {count}",
    optimization_open_position_results: "Բաց position-ով ավարտված՝ {count}",
    optimization_unique_returns: "Տարբեր return-ներ՝ {count}",
    optimization_passed_quality_results: "Որակի ֆիլտրերն անցած՝ {count}",
    optimization_failed_quality_results: "Որակի ֆիլտրերը չանցած՝ {count}",
    optimization_warning_no_closed_trades: "Ոչ մի parameter set փակված trade չունի, ուստի արդյունքները թույլ են։",
    optimization_warning_most_no_closed_trades: "Parameter set-երի մեծ մասը փակված trade չունի։",
    optimization_warning_similar_returns: "Return-ները գրեթե նույնն են բոլոր parameter set-երում։",
    optimization_warning_all_open_positions: "Բոլոր արդյունքները ավարտվում են բաց position-ով։",
    optimization_warning_few_trades: "Trade-երը շատ քիչ են, ranking-ը կարող է անկայուն լինել։",
    optimization_meaningful_filter: "Տեղում ցույց տալ միայն փակված trade-երով արդյունքները",
    optimization_passed_quality_filter: "Ցույց տալ միայն որակի ֆիլտրերն անցած արդյունքները",
    optimization_no_display_filter_results: "Ընտրված ցուցադրման ֆիլտրերին համապատասխան optimization result չկա։",
    optimization_no_meaningful_results:
      "Ոչ մի parameter set փակված trade չունի։ Փորձիր ներմուծել ավելի շատ candle կամ լայնացնել buy/sell միջակայքերը։",
    optimization_quality_passed: "Անցել է որակի ֆիլտրերը",
    optimization_quality_failed: "Չի անցել որակի ֆիլտրերը",
    optimization_result_warnings_label: "Որակի զգուշացումներ",
    optimization_warning_below_min_closed_trades: "Փակված trade-երը քո նվազագույնից քիչ են։",
    optimization_warning_ends_with_open_position: "Run-ը ավարտվել է բաց position-ով։",
    optimization_warning_requires_closed_position: "Քո ֆիլտրը պահանջում է, որ run-ը ավարտվի առանց բաց position-ի։",
    optimization_warning_unknown: "Որակի զգուշացում՝ {warning}",
    apply_to_strategy: "Կիրառել Strategy-ին",
    applying_to_strategy: "Կիրառվում է…",
    optimization_apply_confirm:
      '"{strategy}" Strategy-ին կիրառե՞լ այս parameters-ները։\n\n{parameters}',
    optimization_apply_success: 'Optimization-ի parameters-ները կիրառվեցին "{strategy}" Strategy-ին։',
    optimization_apply_failed: "Չհաջողվեց կիրառել optimization-ի parameters-ները Strategy-ին։",
    optimization_apply_unavailable: "Այս optimization result-ի Strategy-ի մանրամասները հասանելի չեն։",
    buy_below_values_label: "Buy below արժեքներ",
    sell_above_values_label: "Sell above արժեքներ",
    short_window_values_label: "Short window արժեքներ",
    long_window_values_label: "Long window արժեքներ",
    rank_label: "Դիրք",
    parameters_label: "Parameters",
    run_backtest: "Գործարկել Backtest",
    running_backtest: "Գործարկվում է…",
    initial_balance_label: "Սկզբնական balance",
    source_label: "Աղբյուր",
    select_strategy_for_backtest: "Ընտրիր Strategy՝ backtest գործարկելու համար։",
    backtest_uses_selected_bot_strategy: "Հնարավորության դեպքում օգտագործում է ընտրված Bot-ի strategy-ն։",
    enter_positive_initial_balance: "Մուտքագրիր դրական սկզբնական balance։",
    backtest_completed: "Backtest-ը ավարտվեց։",
    could_not_run_backtest: "Չհաջողվեց գործարկել backtest-ը։",
    backtest_strategy_not_found: "Strategy-ն չգտնվեց։",
    no_backtest_result: "Գործարկիր backtest՝ simulation արդյունքները տեսնելու համար։",
    no_backtest_result_hint: "Օգտագործում է ընտրված աղբյուրի historical candle-ները․ իրական order-ներ չեն տեղադրվում։",
    backtest_no_candle_data: "Ընտրված Strategy/source-ի համար candle տվյալներ չկան։",
    backtest_not_enough_candle_data: "Այս Strategy-ի համար candle տվյալները դեռ բավարար չեն։",
    backtest_no_trade_hint:
      "Trade չի բացվել։ Strategy-ն կարող էր signal չգտնել կամ ավելի շատ candle տվյալների կարիք ունենալ։",
    backtest_simulated_note: "Միայն simulation է․ իրական order-ներ չեն տեղադրվում։",
    backtest_data_note: "Historical candle-ներ՝ {source}",
    backtest_strategy_data_note: "Արդյունքները կախված են այս Strategy-ից և հասանելի candle տվյալներից։",
    profit_factor_help: "Ընդհանուր profit-ը բաժանած ընդհանուր loss-ի․ 1.00-ից բարձրն ավելի լավ է։",
    win_rate_help: "Profit-ով ավարտված փակված trade-երի տոկոսը։",
    total_return_help: "Սկզբնական balance-ից մինչև վերջնական balance փոփոխությունը։",
    closed_trades_help: "Trade-եր, որոնք ամբողջությամբ փակել են position-ը։",
    open_position_help: "Ցույց է տալիս՝ simulation-ի վերջում position մնացե՞լ է բաց։",
    backtest_trade_actions: "Backtest գործարքներ",
    action_time_label: "Ժամանակ",
    cash_balance_label: "Կանխիկ balance",
    entry_price_label: "Մուտքի գին",
    open_position_qty_label: "Բաց position-ի քանակ",
    reason_label: "Պատճառ",
    final_balance_label: "Վերջնական balance",
    realized_pnl_label: "Իրացված PnL",
    unrealized_pnl_label: "Չիրացված PnL",
    number_of_trades_label: "Գործարքներ",
    closed_trades_label: "Փակված գործարքներ",
    open_position_label: "Բաց position",
    total_return_label: "Ընդհանուր վերադարձ",
    return_percent_label: "Վերադարձ %",
    win_rate_label: "Win rate",
    average_trade_pnl_label: "Միջին trade PnL",
    best_trade_pnl_label: "Լավագույն trade PnL",
    worst_trade_pnl_label: "Վատագույն trade PnL",
    profit_factor_label: "Profit factor",
    no_backtest_trades: "Այս backtest-ի ընթացքում trade-եր չեն կատարվել։",
    recent_backtests: "Վերջին Backtest-երը",
    recent_backtests_aria: "Վերջին Backtest-եր",
    loading_recent_backtests: "Բեռնվում են վերջին backtest-երը...",
    no_backtests_yet: "Վերջին backtest-եր դեռ չկան։",
    no_backtests_yet_hint: "Գործարկիր մեկը ընտրված Strategy-ի համար՝ history ստեղծելու և արդյունքները համեմատելու համար։",
    failed_to_load_backtest_history: "Չհաջողվեց բեռնել backtest history-ն։",
    refresh_backtest_history: "Թարմացնել",
    refreshing_backtest_history: "Թարմացվում է…",
    backtest_strategy_fallback: "Strategy #{id}",
    winning_losing_trades_label: "Հաղթ. / պարտ.",
    best_recent_run: "Լավագույն վերջին run-ը",
    best_recent_run_help: "Հիմնված է այս strategy-ի վերջին պահպանված backtest-երի վրա։",
    run_more_backtests_to_compare: "Գործարկիր ավելի շատ backtest-եր՝ վերջին արդյունքները համեմատելու համար։",
    candles_processed_label: "Մոմեր",
    recent_activity: "Վերջին ակտիվություն",
    set_price: "Սահմանել գինը",
    fetch_binance_price: "Բեռնել Binance գինը",
    fetching_binance_price: "Բեռնվում է…",
    fetched_binance_price: "Բեռնվեց {symbol}-ի Binance գինը՝ {price}",
    select_bot_for_binance_price: "Ընտրիր Bot՝ Binance գինը բեռնելու համար։",
    missing_symbol_for_binance_price: "Ընտրված Bot-ը symbol չունի։",
    binance_symbol_not_found:
      "Binance-ը չկարողացավ տվյալներ գտնել այս symbol-ի համար։ Օգտագործիր վավեր symbol, օրինակ՝ BTCUSDT, կամ local testing-ի համար օգտագործիր Set price։",
    could_not_fetch_binance_price: "Չհաջողվեց բեռնել Binance գինը։",
    updating: "Թարմացվում է…",
    price: "Գին",
    quantity: "Քանակ",
    loading_recent_activity: "Բեռնվում է վերջին ակտիվությունը...",
    loading_generic: "Բեռնվում է…",
    no_recent_activity_yet: "Տեսանելի ակտիվություն դեռ չկա։",
    failed_to_load_recent_activity: "Չհաջողվեց բեռնել վերջին ակտիվությունը։",
    ready_to_run: "Պատրաստ է գործարկման",
    paused_state: "Դադարեցված է",
    not_runnable: "Չի կարող գործարկվել",
    loading_actions: "Բեռնվում են Bot-ի գործողությունները...",
    activate_draft_before_running: "Ակտիվացրու այս draft Bot-ը՝ նախքան գործարկելը։",
    activate_bot: "Ակտիվացնել Bot-ը",
    activating_bot: "Ակտիվացվում է…",
    execution_settings_required_to_activate: "Execution կարգավորումները պարտադիր են այս draft Bot-ը ակտիվացնելուց առաջ։",
    resume_automatic_checks: "Վերսկսիր՝ automatic checks-ը նորից միացնելու համար։",
    paper_mode_orders: "Paper mode-ը օգտագործում է simulated orders։",
    live_mode_orders: "Live mode-ը տեղադրում է real orders։",
    paper_mode: "Paper mode",
    live_mode: "Live mode",
    mode_loading: "Mode-ը բեռնվում է…",
    run_now: "Գործարկել հիմա",
    running_now: "Գործարկվում է…",
    pause: "Դադար",
    resume: "Վերսկսել",
    pause_resume: "Դադար / Վերսկսել",
    select_bot_to_view_actions: "Ընտրիր Bot՝ գործողությունները տեսնելու համար։",
    bot_count_one: "{count} Bot",
    bot_count_other: "{count} Bots",
    filtered_bot_count: "{visible}/{total} Bots",
    last_refreshed: "Վերջին թարմացում",
    loading_bots: "Բեռնվում են Bots...",
    no_bots_yet: "Bot-եր դեռ չկան։ Ստեղծիր Bot՝ այստեղ տեսնելու համար։",
    no_bots_match_search: "Որոնմանը համապատասխան Bot չգտնվեց։",
    details_unavailable: "Մանրամասները հասանելի չեն",
    no_bots_available_yet: "Bot-եր դեռ չկան։",
    select_bot_to_view_details: "Ընտրիր Bot՝ մանրամասները տեսնելու համար։",
    add_bot_to_get_started: "Ավելացրու Bot՝ սկսելու համար",
    no_bot_activity_yet: "Bot-ի ակտիվություն դեռ չկա",
    loading_details: "Բեռնվում են մանրամասները...",
    select_bot_to_view_activity: "Ընտրիր Bot՝ ակտիվությունը տեսնելու համար։",
    no_bots_activity_after_create: "Bot-եր դեռ չկան։ Վերջին ակտիվությունը այստեղ կհայտնվի Bot ստեղծելուց հետո։",
    loading_available_strategies: "Բեռնվում են հասանելի Strategy-ները…",
    strategies_unavailable: "Strategy-ները հասանելի չեն",
    no_strategies_available: "Strategy-ներ չկան",
    could_not_load_strategies: "Չհաջողվեց բեռնել Strategy-ները։ {detail}",
    create_strategy_first_create_bot: "Սկզբում ստեղծիր Strategy, հետո կկարողանաս ստեղծել Bot։",
    create_strategy_first_edit_bot: "Սկզբում ստեղծիր Strategy, հետո կկարողանաս թարմացնել Bot-ի strategy-ն։",
    select_strategy: "Ընտրիր Strategy։",
    enter_bot_name: "Մուտքագրիր Bot-ի անունը։",
    enter_exchange_name: "Մուտքագրիր բորսայի անունը։",
    strategies_still_loading: "Strategy-ները դեռ բեռնվում են։",
    create_strategy_first_then_create_bot: "Սկզբում ստեղծիր Strategy, հետո ստեղծիր Bot։",
    create_strategy_first_then_edit_bot: "Սկզբում ստեղծիր Strategy, հետո խմբագրիր Bot-ի strategy-ն։",
    check_bot_fields: "Ստուգիր Bot-ի ձևի դաշտերը և նորից փորձիր։",
    created_bot_success:
      "Ստեղծվեց {name}։ Այն հիմա ընտրված է և կմնա draft Paper mode Bot, մինչև դու ակտիվացնես այն։",
    updated_bot_success: "Թարմացվեց {name}։",
    price_updated: "Գինը թարմացվեց",
    check_symbol_positive_price: "Ստուգիր Symbol-ը և դրական գինը։",
    manual_run_completed: "Manual run-ը ավարտվեց։ {activity}։",
    manual_run_skipped: "Manual run-ը բաց թողնվեց։ {activity}։",
    manual_run_checked: "Manual run-ը ստուգեց Bot-ը։ {activity}։",
    decision_explanation: "Որոշման բացատրություն",
    risk_limit_blocked_message: "Գործարքը արգելափակվեց ռիսկի կարգավորումներով։",
    risk_max_trade_quantity_exceeded: "Գործարքի քանակը գերազանցում է թույլատրելի սահմանը։",
    risk_max_position_quantity_exceeded: "Դիրքի սահմանաչափը կգերազանցվի։",
    risk_stop_loss_triggered: "Stop-loss կանոնը գործարկվեց։",
    risk_missing_price: "Ռիսկի ստուգումը հնարավոր չէ կատարել, քանի որ գինը բացակայում է։",
    decision_reason_label: "Որոշում / պատճառ",
    risk_reason_label: "Ռիսկի պատճառ",
    decision_bought: "Գնվեց",
    decision_sold: "Վաճառվեց",
    decision_buy: "Buy",
    decision_sell: "Sell",
    decision_hold: "Պահել",
    decision_skipped: "Բաց թողնվեց",
    decision_reason_buy_threshold_reached: "Buy signal կա․ ընթացիկ գինը buy թիրախից ցածր է։",
    decision_reason_sell_threshold_reached: "Sell signal կա․ ընթացիկ գինը sell թիրախից բարձր է։",
    decision_reason_no_buy_signal: "Buy signal չկա․ ընթացիկ գինը buy թիրախից բարձր է։",
    decision_reason_no_sell_signal: "Position-ը պահվում է․ ընթացիկ գինը sell թիրախից ցածր է։",
    decision_reason_ma_buy_signal: "Buy signal կա․ moving average-ները վերև են հատվել։",
    decision_reason_ma_sell_signal: "Sell signal կա․ moving average-ները ներքև են հատվել։",
    decision_reason_ma_no_buy_signal: "Buy signal չկա․ moving average-ները վերև չեն հատվել։",
    decision_reason_ma_no_sell_signal: "Position-ը պահվում է․ moving average-ները ներքև չեն հատվել։",
    decision_reason_insufficient_candles: "Որոշում կայացնելու համար candle տվյալները բավարար չեն։",
    decision_reason_no_latest_price: "Վերջին գինը հասանելի չէ։",
    decision_reason_strategy_not_supported: "Այս strategy type-ը դեռ չի աջակցվում։",
    decision_reason_invalid_strategy_parameter: "Strategy-ի պարամետրերը պետք է ստուգել։",
    decision_reason_order_quantity_missing: "Order-ի քանակը կարգավորված չէ։",
    current_price_label: "Ընթացիկ գին",
    buy_threshold_label: "Buy-ից ցածր",
    sell_threshold_label: "Sell-ից բարձր",
    position_qty_label: "Position քանակ",
    decision_label: "Որոշում",
    request_failed_404: "Պահանջված Bot-ը չգտնվեց։",
    request_failed_422: "Ստուգիր ուղարկված արժեքները և նորից փորձիր։",
    could_not_update_price: "Չհաջողվեց թարմացնել գինը։",
    could_not_create_bot: "Չհաջողվեց ստեղծել Bot։",
    could_not_update_bot: "Չհաջողվեց թարմացնել Bot-ը։",
    could_not_delete_bot: "Չհաջողվեց ջնջել Bot-ը։",
    could_not_load_bot_settings: "Չհաջողվեց բեռնել Bot-ի կարգավորումները։",
    could_not_load_bot_details: "Չհաջողվեց բեռնել Bot-ի մանրամասները։",
    could_not_load_bots: "Չհաջողվեց բեռնել Bots։",
    could_not_refresh: "Չհաջողվեց թարմացնել։",
    auto_refresh_failed: "Auto-refresh-ը ձախողվեց։ {detail}",
    please_try_again: "Խնդրում ենք նորից փորձել։",
    could_not_run_bot: "Չհաջողվեց գործարկել Bot-ը։",
    could_not_pause_bot: "Չհաջողվեց դադարեցնել Bot-ը։",
    could_not_resume_bot: "Չհաջողվեց վերսկսել Bot-ը։",
    could_not_activate_bot: "Չհաջողվեց ակտիվացնել Bot-ը։",
    market_price_update: "Market price update",
    language_switcher: "Լեզվի ընտրիչ",
    bot_dashboard_aria: "Bot dashboard",
    bots_aria: "Bots",
    create_bot_aria: "Create Bot",
    edit_bot_aria: "Edit Bot",
    recent_activity_aria: "Վերջին ակտիվություն",
    loading_strategies: "Բեռնվում են Strategy-ները…",
    create_bot_hint_name: "Momentum Bot",
    mode_ready: "Պատրաստ է",
    side_label: "Կողմ",
    price_label: "Գին",
    quantity_label: "Քանակ",
    cooldown_until: "Cooldown մինչև",
    activity_success: "Հաջող",
    activity_skipped: "Բաց թողնված",
    activity_failed: "Սխալ",
    activity_running: "Ընթացքում",
    activity_event: "Իրադարձություն",
    order_filled: "Պատվերը կատարված է",
    run_event: "Run իրադարձություն",
    bot_event: "Bot իրադարձություն",
    activity_buy_filled: "Buy order-ը կատարվեց",
    activity_sell_filled: "Sell order-ը կատարվեց",
    activity_order_filled: "Պատվերը կատարված է",
    activity_order_rejected: "Order-ը մերժվեց",
    activity_buy_signal: "Buy signal գտնվեց",
    activity_sell_signal: "Sell signal գտնվեց",
    activity_evaluation_skipped: "Ստուգումը բաց թողնվեց․ գործարք չկատարվեց",
    activity_evaluation_no_signal: "Շուկան ստուգվեց․ signal չկա",
    activity_bot_paused: "Bot-ը դադարեցվեց",
    activity_bot_resumed: "Bot-ը վերսկսվեց",
    activity_bot_resume_requested: "Bot-ը վերսկսվեց",
    activity_bot_skipped_paused: "Bot-ը դադարեցված է․ ստուգումը բաց թողնվեց",
    activity_bot_not_active: "Bot-ը ակտիվ չէ․ ստուգումը բաց թողնվեց",
    activity_execution_profile_missing: "Execution կարգավորումները բացակայում են․ ստուգումը բաց թողնվեց",
    activity_execution_profile_disabled: "Execution կարգավորումներն անջատված են․ ստուգումը բաց թողնվեց",
    activity_cooldown_active: "Սպասում է cooldown-ի ավարտին՝ հաջորդ trade-ից առաջ",
    activity_live_mode_not_implemented: "Live mode-ը դեռ հասանելի չէ․ order չտեղադրվեց",
    activity_unsupported_strategy_type: "Strategy-ի type-ը չի աջակցվում․ ստուգումը բաց թողնվեց",
    activity_strategy_inactive: "Strategy-ն ակտիվ չէ․ ստուգումը բաց թողնվեց",
    activity_started: "Bot-ը գործարկվեց",
    activity_stopped: "Bot-ը կանգնեցվեց",
    activity_error: "Գործարկման սխալ",
    activity_run_requested_system: "Automatic run պահանջվեց",
    activity_run_requested_manual: "Manual run պահանջվեց",
    activity_run_started: "Run-ը սկսվեց",
    activity_run_status_updated: "Run-ի status-ը թարմացվեց",
    activity_side_buy: "Buy",
    activity_side_sell: "Sell",
    bot_prefix: "Bot",
    active_until: "Ակտիվ մինչև",
    active: "Ակտիվ է",
    not_active: "Ակտիվ չէ",
    configured_seconds: "{value}վ կարգավորված",
    unnamed_bot: "Անանուն Bot",
    unnamed_strategy: "Անանուն Strategy",
    activity_update: "Ակտիվության թարմացում",
  },
};

const headerMeta = document.querySelector("#header-meta");
const topbarEyebrow = document.querySelector("#topbar-eyebrow");
const dashboardTitle = document.querySelector("#dashboard-title");
const botList = document.querySelector("#bot-list");
const botCount = document.querySelector("#bot-count");
const botSearch = document.querySelector("#bot-search");
const toggleCreateBot = document.querySelector("#toggle-create-bot");
const languageSwitcher = document.querySelector("#language-switcher");
const langEn = document.querySelector("#lang-en");
const langAm = document.querySelector("#lang-am");
const autoRefreshLabel = document.querySelector("#auto-refresh-label");
const priceSymbolLabel = document.querySelector("#price-symbol-label");
const priceValueLabel = document.querySelector("#price-value-label");
const createBotForm = document.querySelector("#create-bot-form");
const botsHeading = document.querySelector("#bots-heading");
const createBotDefaults = document.querySelector("#create-bot-defaults");
const createBotNameLabel = document.querySelector("#create-bot-name-label");
const createBotStrategyLabel = document.querySelector("#create-bot-strategy-label");
const createBotExchangeLabel = document.querySelector("#create-bot-exchange-label");
const createBotNotesLabel = document.querySelector("#create-bot-notes-label");
const createBotName = document.querySelector("#create-bot-name");
const createBotStrategyId = document.querySelector("#create-bot-strategy-id");
const createBotStrategyHelp = document.querySelector("#create-bot-strategy-help");
const createBotExchangeName = document.querySelector("#create-bot-exchange-name");
const createBotNotes = document.querySelector("#create-bot-notes");
const createBotSubmit = document.querySelector("#create-bot-submit");
const createBotMessageEl = document.querySelector("#create-bot-message");
const selectedSymbol = document.querySelector("#selected-symbol");
const selectedName = document.querySelector("#selected-name");
const selectedStatus = document.querySelector("#selected-status");
const selectedState = document.querySelector("#selected-state");
const selectedMode = document.querySelector("#selected-mode");
const selectedStrategy = document.querySelector("#selected-strategy");
const selectedCooldown = document.querySelector("#selected-cooldown");
const selectedPrice = document.querySelector("#selected-price");
const selectedLastRun = document.querySelector("#selected-last-run");
const pauseResume = document.querySelector("#pause-resume");
const runNow = document.querySelector("#run-now");
const editBot = document.querySelector("#edit-bot");
const deleteBot = document.querySelector("#delete-bot");
const actionHelp = document.querySelector("#action-help");
const decisionPanel = document.querySelector("#decision-panel");
const editBotForm = document.querySelector("#edit-bot-form");
const editBotSummary = document.querySelector("#edit-bot-summary");
const editBotNameLabel = document.querySelector("#edit-bot-name-label");
const editBotStrategyLabel = document.querySelector("#edit-bot-strategy-label");
const editBotExchangeLabel = document.querySelector("#edit-bot-exchange-label");
const editBotNotesLabel = document.querySelector("#edit-bot-notes-label");
const editBotName = document.querySelector("#edit-bot-name");
const editBotStrategyId = document.querySelector("#edit-bot-strategy-id");
const editBotStrategyHelp = document.querySelector("#edit-bot-strategy-help");
const editBotExchangeName = document.querySelector("#edit-bot-exchange-name");
const editBotNotes = document.querySelector("#edit-bot-notes");
const editBotStatus = document.querySelector("#edit-bot-status");
const editBotMode = document.querySelector("#edit-bot-mode");
const editBotSubmit = document.querySelector("#edit-bot-submit");
const editBotCancel = document.querySelector("#edit-bot-cancel");
const editBotMessageEl = document.querySelector("#edit-bot-message");
const actionMessageEl = document.querySelector("#action-message");
const refreshDashboard = document.querySelector("#refresh-dashboard");
const autoRefresh = document.querySelector("#auto-refresh");
const refreshMessageEl = document.querySelector("#refresh-message");
const selectedStrategyLabel = document.querySelector("#selected-strategy-label");
const selectedCooldownLabel = document.querySelector("#selected-cooldown-label");
const selectedPriceLabel = document.querySelector("#selected-price-label");
const selectedLastRunLabel = document.querySelector("#selected-last-run-label");
const botSettingsPanel = document.querySelector(".bot-settings-panel");
const botSettingsHeading = document.querySelector("#bot-settings-heading");
const botSettingsContent = document.querySelector("#bot-settings-content");
const executionSettingsPanel = document.querySelector(".execution-settings-panel");
const executionSettingsHeading = document.querySelector("#execution-settings-heading");
const executionSettingsHelp = document.querySelector("#execution-settings-help");
const executionSettingsForm = document.querySelector("#execution-settings-form");
const executionExchangeLabel = document.querySelector("#execution-exchange-label");
const executionExchangeName = document.querySelector("#execution-exchange-name");
const executionIsPaper = document.querySelector("#execution-is-paper");
const executionIsPaperLabel = document.querySelector("#execution-is-paper-label");
const executionBuyThresholdLabel = document.querySelector("#execution-buy-threshold-label");
const executionBuyThreshold = document.querySelector("#execution-buy-threshold");
const executionSellThresholdLabel = document.querySelector("#execution-sell-threshold-label");
const executionSellThreshold = document.querySelector("#execution-sell-threshold");
const executionQuantityLabel = document.querySelector("#execution-quantity-label");
const executionQuantity = document.querySelector("#execution-quantity");
const executionCooldownSecondsLabel = document.querySelector("#execution-cooldown-seconds-label");
const executionCooldownSeconds = document.querySelector("#execution-cooldown-seconds");
const executionMaxPositionSizeLabel = document.querySelector("#execution-max-position-size-label");
const executionMaxPositionSize = document.querySelector("#execution-max-position-size");
const executionMaxDailyLossLabel = document.querySelector("#execution-max-daily-loss-label");
const executionMaxDailyLoss = document.querySelector("#execution-max-daily-loss");
const executionMaxOpenPositionsLabel = document.querySelector("#execution-max-open-positions-label");
const executionMaxOpenPositions = document.querySelector("#execution-max-open-positions");
const executionMaxTradeQuantityLabel = document.querySelector("#execution-max-trade-quantity-label");
const executionMaxTradeQuantity = document.querySelector("#execution-max-trade-quantity");
const executionMaxPositionQuantityLabel = document.querySelector("#execution-max-position-quantity-label");
const executionMaxPositionQuantity = document.querySelector("#execution-max-position-quantity");
const executionStopLossPercentLabel = document.querySelector("#execution-stop-loss-percent-label");
const executionStopLossPercent = document.querySelector("#execution-stop-loss-percent");
const executionSettingsSubmit = document.querySelector("#execution-settings-submit");
const executionSettingsMessageEl = document.querySelector("#execution-settings-message");
const strategyParametersHeading = document.querySelector("#strategy-parameters-heading");
const strategyParametersContent = document.querySelector("#strategy-parameters-content");
const editStrategyParameters = document.querySelector("#edit-strategy-parameters");
const strategyParametersForm = document.querySelector("#strategy-parameters-form");
const strategyBuyBelowLabel = document.querySelector("#strategy-buy-below-label");
const strategySellAboveLabel = document.querySelector("#strategy-sell-above-label");
const strategyQuantityLabel = document.querySelector("#strategy-quantity-label");
const strategyBuyBelow = document.querySelector("#strategy-buy-below");
const strategySellAbove = document.querySelector("#strategy-sell-above");
const strategyQuantity = document.querySelector("#strategy-quantity");
const strategyParametersSubmit = document.querySelector("#strategy-parameters-submit");
const strategyParametersCancel = document.querySelector("#strategy-parameters-cancel");
const strategyParametersMessageEl = document.querySelector("#strategy-parameters-message");
const riskSettingsPanel = document.querySelector(".risk-settings-panel");
const riskSettingsHeading = document.querySelector("#risk-settings-heading");
const riskSettingsHelp = document.querySelector("#risk-settings-help");
const riskSettingsSummary = document.querySelector("#risk-settings-summary");
const riskSettingsForm = document.querySelector("#risk-settings-form");
const riskMaxTradeQuantityLabel = document.querySelector("#risk-max-trade-quantity-label");
const riskMaxTradeQuantity = document.querySelector("#risk-max-trade-quantity");
const riskMaxTradeQuantityHelp = document.querySelector("#risk-max-trade-quantity-help");
const riskMaxPositionQuantityLabel = document.querySelector("#risk-max-position-quantity-label");
const riskMaxPositionQuantity = document.querySelector("#risk-max-position-quantity");
const riskMaxPositionQuantityHelp = document.querySelector("#risk-max-position-quantity-help");
const riskStopLossPercentLabel = document.querySelector("#risk-stop-loss-percent-label");
const riskStopLossPercent = document.querySelector("#risk-stop-loss-percent");
const riskStopLossPercentHelp = document.querySelector("#risk-stop-loss-percent-help");
const riskSettingsSubmit = document.querySelector("#risk-settings-submit");
const riskSettingsMessageEl = document.querySelector("#risk-settings-message");
const backtestPanel = document.querySelector(".backtest-panel");
const backtestHeading = document.querySelector("#backtest-heading");
const backtestOverview = document.querySelector("#backtest-overview");
const backtestForm = document.querySelector("#backtest-form");
const backtestStrategyLabel = document.querySelector("#backtest-strategy-label");
const backtestStrategyId = document.querySelector("#backtest-strategy-id");
const backtestStrategyHelp = document.querySelector("#backtest-strategy-help");
const backtestInitialBalanceLabel = document.querySelector("#backtest-initial-balance-label");
const backtestInitialBalance = document.querySelector("#backtest-initial-balance");
const backtestSourceLabel = document.querySelector("#backtest-source-label");
const backtestSource = document.querySelector("#backtest-source");
const backtestCandleLimitLabel = document.querySelector("#backtest-candle-limit-label");
const backtestCandleLimit = document.querySelector("#backtest-candle-limit");
const backtestCandleLimitHelp = document.querySelector("#backtest-candle-limit-help");
const backtestImportBinance = document.querySelector("#backtest-import-binance");
const backtestImportMessageEl = document.querySelector("#backtest-import-message");
const backtestSubmit = document.querySelector("#backtest-submit");
const backtestMessageEl = document.querySelector("#backtest-message");
const backtestOptimizationHeading = document.querySelector("#backtest-optimization-heading");
const backtestOptimizationHelp = document.querySelector("#backtest-optimization-help");
const backtestOptimizationForm = document.querySelector("#backtest-optimization-form");
const optimizationFirstValuesLabel = document.querySelector("#optimization-first-values-label");
const optimizationFirstValues = document.querySelector("#optimization-first-values");
const optimizationSecondValuesLabel = document.querySelector("#optimization-second-values-label");
const optimizationSecondValues = document.querySelector("#optimization-second-values");
const optimizationQuantityLabel = document.querySelector("#optimization-quantity-label");
const optimizationQuantity = document.querySelector("#optimization-quantity");
const optimizationMinClosedTradesLabel = document.querySelector("#optimization-min-closed-trades-label");
const optimizationMinClosedTrades = document.querySelector("#optimization-min-closed-trades");
const optimizationRequireClosedPositionLabel = document.querySelector("#optimization-require-closed-position-label");
const optimizationRequireClosedPosition = document.querySelector("#optimization-require-closed-position");
const backtestOptimizationSubmit = document.querySelector("#backtest-optimization-submit");
const backtestOptimizationMessageEl = document.querySelector("#backtest-optimization-message");
const backtestOptimizationResultEl = document.querySelector("#backtest-optimization-result");
const backtestResultEl = document.querySelector("#backtest-result");
const backtestHistoryPanel = document.querySelector(".backtest-history-panel");
const backtestHistoryHeading = document.querySelector("#backtest-history-heading");
const refreshBacktestHistory = document.querySelector("#refresh-backtest-history");
const backtestHistoryEl = document.querySelector("#backtest-history");
const recentActivityHeading = document.querySelector("#recent-activity-heading");
const activityList = document.querySelector("#activity-list");
const priceForm = document.querySelector("#price-form");
const priceSymbol = document.querySelector("#price-symbol");
const priceValue = document.querySelector("#price-value");
const priceSubmit = document.querySelector("#price-submit");
const binancePriceFetch = document.querySelector("#binance-price-fetch");
const priceMessageEl = document.querySelector("#price-message");

function getStoredLanguage() {
  const storedLanguage = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
  return SUPPORTED_LANGUAGES.has(storedLanguage) ? storedLanguage : DEFAULT_LANGUAGE;
}

function t(key, params = {}) {
  const template =
    translations[currentLanguage]?.[key] ??
    translations[DEFAULT_LANGUAGE]?.[key] ??
    key;
  return Object.entries(params).reduce(
    (result, [name, value]) => result.replaceAll(`{${name}}`, String(value)),
    template,
  );
}

const RISK_MESSAGE_LABELS = {
  risk_limit_blocked: "risk_limit_blocked_message",
  max_trade_quantity_exceeded: "risk_max_trade_quantity_exceeded",
  max_position_quantity_exceeded: "risk_max_position_quantity_exceeded",
  stop_loss_triggered: "risk_stop_loss_triggered",
  missing_price: "risk_missing_price",
};

const DECISION_REASON_LABELS = {
  entry_threshold_reached: "decision_reason_buy_threshold_reached",
  price_is_below_strategy_buy_below: "decision_reason_buy_threshold_reached",
  exit_threshold_reached: "decision_reason_sell_threshold_reached",
  price_is_above_strategy_sell_above_and_position_exists: "decision_reason_sell_threshold_reached",
  entry_threshold_not_met: "decision_reason_no_buy_signal",
  price_did_not_go_below_buy_below_so_no_buy_signal: "decision_reason_no_buy_signal",
  exit_threshold_not_met: "decision_reason_no_sell_signal",
  price_did_not_go_above_sell_above_so_no_sell_signal: "decision_reason_no_sell_signal",
  short_moving_average_crossed_above_long_moving_average: "decision_reason_ma_buy_signal",
  short_moving_average_crossed_below_long_moving_average: "decision_reason_ma_sell_signal",
  moving_averages_did_not_cross_bullish_so_no_buy_signal: "decision_reason_ma_no_buy_signal",
  moving_averages_did_not_cross_bearish_so_no_sell_signal: "decision_reason_ma_no_sell_signal",
  insufficient_candles: "decision_reason_insufficient_candles",
  no_latest_price: "decision_reason_no_latest_price",
  invalid_strategy_parameter: "decision_reason_invalid_strategy_parameter",
  order_quantity_not_configured: "decision_reason_order_quantity_missing",
};

function setLanguage(language) {
  currentLanguage = SUPPORTED_LANGUAGES.has(language) ? language : DEFAULT_LANGUAGE;
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, currentLanguage);
  document.documentElement.lang = currentLanguage === "am" ? "hy" : "en";
  renderLanguageSwitcher();
  applyStaticTranslations();
  render();
}

function renderLanguageSwitcher() {
  langEn.setAttribute("aria-pressed", String(currentLanguage === "en"));
  langAm.setAttribute("aria-pressed", String(currentLanguage === "am"));
  langEn.classList.toggle("active", currentLanguage === "en");
  langAm.classList.toggle("active", currentLanguage === "am");
}

function applyStaticTranslations() {
  document.title = t("dashboard_title");
  topbarEyebrow.textContent = t("topbar_eyebrow");
  dashboardTitle.textContent = t("dashboard_title");
  languageSwitcher.setAttribute("aria-label", t("language_switcher"));
  refreshDashboard.textContent = isRefreshing ? t("refreshing") : t("refresh");
  autoRefreshLabel.textContent = t("auto_refresh");
  document.querySelector(".dashboard-grid")?.setAttribute("aria-label", t("bot_dashboard_aria"));
  document.querySelector(".bot-list-panel")?.setAttribute("aria-label", t("bots_aria"));
  createBotForm.setAttribute("aria-label", t("create_bot_aria"));
  editBotForm.setAttribute("aria-label", t("edit_bot_aria"));
  document.querySelector(".activity-panel")?.setAttribute("aria-label", t("recent_activity_aria"));
  botsHeading.textContent = t("bots_heading");
  createBotDefaults.textContent = t("create_bot_defaults");
  createBotNameLabel.textContent = t("name");
  createBotStrategyLabel.textContent = t("strategy");
  createBotExchangeLabel.textContent = t("exchange");
  createBotNotesLabel.textContent = t("notes");
  createBotName.placeholder = t("create_bot_hint_name");
  createBotNotes.placeholder = t("optional_notes");
  botSearch.placeholder = t("search_bots");
  priceForm.setAttribute("aria-label", t("market_price_update"));
  priceSymbolLabel.textContent = t("symbol");
  priceValueLabel.textContent = t("price");
  editBotSummary.textContent = t("edit_bot_summary");
  editBotNameLabel.textContent = t("name");
  editBotStrategyLabel.textContent = t("strategy");
  editBotExchangeLabel.textContent = t("exchange");
  editBotNotesLabel.textContent = t("notes");
  editBotNotes.placeholder = t("optional_notes");
  selectedStrategyLabel.textContent = t("selected_strategy_label");
  selectedCooldownLabel.textContent = t("selected_cooldown_label");
  selectedPriceLabel.textContent = t("selected_price_label");
  selectedLastRunLabel.textContent = t("selected_last_run_label");
  botSettingsHeading.textContent = t("bot_settings");
  botSettingsPanel?.setAttribute("aria-label", t("bot_settings_aria"));
  executionSettingsHeading.textContent = t("execution_settings");
  executionSettingsPanel?.setAttribute("aria-label", t("execution_settings_aria"));
  executionSettingsForm.setAttribute("aria-label", t("create_execution_settings_aria"));
  executionSettingsHelp.textContent = t("execution_settings_help");
  executionExchangeLabel.textContent = t("exchange");
  executionIsPaperLabel.textContent = t("paper_mode");
  executionBuyThresholdLabel.textContent = t("buy_threshold_label");
  executionSellThresholdLabel.textContent = t("sell_threshold_label");
  executionQuantityLabel.textContent = t("quantity");
  executionCooldownSecondsLabel.textContent = t("cooldown_seconds_label");
  executionMaxPositionSizeLabel.textContent = t("max_position_size_usd_label");
  executionMaxDailyLossLabel.textContent = t("max_daily_loss_usd_label");
  executionMaxOpenPositionsLabel.textContent = t("max_open_positions_label");
  executionMaxTradeQuantityLabel.textContent = t("max_trade_quantity_label");
  executionMaxPositionQuantityLabel.textContent = t("max_position_quantity_label");
  executionStopLossPercentLabel.textContent = t("stop_loss_percent_label");
  executionSettingsSubmit.textContent = isCreatingExecutionProfile
    ? t("creating_execution_settings")
    : t("create_execution_settings");
  strategyParametersHeading.textContent = t("strategy_parameters");
  editStrategyParameters.textContent = t("edit_strategy_parameters");
  editStrategyParameters.setAttribute("aria-label", t("edit_strategy_parameters_aria"));
  strategyParametersForm.setAttribute("aria-label", t("edit_strategy_parameters_aria"));
  strategyBuyBelowLabel.textContent = t("buy_below_label");
  strategySellAboveLabel.textContent = t("sell_above_label");
  strategyQuantityLabel.textContent = t("quantity");
  strategyParametersSubmit.textContent = isSavingStrategyParameters ? t("saving") : t("save");
  strategyParametersCancel.textContent = t("cancel");
  document
    .querySelector(".strategy-parameters-panel")
    ?.setAttribute("aria-label", t("strategy_parameters"));
  riskSettingsHeading.textContent = t("risk_settings");
  riskSettingsPanel?.setAttribute("aria-label", t("risk_settings_aria"));
  riskSettingsSummary?.setAttribute("aria-label", t("risk_rule_status_aria"));
  riskSettingsForm.setAttribute("aria-label", t("risk_settings_aria"));
  riskSettingsHelp.textContent = t("risk_settings_help");
  riskMaxTradeQuantityLabel.textContent = t("max_trade_quantity_label");
  riskMaxPositionQuantityLabel.textContent = t("max_position_quantity_label");
  riskStopLossPercentLabel.textContent = t("stop_loss_percent_label");
  riskMaxTradeQuantityHelp.textContent = t("max_trade_quantity_help");
  riskMaxPositionQuantityHelp.textContent = t("max_position_quantity_help");
  riskStopLossPercentHelp.textContent = t("stop_loss_percent_help");
  riskSettingsSubmit.textContent = isSavingRiskSettings ? t("saving") : t("save");
  backtestHeading.textContent = t("backtest");
  backtestOverview.textContent = t("backtest_overview");
  backtestPanel?.setAttribute("aria-label", t("backtest"));
  backtestForm.setAttribute("aria-label", t("backtest_aria"));
  backtestStrategyLabel.textContent = t("strategy");
  backtestInitialBalanceLabel.textContent = t("initial_balance_label");
  backtestSourceLabel.textContent = t("source_label");
  backtestCandleLimitLabel.textContent = t("candle_limit_label");
  backtestCandleLimitHelp.textContent = t("candle_limit_help");
  backtestImportBinance.textContent = isImportingBacktestCandles
    ? t("importing_binance_candles")
    : t("import_binance_candles");
  backtestSubmit.textContent = isRunningBacktest ? t("running_backtest") : t("run_backtest");
  backtestOptimizationHeading.textContent = t("parameter_optimization");
  backtestOptimizationForm.setAttribute("aria-label", t("parameter_optimization_aria"));
  backtestOptimizationSubmit.textContent = isRunningBacktestOptimization
    ? t("running_optimization")
    : t("run_optimization");
  optimizationMinClosedTradesLabel.textContent = t("optimization_min_closed_trades_label");
  optimizationRequireClosedPositionLabel.textContent = t("optimization_require_closed_position_label");
  backtestHistoryPanel?.setAttribute("aria-label", t("recent_backtests_aria"));
  backtestHistoryHeading.textContent = t("recent_backtests");
  refreshBacktestHistory.textContent = isLoadingBacktestHistory
    ? t("refreshing_backtest_history")
    : t("refresh_backtest_history");
  recentActivityHeading.textContent = t("recent_activity");
  toggleCreateBot.textContent = isCreateBotOpen ? t("close") : t("create_bot");
  createBotSubmit.textContent = isCreatingBot ? t("creating") : t("create_draft_bot");
  editBot.textContent = isLoadingEditBot ? t("loading_generic") : t("edit");
  deleteBot.textContent = isDeletingBot ? t("deleting_bot") : t("delete_bot");
  editBotSubmit.textContent = isSavingEditBot ? t("saving") : t("save_changes");
  editBotCancel.textContent = t("cancel");
  priceSubmit.textContent = isUpdatingPrice ? t("updating") : t("set_price");
  binancePriceFetch.textContent = isFetchingBinancePrice
    ? t("fetching_binance_price")
    : t("fetch_binance_price");
}

function normalizeBot(rawBot) {
  return {
    id: rawBot.bot_id ?? rawBot.id,
    name: rawBot.name ?? "",
    strategyId: rawBot.strategy_id ?? rawBot.strategyId ?? null,
    status: rawBot.status ?? "idle",
    isPaused: rawBot.is_paused ?? false,
    strategyType: normalizeStrategyType(rawBot.strategy_type ?? rawBot.strategyType ?? ""),
    symbol: rawBot.symbol ?? "",
    cooldownActive: rawBot.cooldown_active ?? false,
    cooldownUntil: rawBot.cooldown_until ?? null,
    currentPositionQty: rawBot.current_position_qty ?? "0",
    lastPrice: rawBot.last_price ?? null,
    updatedAt: rawBot.updated_at ?? null,
  };
}

function normalizeBotsResponse(data) {
  const rawBots = Array.isArray(data) ? data : data.items ?? [];
  return Array.isArray(rawBots) ? rawBots.map(normalizeBot) : [];
}

function normalizeSummary(rawSummary) {
  return {
    ...normalizeBot(rawSummary),
    strategyId: rawSummary.strategy_id ?? rawSummary.strategyId ?? rawSummary.strategy?.id ?? null,
    strategyName: rawSummary.strategy_name ?? "",
    strategyTimeframe: rawSummary.strategy_timeframe ?? "",
    strategyParameters:
      rawSummary.strategy_parameters && typeof rawSummary.strategy_parameters === "object"
        ? rawSummary.strategy_parameters
        : {},
    cooldownSeconds: rawSummary.cooldown_seconds ?? null,
    recentActivity: Array.isArray(rawSummary.recent_activity)
      ? rawSummary.recent_activity
      : [],
  };
}

function normalizeStrategy(rawStrategy) {
  return {
    id: rawStrategy.id,
    name: rawStrategy.name ?? "",
    symbol: rawStrategy.symbol ?? "",
    timeframe: rawStrategy.timeframe ?? "",
    strategyType: normalizeStrategyType(rawStrategy.strategy_type ?? rawStrategy.strategyType ?? ""),
    parameters:
      rawStrategy.parameters && typeof rawStrategy.parameters === "object"
        ? rawStrategy.parameters
        : {},
    isActive: rawStrategy.is_active ?? true,
  };
}

function normalizeStrategiesResponse(data) {
  const rawStrategies = Array.isArray(data) ? data : data?.items ?? [];
  return Array.isArray(rawStrategies) ? rawStrategies.map(normalizeStrategy) : [];
}

function normalizeStrategyType(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_")
    .replace(/\s+/g, "_");
}

function normalizeBotConfig(rawBot) {
  return {
    id: rawBot.id,
    name: rawBot.name ?? "",
    strategyId: rawBot.strategy_id ?? null,
    exchangeName: rawBot.exchange_name ?? "",
    notes: rawBot.notes ?? "",
    status: rawBot.status ?? "draft",
    isPaper: rawBot.is_paper ?? true,
  };
}

function normalizeExecutionProfile(rawProfile) {
  if (!rawProfile || typeof rawProfile !== "object") return null;
  return {
    id: rawProfile.id ?? null,
    botId: rawProfile.bot_id ?? rawProfile.botId ?? null,
    maxTradeQuantity: rawProfile.max_trade_quantity ?? rawProfile.maxTradeQuantity ?? null,
    maxPositionQuantity: rawProfile.max_position_quantity ?? rawProfile.maxPositionQuantity ?? null,
    stopLossPercent: rawProfile.stop_loss_percent ?? rawProfile.stopLossPercent ?? null,
  };
}

function normalizeDecisionExplanation(rawExplanation) {
  if (!rawExplanation || typeof rawExplanation !== "object") return null;
  const reason = firstAvailable(rawExplanation.reason, rawExplanation.detail, rawExplanation.message, "");
  const reasonLabel = getRiskMessage(reason) || humanizeMessage(reason, reason);
  return {
    currentPrice: rawExplanation.current_price ?? rawExplanation.currentPrice ?? null,
    buyBelow: rawExplanation.buy_below ?? rawExplanation.buyBelow ?? null,
    sellAbove: rawExplanation.sell_above ?? rawExplanation.sellAbove ?? null,
    positionQty: rawExplanation.position_qty ?? rawExplanation.positionQty ?? null,
    decision: rawExplanation.decision ?? "",
    reason,
    detail: rawExplanation.detail ?? "",
    message: rawExplanation.message ?? "",
    reasonLabel,
  };
}

function normalizeBacktestResult(rawResult) {
  if (!rawResult || typeof rawResult !== "object") return null;
  return {
    symbol: rawResult.symbol ?? "",
    timeframe: rawResult.timeframe ?? "",
    strategyType: normalizeStrategyType(rawResult.strategy_type ?? rawResult.strategyType ?? ""),
    source: rawResult.source ?? "",
    initialBalance: rawResult.initial_balance ?? null,
    finalBalance: rawResult.final_balance ?? null,
    realizedPnl: rawResult.realized_pnl ?? null,
    unrealizedPnl: rawResult.unrealized_pnl ?? null,
    numberOfTrades: rawResult.number_of_trades ?? 0,
    closedTrades: rawResult.closed_trades ?? 0,
    openPosition: rawResult.open_position ?? false,
    positionQuantity: rawResult.position_quantity ?? null,
    entryPrice: rawResult.entry_price ?? null,
    totalReturn: rawResult.total_return ?? null,
    totalReturnPercent: rawResult.total_return_percent ?? null,
    winRate: rawResult.win_rate ?? null,
    averageTradePnl: rawResult.average_trade_pnl ?? null,
    bestTradePnl: rawResult.best_trade_pnl ?? null,
    worstTradePnl: rawResult.worst_trade_pnl ?? null,
    profitFactor: rawResult.profit_factor ?? null,
    candlesProcessed: rawResult.candles_processed ?? rawResult.candlesProcessed ?? null,
    trades: Array.isArray(rawResult.trades) ? rawResult.trades.map(normalizeBacktestTrade) : [],
  };
}

function normalizeBacktestTrade(rawTrade) {
  const trade = rawTrade && typeof rawTrade === "object" ? rawTrade : {};
  const side = firstAvailable(trade.side, trade.decision, "");
  return {
    openedAt: firstAvailable(trade.opened_at, trade.openedAt, null),
    decision: firstAvailable(trade.decision, side, ""),
    side,
    symbol: firstAvailable(trade.symbol, ""),
    price: firstAvailable(trade.price, null),
    quantity: firstAvailable(trade.quantity, null),
    cashBalance: firstAvailable(trade.cash_balance, trade.cashBalance, null),
    positionQuantity: firstAvailable(trade.position_quantity, trade.positionQuantity, null),
    realizedPnl: firstAvailable(trade.realized_pnl, trade.realizedPnl, null),
    decisionReason: firstAvailable(trade.decision_reason, trade.decisionReason, trade.reason, ""),
  };
}

function normalizeBacktestHistoryItem(rawItem) {
  return {
    id: rawItem.id,
    strategyId: rawItem.strategy_id ?? rawItem.strategyId ?? null,
    symbol: rawItem.symbol ?? "",
    timeframe: rawItem.timeframe ?? "",
    strategyType: normalizeStrategyType(rawItem.strategy_type ?? rawItem.strategyType ?? ""),
    source: rawItem.source ?? "",
    initialBalance: rawItem.initial_balance ?? null,
    finalBalance: rawItem.final_balance ?? null,
    realizedPnl: rawItem.realized_pnl ?? null,
    totalReturn: rawItem.total_return ?? null,
    totalReturnPercent: rawItem.total_return_percent ?? null,
    winRate: rawItem.win_rate ?? null,
    profitFactor: rawItem.profit_factor ?? null,
    numberOfTrades: rawItem.number_of_trades ?? 0,
    winningTrades: rawItem.winning_trades ?? null,
    losingTrades: rawItem.losing_trades ?? null,
    candlesProcessed: rawItem.candles_processed ?? null,
    createdAt: rawItem.created_at ?? null,
  };
}

function normalizeBacktestHistoryResponse(data) {
  const rawItems = Array.isArray(data) ? data : data?.items ?? [];
  return Array.isArray(rawItems) ? rawItems.map(normalizeBacktestHistoryItem) : [];
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function normalizeOptimizationResultItem(rawItem) {
  const closedTrades = firstAvailable(rawItem.closed_trades, rawItem.closedTrades, 0);
  const openPosition = firstAvailable(rawItem.open_position, rawItem.openPosition, false);
  const qualityWarnings = firstAvailable(rawItem.quality_warnings, rawItem.qualityWarnings, []);
  return {
    rank: firstAvailable(rawItem.rank, null),
    parameters: objectValue(rawItem.parameters),
    baseParameters: objectValue(firstAvailable(rawItem.base_parameters, rawItem.baseParameters, {})),
    parameterOverrides: objectValue(firstAvailable(rawItem.parameter_overrides, rawItem.parameterOverrides, {})),
    effectiveParameters: objectValue(firstAvailable(rawItem.effective_parameters, rawItem.effectiveParameters, {})),
    finalBalance: firstAvailable(rawItem.final_balance, rawItem.finalBalance, null),
    totalReturn: firstAvailable(rawItem.total_return, rawItem.totalReturn, null),
    totalReturnPercent: firstAvailable(rawItem.total_return_percent, rawItem.totalReturnPercent, null),
    winRate: firstAvailable(rawItem.win_rate, rawItem.winRate, null),
    profitFactor: firstAvailable(rawItem.profit_factor, rawItem.profitFactor, null),
    numberOfTrades: firstAvailable(rawItem.number_of_trades, rawItem.numberOfTrades, 0),
    closedTrades,
    openPosition,
    positionQuantity: firstAvailable(rawItem.position_quantity, rawItem.positionQuantity, null),
    entryPrice: firstAvailable(rawItem.entry_price, rawItem.entryPrice, null),
    hasClosedTrades: firstAvailable(rawItem.has_closed_trades, rawItem.hasClosedTrades, Number(closedTrades) > 0),
    hasOpenPosition: firstAvailable(rawItem.has_open_position, rawItem.hasOpenPosition, Boolean(openPosition)),
    passesQualityFilters: firstAvailable(rawItem.passes_quality_filters, rawItem.passesQualityFilters, true),
    qualityWarnings: Array.isArray(qualityWarnings) ? qualityWarnings : [],
  };
}

function normalizeOptimizationResponse(data) {
  return {
    strategyId: data.strategy_id ?? null,
    symbol: data.symbol ?? "",
    timeframe: data.timeframe ?? "",
    strategyType: normalizeStrategyType(data.strategy_type ?? ""),
    source: data.source ?? null,
    initialBalance: data.initial_balance ?? null,
    totalRuns: data.total_runs ?? 0,
    results: Array.isArray(data.results) ? data.results.map(normalizeOptimizationResultItem) : [],
  };
}

function isBacktestDataIssueMessage(message) {
  const normalized = normalizeRiskReason(message);
  return (
    normalized.includes("candle") ||
    normalized.includes("market_data") ||
    normalized.includes("historical_data") ||
    normalized.includes("insufficient_data") ||
    normalized.includes("not_enough_data")
  );
}

function friendlyBacktestErrorMessage(error, fallback) {
  const message = requestErrorMessage(error, fallback);
  return isBacktestDataIssueMessage(message) ? t("backtest_not_enough_candle_data") : message;
}

function friendlyCandleImportErrorMessage(error) {
  if (error?.status === 422) return t("candle_import_validation_failed");

  const message = String(error?.message || "");
  const normalized = normalizeRiskReason(message);
  if (normalized.includes("symbol")) return t("candle_import_invalid_symbol");
  if (normalized.includes("timeframe") || normalized.includes("interval")) return t("candle_import_invalid_timeframe");
  if (normalized.includes("binance") || normalized.includes("network") || error?.status === 502) {
    return t("candle_import_network_failed");
  }
  return requestErrorMessage(error, t("candle_import_failed"));
}

function backtestResultNotice(result) {
  if (!result) return "";
  const candlesProcessed = Number(result.candlesProcessed);
  if (Number.isFinite(candlesProcessed) && candlesProcessed === 0) {
    return t("backtest_no_candle_data");
  }
  if ((Number.isFinite(candlesProcessed) && candlesProcessed > 0) && result.trades.length === 0) {
    return t("backtest_no_trade_hint");
  }
  return "";
}

function comparableNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function selectBestRecentBacktest(items) {
  return items.reduce((best, item) => {
    if (!best) return item;

    const itemReturnPercent = comparableNumber(item.totalReturnPercent);
    const bestReturnPercent = comparableNumber(best.totalReturnPercent);
    if (itemReturnPercent !== bestReturnPercent) {
      if (itemReturnPercent === null) return best;
      if (bestReturnPercent === null) return item;
      return itemReturnPercent > bestReturnPercent ? item : best;
    }

    const itemTotalReturn = comparableNumber(item.totalReturn);
    const bestTotalReturn = comparableNumber(best.totalReturn);
    if (itemTotalReturn !== bestTotalReturn) {
      if (itemTotalReturn === null) return best;
      if (bestTotalReturn === null) return item;
      return itemTotalReturn > bestTotalReturn ? item : best;
    }

    const itemTime = new Date(item.createdAt || 0).getTime();
    const bestTime = new Date(best.createdAt || 0).getTime();
    return itemTime > bestTime ? item : best;
  }, null);
}

function statusClass(status) {
  if (["active", "running", "enabled"].includes(status)) return "status-active";
  if (["paused", "stopped", "disabled"].includes(status)) return "status-paused";
  return "status-draft";
}

function statusRank(status) {
  if (["active", "running", "enabled"].includes(status)) return 0;
  if (["paused", "stopped", "disabled"].includes(status)) return 1;
  return 2;
}

function shouldPause(status) {
  return ["active", "running", "enabled"].includes(status);
}

function pauseResumeLabel(status) {
  if (status === "draft") return t("activate_bot");
  return shouldPause(status) ? t("pause") : t("resume");
}

function pauseResumeLoadingLabel(status) {
  if (status === "draft") return t("activating_bot");
  return `${pauseResumeLabel(status)}…`;
}

function isRunnableStatus(status) {
  return ["active", "running", "enabled"].includes(status);
}

function formatValue(value, fallback = "—") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function humanizeMessage(value, fallback = "Update") {
  const text = formatValue(value, fallback);
  return text
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatStatus(status) {
  return formatValue(status, "draft").replaceAll("_", " ");
}

function formatDateTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  const parts = new Intl.DateTimeFormat([], {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(parsed);
  const byType = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${byType.year}-${byType.month}-${byType.day} ${byType.hour}:${byType.minute}`;
}

function formatTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

function botCountText(count) {
  return count === 1 ? t("bot_count_one", { count }) : t("bot_count_other", { count });
}

function filteredBots() {
  const query = botSearchQuery.trim().toLowerCase();
  const source = query
    ? bots.filter((bot) =>
        `${bot.name ?? ""} ${bot.symbol ?? ""}`.toLowerCase().includes(query),
      )
    : bots;
  return sortedBots(source);
}

function sortedBots(source) {
  return [...source].sort((left, right) => {
    const rankDiff = statusRank(left.status) - statusRank(right.status);
    if (rankDiff !== 0) return rankDiff;

    const leftName = left.name || left.symbol || String(left.id);
    const rightName = right.name || right.symbol || String(right.id);
    return leftName.localeCompare(rightName, undefined, {
      numeric: true,
      sensitivity: "base",
    });
  });
}

function defaultSelectedBotId(sortedSource) {
  return sortedSource.find((bot) => isRunnableStatus(bot.status))?.id ?? sortedSource[0]?.id ?? null;
}

function botIdsEqual(left, right) {
  return (
    left !== null &&
    left !== undefined &&
    right !== null &&
    right !== undefined &&
    String(left) === String(right)
  );
}

function chooseSelectedBotId(sortedSource) {
  const selectedExists = Boolean(
    selectedBotId && sortedSource.some((bot) => botIdsEqual(bot.id, selectedBotId)),
  );

  if (hasUserSelectedBot && selectedExists) {
    return selectedBotId;
  }

  return defaultSelectedBotId(sortedSource);
}

function formatDecimal(value, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value);
  return new Intl.NumberFormat([], {
    minimumFractionDigits: 0,
    maximumFractionDigits: 8,
  }).format(parsed);
}

function formatPercent(value, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value);
  return `${new Intl.NumberFormat([], {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed)}%`;
}

function formatRatio(value, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value);
  return new Intl.NumberFormat([], {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(parsed);
}

function pnlClass(value, baseline = 0) {
  const parsed = Number(value);
  const parsedBaseline = Number(baseline);
  if (!Number.isFinite(parsed) || !Number.isFinite(parsedBaseline)) return "pnl-neutral";
  const diff = parsed - parsedBaseline;
  if (diff > 0) return "pnl-positive";
  if (diff < 0) return "pnl-negative";
  return "pnl-neutral";
}

function formatParameterValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number" || typeof value === "bigint") return formatDecimal(value);
  if (typeof value === "boolean") return value ? t("active") : t("not_active");
  if (typeof value === "string") return formatDecimal(value, value);
  return JSON.stringify(value);
}

function firstAvailable(...values) {
  return values.find((value) => value !== null && value !== undefined && value !== "");
}

function formatBoolean(value) {
  if (value === null || value === undefined || value === "") return t("not_available");
  return value ? t("yes") : t("no");
}

function strategyParameterLabel(key) {
  const knownLabels = {
    buy_below: t("buy_below_label"),
    sell_above: t("sell_above_label"),
    short_window: t("short_window_label"),
    long_window: t("long_window_label"),
    quantity: t("quantity"),
  };
  return knownLabels[key] ?? humanizeMessage(key, key);
}

function orderedStrategyParameters(parameters) {
  const safeParameters =
    parameters && typeof parameters === "object" && !Array.isArray(parameters)
      ? parameters
      : {};
  const knownOrder = ["buy_below", "sell_above", "short_window", "long_window", "quantity"];
  const knownKeys = knownOrder.filter((key) =>
    Object.prototype.hasOwnProperty.call(safeParameters, key),
  );
  const customKeys = Object.keys(safeParameters)
    .filter((key) => !knownOrder.includes(key))
    .sort((left, right) => left.localeCompare(right));

  return [...knownKeys, ...customKeys].map((key) => ({
    key,
    label: strategyParameterLabel(key),
    value: safeParameters[key],
  }));
}

function strategyIdForSelectedBot() {
  return selectedBotConfig?.strategyId ?? selectedSummary?.strategyId ?? null;
}

function selectedStrategyType() {
  return selectedSummary?.strategyType || "price_threshold";
}

function selectedStrategyParameterFields() {
  const strategyType = selectedStrategyType();
  if (strategyType === "moving_average_cross") {
    return [
      { key: "short_window", label: t("short_window_label"), input: strategyBuyBelow, labelEl: strategyBuyBelowLabel },
      { key: "long_window", label: t("long_window_label"), input: strategySellAbove, labelEl: strategySellAboveLabel },
      { key: "quantity", label: t("quantity"), input: strategyQuantity, labelEl: strategyQuantityLabel },
    ];
  }
  if (strategyType === "price_threshold") {
    return [
      { key: "buy_below", label: t("buy_below_label"), input: strategyBuyBelow, labelEl: strategyBuyBelowLabel },
      { key: "sell_above", label: t("sell_above_label"), input: strategySellAbove, labelEl: strategySellAboveLabel },
      { key: "quantity", label: t("quantity"), input: strategyQuantity, labelEl: strategyQuantityLabel },
    ];
  }
  return [];
}

function canEditSelectedStrategyParameters() {
  return selectedStrategyParameterFields().length > 0;
}

function selectedBotSymbol() {
  const bot = selectedSummary || bots.find((item) => botIdsEqual(item.id, selectedBotId));
  return bot?.symbol ? String(bot.symbol).trim().toUpperCase() : "";
}

function strategyParameterInputValue(key) {
  const value = selectedSummary?.strategyParameters?.[key];
  return value === null || value === undefined ? "" : String(value);
}

function populateStrategyParametersForm() {
  const fields = selectedStrategyParameterFields();
  [strategyBuyBelow, strategySellAbove, strategyQuantity].forEach((input) => {
    input.value = "";
    input.name = "";
  });
  fields.forEach((field) => {
    field.input.value = strategyParameterInputValue(field.key);
    field.input.name = field.key;
  });
}

function parsePositiveParameter(value) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed > 0 ? trimmed : null;
}

function parsePositiveIntegerParameter(value) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!/^[1-9]\d*$/.test(trimmed)) return null;
  const parsed = Number(trimmed);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function validateStrategyParametersForm() {
  if (!strategyIdForSelectedBot()) return t("strategy_details_unavailable");
  if (!canEditSelectedStrategyParameters()) return t("strategy_parameters_edit_unavailable");

  if (selectedStrategyType() === "moving_average_cross") {
    const shortWindow = parsePositiveIntegerParameter(strategyBuyBelow.value);
    const longWindow = parsePositiveIntegerParameter(strategySellAbove.value);
    const quantity = strategyQuantity.value.trim();
    if (!strategyBuyBelow.value.trim() || !strategySellAbove.value.trim()) {
      return t("enter_moving_average_parameters");
    }
    if (shortWindow === null || longWindow === null) {
      return t("moving_average_windows_must_be_integers");
    }
    if (shortWindow >= longWindow) {
      return t("moving_average_short_less_than_long");
    }
    if (quantity && parsePositiveParameter(quantity) === null) {
      return t("strategy_parameters_must_be_numbers");
    }
    return "";
  }

  const values = [strategyBuyBelow.value.trim(), strategySellAbove.value.trim(), strategyQuantity.value.trim()];
  if (values.some((value) => !value)) return t("enter_strategy_parameters");
  if (values.some((value) => parsePositiveParameter(value) === null)) return t("strategy_parameters_must_be_numbers");
  return "";
}

function strategyParameterPayload() {
  const parameters = { ...(selectedSummary?.strategyParameters ?? {}) };
  selectedStrategyParameterFields().forEach((field) => {
    const value = field.input.value.trim();
    if (value) {
      parameters[field.key] = value;
    } else {
      delete parameters[field.key];
    }
  });
  return parameters;
}

function riskSettingsInputValue(key) {
  const value = selectedExecutionProfile?.[key];
  return value === null || value === undefined ? "" : String(value);
}

function populateRiskSettingsForm() {
  riskMaxTradeQuantity.value = riskSettingsInputValue("maxTradeQuantity");
  riskMaxPositionQuantity.value = riskSettingsInputValue("maxPositionQuantity");
  riskStopLossPercent.value = riskSettingsInputValue("stopLossPercent");
}

function validateRiskSettingsForm() {
  if (!selectedBotId || !selectedExecutionProfile) return t("risk_settings_unavailable");
  const values = [
    riskMaxTradeQuantity.value.trim(),
    riskMaxPositionQuantity.value.trim(),
    riskStopLossPercent.value.trim(),
  ];
  if (values.some((value) => value && parsePositiveParameter(value) === null)) {
    return t("risk_settings_must_be_positive");
  }
  return "";
}

function riskSettingsPayload() {
  return {
    max_trade_quantity: riskMaxTradeQuantity.value.trim() || null,
    max_position_quantity: riskMaxPositionQuantity.value.trim() || null,
    stop_loss_percent: riskStopLossPercent.value.trim() || null,
  };
}

function riskRuleStatusLabel(value, formatter = formatDecimal) {
  if (value === null || value === undefined || value === "") return t("risk_rule_disabled");
  return t("risk_rule_active", { value: formatter(value) });
}

function riskSettingsSummaryRows() {
  return [
    {
      label: t("max_trade_quantity_label"),
      value: selectedExecutionProfile?.maxTradeQuantity,
      formatter: formatDecimal,
    },
    {
      label: t("max_position_quantity_label"),
      value: selectedExecutionProfile?.maxPositionQuantity,
      formatter: formatDecimal,
    },
    {
      label: t("stop_loss_percent_label"),
      value: selectedExecutionProfile?.stopLossPercent,
      formatter: formatPercent,
    },
  ];
}

function populateExecutionSettingsForm() {
  executionExchangeName.value = selectedBotConfig?.exchangeName || "binance";
  executionIsPaper.checked = selectedBotConfig?.isPaper !== false;
  executionBuyThreshold.value = executionBuyThreshold.value || "100000";
  executionSellThreshold.value = executionSellThreshold.value || "200000";
  executionQuantity.value = executionQuantity.value || "0.001";
  executionCooldownSeconds.value = executionCooldownSeconds.value || "60";
  executionMaxPositionSize.value = executionMaxPositionSize.value || "100000";
  executionMaxDailyLoss.value = executionMaxDailyLoss.value || "10000";
  executionMaxOpenPositions.value = executionMaxOpenPositions.value || "1";
  executionMaxTradeQuantity.value = executionMaxTradeQuantity.value || "";
  executionMaxPositionQuantity.value = executionMaxPositionQuantity.value || "";
  executionStopLossPercent.value = executionStopLossPercent.value || "";
}

function resetExecutionSettingsForm() {
  [
    executionExchangeName,
    executionBuyThreshold,
    executionSellThreshold,
    executionQuantity,
    executionCooldownSeconds,
    executionMaxPositionSize,
    executionMaxDailyLoss,
    executionMaxOpenPositions,
    executionMaxTradeQuantity,
    executionMaxPositionQuantity,
    executionStopLossPercent,
  ].forEach((input) => {
    input.value = "";
  });
  executionIsPaper.checked = true;
}

function validateExecutionSettingsForm() {
  if (!selectedBotId) return t("select_bot_to_view_details");
  if (!executionExchangeName.value.trim()) return t("enter_exchange_name");

  const requiredNumbers = [
    executionBuyThreshold.value.trim(),
    executionSellThreshold.value.trim(),
    executionQuantity.value.trim(),
    executionMaxPositionSize.value.trim(),
    executionMaxDailyLoss.value.trim(),
  ];
  if (requiredNumbers.some((value) => !value) || !executionCooldownSeconds.value.trim() || !executionMaxOpenPositions.value.trim()) {
    return t("execution_settings_required_fields");
  }
  if (requiredNumbers.some((value) => parsePositiveParameter(value) === null)) {
    return t("execution_settings_positive_numbers");
  }
  if (
    parsePositiveIntegerParameter(executionCooldownSeconds.value) === null ||
    parsePositiveIntegerParameter(executionMaxOpenPositions.value) === null
  ) {
    return t("execution_settings_positive_integers");
  }

  const optionalRiskValues = [
    executionMaxTradeQuantity.value.trim(),
    executionMaxPositionQuantity.value.trim(),
    executionStopLossPercent.value.trim(),
  ];
  if (optionalRiskValues.some((value) => value && parsePositiveParameter(value) === null)) {
    return t("risk_settings_must_be_positive");
  }
  return "";
}

function executionProfilePayload() {
  return {
    max_position_size_usd: executionMaxPositionSize.value.trim(),
    max_daily_loss_usd: executionMaxDailyLoss.value.trim(),
    max_open_positions: parsePositiveIntegerParameter(executionMaxOpenPositions.value),
    strategy_type: "price_threshold",
    entry_below: executionBuyThreshold.value.trim(),
    exit_above: executionSellThreshold.value.trim(),
    order_quantity: executionQuantity.value.trim(),
    cooldown_seconds: parsePositiveIntegerParameter(executionCooldownSeconds.value),
    default_order_type: "market",
    is_enabled: true,
    max_trade_quantity: executionMaxTradeQuantity.value.trim() || null,
    max_position_quantity: executionMaxPositionQuantity.value.trim() || null,
    stop_loss_percent: executionStopLossPercent.value.trim() || null,
  };
}

function executionBotUpdatePayload() {
  const payload = {};
  const exchangeName = executionExchangeName.value.trim();
  if (exchangeName && exchangeName !== selectedBotConfig?.exchangeName) {
    payload.exchange_name = exchangeName;
  }
  if (executionIsPaper.checked !== selectedBotConfig?.isPaper) {
    payload.is_paper = executionIsPaper.checked;
  }
  return payload;
}

function renderStrategyParametersForm() {
  const hasStrategyDetails = Boolean(selectedBotId && selectedSummary && strategyIdForSelectedBot());
  const canEditParameters = hasStrategyDetails && canEditSelectedStrategyParameters();
  const fields = selectedStrategyParameterFields();
  const strategyType = selectedStrategyType();
  const parameterHelp =
    hasStrategyDetails && strategyType === "moving_average_cross"
      ? t("moving_average_parameters_help")
      : hasStrategyDetails && strategyType === "price_threshold"
        ? t("price_threshold_parameters_help")
        : "";
  const shouldDisable =
    !hasStrategyDetails ||
    !canEditParameters ||
    isLoadingSummary ||
    isSavingStrategyParameters ||
    isRunningNow ||
    isTogglingPause;
  const visibleMessage =
    strategyParametersMessage ||
    (hasStrategyDetails && !canEditParameters
      ? t("strategy_parameters_edit_unavailable")
      : parameterHelp);
  const visibleMessageType =
    strategyParametersMessageType || (visibleMessage && visibleMessage !== strategyParametersMessage ? "note" : "");

  fields.forEach((field) => {
    field.labelEl.textContent = field.label;
  });
  editStrategyParameters.textContent = t("edit_strategy_parameters");
  editStrategyParameters.disabled = shouldDisable || isEditingStrategyParameters;
  strategyParametersForm.setAttribute("data-open", String(isEditingStrategyParameters));
  strategyParametersSubmit.textContent = isSavingStrategyParameters ? t("saving") : t("save");
  strategyParametersSubmit.disabled = shouldDisable;
  strategyParametersCancel.textContent = t("cancel");
  strategyParametersCancel.disabled = isSavingStrategyParameters;
  [strategyBuyBelow, strategySellAbove, strategyQuantity].forEach((input) => {
    input.disabled = shouldDisable;
  });
  strategyBuyBelow.inputMode = selectedStrategyType() === "moving_average_cross" ? "numeric" : "decimal";
  strategySellAbove.inputMode = selectedStrategyType() === "moving_average_cross" ? "numeric" : "decimal";
  strategyQuantity.inputMode = "decimal";
  strategyParametersMessageEl.textContent = visibleMessage;
  strategyParametersMessageEl.className = visibleMessageType
    ? `form-message ${visibleMessageType}`
    : "form-message";
}

function renderRiskSettingsForm() {
  const hasProfile = Boolean(selectedBotId && selectedExecutionProfile);
  riskSettingsPanel.hidden = !hasProfile;
  riskSettingsSummary.innerHTML = "";
  const shouldDisable =
    !hasProfile ||
    isLoadingSummary ||
    isSavingRiskSettings ||
    isRunningNow ||
    isTogglingPause;

  riskSettingsSubmit.textContent = isSavingRiskSettings ? t("saving") : t("save");
  riskSettingsSubmit.disabled = shouldDisable;
  [riskMaxTradeQuantity, riskMaxPositionQuantity, riskStopLossPercent].forEach((input) => {
    input.disabled = shouldDisable;
  });

  if (hasProfile && !isSavingRiskSettings && !riskSettingsMessageType) {
    populateRiskSettingsForm();
  } else if (!hasProfile && !isSavingRiskSettings) {
    [riskMaxTradeQuantity, riskMaxPositionQuantity, riskStopLossPercent].forEach((input) => {
      input.value = "";
    });
  }

  if (hasProfile) {
    riskSettingsSummaryRows().forEach((item) => {
      const isActive = item.value !== null && item.value !== undefined && item.value !== "";
      const row = document.createElement("span");
      const label = document.createElement("strong");
      const status = document.createElement("span");
      row.className = "risk-rule-status";
      label.textContent = item.label;
      status.className = isActive
        ? "risk-rule-badge risk-rule-badge-active"
        : "risk-rule-badge risk-rule-badge-disabled";
      status.textContent = riskRuleStatusLabel(item.value, item.formatter);
      row.append(label, status);
      riskSettingsSummary.append(row);
    });
  }

  const visibleMessage =
    riskSettingsMessage ||
    (selectedBotId && !selectedExecutionProfile && !isLoadingSummary ? t("risk_settings_unavailable") : "");
  const visibleMessageType =
    riskSettingsMessageType || (visibleMessage && visibleMessage !== riskSettingsMessage ? "note" : "");
  riskSettingsMessageEl.textContent = visibleMessage;
  riskSettingsMessageEl.className = visibleMessageType
    ? `form-message ${visibleMessageType}`
    : "form-message";
}

function renderExecutionSettingsForm() {
  const shouldShow = Boolean(selectedBotId && !selectedExecutionProfile && !isLoadingSummary);
  executionSettingsPanel.hidden = !shouldShow;
  if (!shouldShow) {
    executionSettingsMessageEl.textContent = "";
    executionSettingsMessageEl.className = "form-message";
    return;
  }

  if (!isCreatingExecutionProfile && !executionSettingsMessageType) {
    populateExecutionSettingsForm();
  }

  const shouldDisable = isCreatingExecutionProfile || isRunningNow || isTogglingPause;
  [
    executionExchangeName,
    executionIsPaper,
    executionBuyThreshold,
    executionSellThreshold,
    executionQuantity,
    executionCooldownSeconds,
    executionMaxPositionSize,
    executionMaxDailyLoss,
    executionMaxOpenPositions,
    executionMaxTradeQuantity,
    executionMaxPositionQuantity,
    executionStopLossPercent,
  ].forEach((input) => {
    input.disabled = shouldDisable;
  });

  executionSettingsSubmit.textContent = isCreatingExecutionProfile
    ? t("creating_execution_settings")
    : t("create_execution_settings");
  executionSettingsSubmit.disabled = shouldDisable;
  executionSettingsMessageEl.textContent = executionSettingsMessage;
  executionSettingsMessageEl.className = executionSettingsMessageType
    ? `form-message ${executionSettingsMessageType}`
    : "form-message";
}

function optimizationParametersLabel(parameters) {
  return Object.entries(parameters)
    .map(([key, value]) => `${strategyParameterLabel(key)}: ${formatValue(value)}`)
    .join(" · ");
}

function readableQualityWarningKey(warning) {
  return String(warning ?? "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function optimizationQualityWarningLabel(warning) {
  const warningKey = String(warning ?? "");
  const knownWarningKey = `optimization_warning_${warningKey}`;
  if (translations.en[knownWarningKey]) return t(knownWarningKey);
  return t("optimization_warning_unknown", {
    warning: readableQualityWarningKey(warningKey) || formatValue(warningKey),
  });
}

function optimizationReturnBucket(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(2) : "—";
}

function optimizationQuality(results) {
  const total = results.length;
  const closedTradeResults = results.filter((item) => item.hasClosedTrades).length;
  const openPositionResults = results.filter((item) => item.hasOpenPosition).length;
  const passedQualityResults = results.filter((item) => item.passesQualityFilters).length;
  const failedQualityResults = total - passedQualityResults;
  const uniqueReturns = new Set(results.map((item) => optimizationReturnBucket(item.totalReturnPercent))).size;
  const lowTradeResults = results.filter((item) => Number(item.numberOfTrades) <= 1).length;
  const warnings = [];

  if (closedTradeResults === 0) {
    warnings.push(t("optimization_warning_no_closed_trades"));
  } else if (closedTradeResults <= Math.floor(total / 4)) {
    warnings.push(t("optimization_warning_most_no_closed_trades"));
  }
  if (uniqueReturns <= 1 && total > 1) {
    warnings.push(t("optimization_warning_similar_returns"));
  }
  if (openPositionResults === total && total > 0) {
    warnings.push(t("optimization_warning_all_open_positions"));
  }
  if (lowTradeResults >= Math.ceil(total * 0.75)) {
    warnings.push(t("optimization_warning_few_trades"));
  }

  return {
    total,
    closedTradeResults,
    openPositionResults,
    uniqueReturns,
    passedQualityResults,
    failedQualityResults,
    warnings,
  };
}

function renderOptimizationQualitySummary(results) {
  const quality = optimizationQuality(results);
  const summary = document.createElement("section");
  summary.className = "backtest-optimization-quality";

  const heading = document.createElement("div");
  heading.className = "backtest-optimization-quality-heading";
  const title = document.createElement("strong");
  title.textContent = t("optimization_quality_title");
  heading.append(title);

  const stats = document.createElement("div");
  stats.className = "backtest-optimization-quality-stats";
  [
    t("optimization_total_combinations", { count: formatDecimal(quality.total) }),
    t("optimization_closed_trade_results", { count: formatDecimal(quality.closedTradeResults) }),
    t("optimization_open_position_results", { count: formatDecimal(quality.openPositionResults) }),
    t("optimization_unique_returns", { count: formatDecimal(quality.uniqueReturns) }),
    t("optimization_passed_quality_results", { count: formatDecimal(quality.passedQualityResults) }),
    t("optimization_failed_quality_results", { count: formatDecimal(quality.failedQualityResults) }),
  ].forEach((text) => {
    const chip = document.createElement("span");
    chip.textContent = text;
    stats.append(chip);
  });

  const warnings = document.createElement("ul");
  warnings.className = "backtest-optimization-warnings";
  quality.warnings.forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    warnings.append(item);
  });

  const note = document.createElement("p");
  note.textContent = t("optimization_quality_note");

  summary.append(heading, stats);
  if (quality.warnings.length > 0) summary.append(warnings);
  summary.append(note);
  return summary;
}

function renderOptimizationDisplayFilter({ checked, label, onChange }) {
  const wrapper = document.createElement("label");
  wrapper.className = "backtest-optimization-filter";
  const checkbox = document.createElement("input");
  const text = document.createElement("span");
  checkbox.type = "checkbox";
  checkbox.checked = checked;
  text.textContent = label;
  checkbox.addEventListener("change", () => {
    onChange(checkbox.checked);
    renderBacktestOptimizationResult();
  });
  wrapper.append(checkbox, text);
  return wrapper;
}

function renderOptimizationFilters() {
  const filters = document.createElement("div");
  filters.className = "backtest-optimization-filters";
  filters.append(
    renderOptimizationDisplayFilter({
      checked: showMeaningfulOptimizationOnly,
      label: t("optimization_meaningful_filter"),
      onChange: (checked) => {
        showMeaningfulOptimizationOnly = checked;
      },
    }),
    renderOptimizationDisplayFilter({
      checked: showPassedOptimizationOnly,
      label: t("optimization_passed_quality_filter"),
      onChange: (checked) => {
        showPassedOptimizationOnly = checked;
      },
    }),
  );
  return filters;
}

function optimizationApplyKeys(strategyType) {
  if (strategyType === "moving_average_cross") return ["short_window", "long_window", "quantity"];
  if (strategyType === "price_threshold") return ["buy_below", "sell_above", "quantity"];
  return [];
}

function optimizationResultStrategy() {
  const strategyId = backtestOptimizationResult?.strategyId ?? selectedBacktestStrategyId();
  return strategies.find((strategy) => botIdsEqual(strategy.id, strategyId)) ?? null;
}

function optimizationApplyParameters(resultItem) {
  const strategyType = backtestOptimizationResult?.strategyType || optimizationStrategyType();
  const allowedKeys = optimizationApplyKeys(strategyType);
  const resultParameters =
    resultItem?.parameters && typeof resultItem.parameters === "object" ? resultItem.parameters : {};
  return Object.fromEntries(
    allowedKeys
      .filter((key) => Object.prototype.hasOwnProperty.call(resultParameters, key))
      .map((key) => [key, resultParameters[key]]),
  );
}

function updateStrategyInList(strategy) {
  if (!strategy?.id) return;
  const normalized = normalizeStrategy(strategy);
  const index = strategies.findIndex((item) => botIdsEqual(item.id, normalized.id));
  if (index >= 0) {
    strategies = strategies.map((item) => (botIdsEqual(item.id, normalized.id) ? normalized : item));
  } else {
    strategies = [...strategies, normalized];
  }
}

function renderBacktestOptimizationResult() {
  backtestOptimizationResultEl.innerHTML = "";
  if (!backtestOptimizationResult?.results?.length) {
    backtestOptimizationResultEl.className = "backtest-optimization-result empty";
    backtestOptimizationResultEl.textContent = t("optimization_no_result");
    return;
  }

  const allResults = backtestOptimizationResult.results;
  const visibleResults = allResults.filter(
    (item) =>
      (!showMeaningfulOptimizationOnly || item.hasClosedTrades) &&
      (!showPassedOptimizationOnly || item.passesQualityFilters),
  );
  const qualitySummary = renderOptimizationQualitySummary(allResults);
  const filters = renderOptimizationFilters();

  const note = document.createElement("p");
  note.className = "backtest-optimization-note";
  note.textContent = t("optimization_review_note");

  if (visibleResults.length === 0) {
    const empty = document.createElement("div");
    empty.className = "backtest-optimization-result empty";
    empty.textContent =
      showMeaningfulOptimizationOnly || showPassedOptimizationOnly
        ? t("optimization_no_display_filter_results")
        : t("optimization_no_meaningful_results");
    backtestOptimizationResultEl.className = "backtest-optimization-result";
    backtestOptimizationResultEl.append(qualitySummary, filters, empty);
    return;
  }

  const list = document.createElement("ol");
  list.className = "backtest-optimization-list";
  visibleResults.forEach((item, index) => {
    const row = document.createElement("li");
    row.className = index === 0 ? "backtest-optimization-item best" : "backtest-optimization-item";

    const header = document.createElement("div");
    header.className = "backtest-optimization-item-header";
    const rank = document.createElement("strong");
    rank.textContent = `${t("rank_label")} ${formatDecimal(item.rank, String(index + 1))}`;
    const parameters = document.createElement("span");
    parameters.textContent = optimizationParametersLabel(item.parameters);
    header.append(rank, parameters);

    const qualityStatus = document.createElement("div");
    qualityStatus.className = item.passesQualityFilters
      ? "backtest-optimization-status passed"
      : "backtest-optimization-status failed";
    qualityStatus.textContent = item.passesQualityFilters
      ? t("optimization_quality_passed")
      : t("optimization_quality_failed");

    const metrics = document.createElement("dl");
    metrics.className = "backtest-history-metrics";
    [
      {
        label: t("return_percent_label"),
        value: formatPercent(item.totalReturnPercent),
        className: pnlClass(item.totalReturnPercent),
      },
      {
        label: t("total_return_label"),
        value: formatDecimal(item.totalReturn),
        className: pnlClass(item.totalReturn),
      },
      { label: t("final_balance_label"), value: formatDecimal(item.finalBalance) },
      { label: t("win_rate_label"), value: formatPercent(item.winRate) },
      { label: t("profit_factor_label"), value: formatRatio(item.profitFactor) },
      { label: t("number_of_trades_label"), value: formatDecimal(item.numberOfTrades) },
      { label: t("closed_trades_label"), value: formatDecimal(item.closedTrades) },
      { label: t("open_position_label"), value: formatBoolean(item.openPosition) },
    ].forEach((metric) => {
      const group = document.createElement("div");
      const label = document.createElement("dt");
      const value = document.createElement("dd");
      label.textContent = metric.label;
      value.textContent = metric.value;
      if (metric.className) value.classList.add(metric.className);
      group.append(label, value);
      metrics.append(group);
    });

    const audit = document.createElement("dl");
    audit.className = "backtest-optimization-audit";
    [
      { label: t("optimization_effective_parameters_label"), value: optimizationParametersLabel(item.effectiveParameters) },
      { label: t("optimization_submitted_overrides_label"), value: optimizationParametersLabel(item.parameterOverrides) },
      { label: t("optimization_base_parameters_label"), value: optimizationParametersLabel(item.baseParameters) },
    ]
      .filter((entry) => entry.value)
      .forEach((entry) => {
        const group = document.createElement("div");
        const label = document.createElement("dt");
        const value = document.createElement("dd");
        label.textContent = entry.label;
        value.textContent = entry.value;
        group.append(label, value);
        audit.append(group);
      });

    const warnings = document.createElement("div");
    warnings.className = "backtest-optimization-result-warnings";
    if (item.qualityWarnings.length > 0) {
      const warningTitle = document.createElement("strong");
      warningTitle.textContent = t("optimization_result_warnings_label");
      const warningList = document.createElement("ul");
      item.qualityWarnings.forEach((warning) => {
        const warningItem = document.createElement("li");
        warningItem.textContent = optimizationQualityWarningLabel(warning);
        warningList.append(warningItem);
      });
      warnings.append(warningTitle, warningList);
    }

    const actions = document.createElement("div");
    actions.className = "backtest-optimization-item-actions";
    const applyButton = document.createElement("button");
    applyButton.type = "button";
    applyButton.className = "secondary-button";
    applyButton.textContent = isApplyingOptimizationParameters
      ? t("applying_to_strategy")
      : t("apply_to_strategy");
    applyButton.disabled = isApplyingOptimizationParameters || isRunningBacktestOptimization;
    applyButton.addEventListener("click", () => applyOptimizationParametersToStrategy(item));
    actions.append(applyButton);

    row.append(header, qualityStatus, metrics);
    if (audit.childElementCount > 0) row.append(audit);
    if (warnings.childElementCount > 0) row.append(warnings);
    row.append(actions);
    list.append(row);
  });

  backtestOptimizationResultEl.className = "backtest-optimization-result";
  backtestOptimizationResultEl.append(qualitySummary, filters, note, list);
}

function renderBacktestPanel() {
  const preferredStrategyId = selectedBacktestStrategyId();
  renderStrategySelect(backtestStrategyId, preferredStrategyId);

  if (!backtestStrategyTouched && preferredStrategyId) {
    backtestStrategyId.value = String(preferredStrategyId);
  }

  const shouldDisable =
    isRunningBacktest ||
    isImportingBacktestCandles ||
    isRunningBacktestOptimization ||
    isApplyingOptimizationParameters ||
    isLoadingStrategies ||
    strategies.length === 0 ||
    Boolean(strategyLoadError);
  backtestStrategyId.disabled = shouldDisable;
  backtestInitialBalance.disabled = isRunningBacktest || isImportingBacktestCandles;
  backtestSource.disabled = isRunningBacktest || isImportingBacktestCandles;
  backtestCandleLimit.disabled = isRunningBacktest || isImportingBacktestCandles;
  backtestImportBinance.textContent = isImportingBacktestCandles
    ? t("importing_binance_candles")
    : t("import_binance_candles");
  backtestImportBinance.disabled = shouldDisable;
  backtestSubmit.textContent = isRunningBacktest ? t("running_backtest") : t("run_backtest");
  backtestSubmit.disabled = shouldDisable;
  backtestStrategyHelp.textContent = isLoadingStrategies
    ? t("loading_available_strategies")
    : strategyLoadError
      ? t("could_not_load_strategies", { detail: strategyLoadError })
      : strategies.length === 0
        ? t("no_strategies_available")
        : t("backtest_uses_selected_bot_strategy");
  backtestStrategyHelp.className = strategyLoadError
    ? "backtest-help error"
    : "backtest-help";
  backtestMessageEl.textContent =
    backtestMessage ||
    (strategies.length === 0 && !isLoadingStrategies ? t("no_strategies_available") : "");
  backtestMessageEl.className = backtestMessageType
    ? `form-message ${backtestMessageType}`
    : "form-message";
  backtestImportMessageEl.textContent = backtestImportMessage;
  backtestImportMessageEl.className = backtestImportMessageType
    ? `form-message ${backtestImportMessageType}`
    : "form-message";
  populateOptimizationDefaults();
  const strategyType = optimizationStrategyType();
  const optimizationSupported = ["price_threshold", "moving_average_cross"].includes(strategyType);
  optimizationFirstValuesLabel.textContent =
    strategyType === "moving_average_cross" ? t("short_window_values_label") : t("buy_below_values_label");
  optimizationSecondValuesLabel.textContent =
    strategyType === "moving_average_cross" ? t("long_window_values_label") : t("sell_above_values_label");
  optimizationQuantityLabel.textContent = t("quantity");
  optimizationMinClosedTradesLabel.textContent = t("optimization_min_closed_trades_label");
  optimizationRequireClosedPositionLabel.textContent = t("optimization_require_closed_position_label");
  backtestOptimizationHelp.textContent =
    t("parameter_optimization_help") +
    " " +
    (strategyType === "moving_average_cross" ? t("optimization_ma_help") : t("optimization_price_help"));
  const shouldDisableOptimization = shouldDisable || !optimizationSupported;
  [optimizationFirstValues, optimizationSecondValues, optimizationQuantity, optimizationMinClosedTrades].forEach((input) => {
    input.disabled = shouldDisableOptimization;
  });
  optimizationRequireClosedPosition.disabled = shouldDisableOptimization;
  backtestOptimizationSubmit.textContent = isRunningBacktestOptimization
    ? t("running_optimization")
    : t("run_optimization");
  backtestOptimizationSubmit.disabled = shouldDisableOptimization;
  const visibleOptimizationMessage =
    backtestOptimizationMessage || (!optimizationSupported ? t("optimization_unsupported_strategy") : "");
  backtestOptimizationMessageEl.textContent = visibleOptimizationMessage;
  backtestOptimizationMessageEl.className = backtestOptimizationMessageType
    ? `form-message ${backtestOptimizationMessageType}`
    : "form-message";
  if (backtestOptimizationResult) {
    renderBacktestOptimizationResult();
  } else {
    backtestOptimizationResultEl.className = "backtest-optimization-result empty";
    backtestOptimizationResultEl.textContent = t("optimization_no_result");
  }

  backtestResultEl.innerHTML = "";
  if (isRunningBacktest) {
    backtestResultEl.className = "backtest-result empty loading";
    backtestResultEl.textContent = t("running_backtest");
    return;
  }

  if (!backtestResult) {
    backtestResultEl.className = "backtest-result empty";
    const title = document.createElement("strong");
    const hint = document.createElement("span");
    title.textContent = t("no_backtest_result");
    hint.textContent = t("no_backtest_result_hint");
    backtestResultEl.append(title, hint);
    return;
  }

  const notes = document.createElement("div");
  notes.className = "backtest-result-notes";
  [
    t("backtest_simulated_note"),
    t("backtest_data_note", { source: formatValue(backtestResult.source) }),
    t("backtest_strategy_data_note"),
  ].forEach((text) => {
    const note = document.createElement("span");
    note.textContent = text;
    notes.append(note);
  });

  const resultNoticeText = backtestResultNotice(backtestResult);
  const resultNotice = document.createElement("p");
  resultNotice.className = "backtest-result-notice";
  resultNotice.hidden = !resultNoticeText;
  resultNotice.textContent = resultNoticeText;

  const rows = [
    { label: t("symbol"), value: formatValue(backtestResult.symbol) },
    { label: t("timeframe_label"), value: formatValue(backtestResult.timeframe) },
    { label: t("strategy_type_label"), value: humanizeMessage(backtestResult.strategyType) },
    { label: t("source_label"), value: formatValue(backtestResult.source) },
    { label: t("candles_processed_label"), value: formatDecimal(backtestResult.candlesProcessed) },
    { label: t("initial_balance_label"), value: formatDecimal(backtestResult.initialBalance) },
    {
      label: t("final_balance_label"),
      value: formatDecimal(backtestResult.finalBalance),
      className: pnlClass(backtestResult.finalBalance, backtestResult.initialBalance),
    },
    {
      label: t("realized_pnl_label"),
      value: formatDecimal(backtestResult.realizedPnl),
      className: pnlClass(backtestResult.realizedPnl),
    },
    {
      label: t("unrealized_pnl_label"),
      value: formatDecimal(backtestResult.unrealizedPnl),
      className: pnlClass(backtestResult.unrealizedPnl),
    },
    {
      label: t("total_return_label"),
      value: formatDecimal(backtestResult.totalReturn),
      className: pnlClass(backtestResult.totalReturn),
      help: t("total_return_help"),
    },
    {
      label: t("return_percent_label"),
      value: formatPercent(backtestResult.totalReturnPercent),
      className: pnlClass(backtestResult.totalReturnPercent),
      help: t("total_return_help"),
    },
    { label: t("win_rate_label"), value: formatPercent(backtestResult.winRate), help: t("win_rate_help") },
    {
      label: t("average_trade_pnl_label"),
      value: formatDecimal(backtestResult.averageTradePnl),
      className: pnlClass(backtestResult.averageTradePnl),
    },
    {
      label: t("best_trade_pnl_label"),
      value: formatDecimal(backtestResult.bestTradePnl),
      className: pnlClass(backtestResult.bestTradePnl),
    },
    {
      label: t("worst_trade_pnl_label"),
      value: formatDecimal(backtestResult.worstTradePnl),
      className: pnlClass(backtestResult.worstTradePnl),
    },
    { label: t("profit_factor_label"), value: formatRatio(backtestResult.profitFactor), help: t("profit_factor_help") },
    { label: t("number_of_trades_label"), value: formatDecimal(backtestResult.numberOfTrades) },
    { label: t("closed_trades_label"), value: formatDecimal(backtestResult.closedTrades), help: t("closed_trades_help") },
    { label: t("open_position_label"), value: formatBoolean(backtestResult.openPosition), help: t("open_position_help") },
  ];
  if (backtestResult.openPosition) {
    rows.push(
      { label: t("open_position_qty_label"), value: formatDecimal(backtestResult.positionQuantity) },
      { label: t("entry_price_label"), value: formatDecimal(backtestResult.entryPrice) },
    );
  }

  const grid = document.createElement("dl");
  grid.className = "backtest-result-grid";
  rows.forEach((item) => {
    const row = document.createElement("div");
    const label = document.createElement("dt");
    const value = document.createElement("dd");
    label.textContent = item.label;
    if (item.help) label.title = item.help;
    value.textContent = item.value;
    if (item.className) value.classList.add(item.className);
    row.append(label, value);
    if (item.help) {
      const help = document.createElement("small");
      help.textContent = item.help;
      row.append(help);
    }
    grid.append(row);
  });

  const tradesHeading = document.createElement("h3");
  tradesHeading.className = "backtest-trades-heading";
  tradesHeading.textContent = t("backtest_trade_actions");
  const tradesList = document.createElement("ul");
  tradesList.className = "backtest-trades";

  if (backtestResult.trades.length === 0) {
    const empty = document.createElement("li");
    empty.className = "backtest-trade-empty";
    empty.textContent = t("no_backtest_trades");
    tradesList.append(empty);
  } else {
    backtestResult.trades.forEach((trade) => {
      const item = document.createElement("li");
      const sideValue = trade.decision || trade.side;
      const side = sideValue ? formatActivitySide(sideValue) : "—";
      const detailParts = [
        [t("action_time_label"), formatDateTime(trade.openedAt)],
        [t("symbol"), formatValue(trade.symbol)],
        [t("quantity_label"), formatDecimal(trade.quantity)],
        [t("price_label"), formatDecimal(trade.price)],
        [t("cash_balance_label"), formatDecimal(trade.cashBalance)],
        [t("position_qty_label"), formatDecimal(trade.positionQuantity)],
        [t("realized_pnl_label"), formatDecimal(trade.realizedPnl), pnlClass(trade.realizedPnl)],
      ];
      const sideEl = document.createElement("span");
      sideEl.className = "backtest-trade-side";
      sideEl.textContent = side;

      const main = document.createElement("div");
      main.className = "backtest-trade-main";

      const detail = document.createElement("div");
      detail.className = "backtest-trade-detail";
      detailParts.forEach(([label, value, className]) => {
        const chip = document.createElement("span");
        chip.textContent = `${label}: ${value}`;
        if (className) chip.classList.add(className);
        detail.append(chip);
      });
      main.append(detail);

      const reason = document.createElement("span");
      reason.className = "backtest-trade-reason";
      reason.textContent = `${t("reason_label")}: ${formatRiskReason(trade.decisionReason)}`;
      main.append(reason);

      item.append(sideEl, main);
      tradesList.append(item);
    });
  }

  backtestResultEl.className = "backtest-result";
  backtestResultEl.append(notes, resultNotice, grid, tradesHeading, tradesList);
}

function renderBacktestHistory() {
  refreshBacktestHistory.textContent = isLoadingBacktestHistory
    ? t("refreshing_backtest_history")
    : t("refresh_backtest_history");
  refreshBacktestHistory.disabled = isLoadingBacktestHistory;
  backtestHistoryEl.innerHTML = "";

  if (isLoadingBacktestHistory) {
    backtestHistoryEl.className = "backtest-history empty loading";
    backtestHistoryEl.textContent = t("loading_recent_backtests");
    return;
  }

  if (backtestHistoryError) {
    backtestHistoryEl.className = "backtest-history empty error";
    backtestHistoryEl.textContent = isBacktestDataIssueMessage(backtestHistoryError)
      ? t("backtest_not_enough_candle_data")
      : backtestHistoryError || t("failed_to_load_backtest_history");
    return;
  }

  if (backtestHistory.length === 0) {
    backtestHistoryEl.className = "backtest-history empty";
    const title = document.createElement("strong");
    const hint = document.createElement("span");
    title.textContent = t("no_backtests_yet");
    hint.textContent = t("no_backtests_yet_hint");
    backtestHistoryEl.append(title, hint);
    return;
  }

  const fragments = [];
  if (backtestHistory.length >= 2) {
    const bestRun = selectBestRecentBacktest(backtestHistory);
    if (bestRun) {
      const summary = document.createElement("section");
      summary.className = "backtest-best-run";
      const heading = document.createElement("div");
      heading.className = "backtest-best-run-heading";
      const title = document.createElement("strong");
      title.textContent = t("best_recent_run");
      const createdAt = document.createElement("span");
      createdAt.textContent = formatDateTime(bestRun.createdAt);
      heading.append(title, createdAt);

      const help = document.createElement("p");
      help.textContent = t("best_recent_run_help");

      const metrics = document.createElement("dl");
      metrics.className = "backtest-history-metrics";
      [
        {
          label: t("return_percent_label"),
          value: formatPercent(bestRun.totalReturnPercent),
          className: pnlClass(bestRun.totalReturnPercent),
        },
        {
          label: t("total_return_label"),
          value: formatDecimal(bestRun.totalReturn),
          className: pnlClass(bestRun.totalReturn),
          help: t("total_return_help"),
        },
        { label: t("win_rate_label"), value: formatPercent(bestRun.winRate), help: t("win_rate_help") },
        { label: t("profit_factor_label"), value: formatRatio(bestRun.profitFactor), help: t("profit_factor_help") },
        { label: t("closed_trades_label"), value: formatDecimal(bestRun.closedTrades), help: t("closed_trades_help") },
      ].forEach((metric) => {
        const group = document.createElement("div");
        const label = document.createElement("dt");
        const value = document.createElement("dd");
        label.textContent = metric.label;
        if (metric.help) label.title = metric.help;
        value.textContent = metric.value;
        if (metric.className) value.classList.add(metric.className);
        group.append(label, value);
        metrics.append(group);
      });

      summary.append(heading, help, metrics);
      fragments.push(summary);
    }
  } else {
    const note = document.createElement("p");
    note.className = "backtest-compare-note";
    note.textContent = t("run_more_backtests_to_compare");
    fragments.push(note);
  }

  const list = document.createElement("ul");
  list.className = "backtest-history-list";
  backtestHistory.forEach((item) => {
    const row = document.createElement("li");
    row.className = "backtest-history-item";

    const header = document.createElement("div");
    header.className = "backtest-history-item-header";

    const title = document.createElement("strong");
    title.textContent = strategyLabelForHistory(item.strategyId);

    const createdAt = document.createElement("span");
    createdAt.textContent = formatDateTime(item.createdAt);
    header.append(title, createdAt);

    const meta = document.createElement("div");
    meta.className = "backtest-history-meta";
    [
      [t("symbol"), item.symbol],
      [t("timeframe_label"), item.timeframe],
      [t("strategy_type_label"), humanizeMessage(item.strategyType)],
      [t("source_label"), item.source],
    ].forEach(([label, value]) => {
      const pill = document.createElement("span");
      pill.textContent = `${label}: ${formatValue(value)}`;
      meta.append(pill);
    });

    const metrics = document.createElement("dl");
    metrics.className = "backtest-history-metrics";
    [
      { label: t("initial_balance_label"), value: formatDecimal(item.initialBalance) },
      {
        label: t("final_balance_label"),
        value: formatDecimal(item.finalBalance),
        className: pnlClass(item.finalBalance, item.initialBalance),
      },
      {
        label: t("realized_pnl_label"),
        value: formatDecimal(item.realizedPnl),
        className: pnlClass(item.realizedPnl),
      },
      {
        label: t("total_return_label"),
        value: formatDecimal(item.totalReturn),
        className: pnlClass(item.totalReturn),
        help: t("total_return_help"),
      },
      {
        label: t("return_percent_label"),
        value: formatPercent(item.totalReturnPercent),
        className: pnlClass(item.totalReturnPercent),
        help: t("total_return_help"),
      },
      { label: t("win_rate_label"), value: formatPercent(item.winRate), help: t("win_rate_help") },
      { label: t("profit_factor_label"), value: formatRatio(item.profitFactor), help: t("profit_factor_help") },
      { label: t("number_of_trades_label"), value: formatDecimal(item.numberOfTrades) },
      {
        label: t("winning_losing_trades_label"),
        value:
          item.winningTrades === null && item.losingTrades === null
            ? "—"
            : `${formatDecimal(item.winningTrades, "0")} / ${formatDecimal(item.losingTrades, "0")}`,
      },
      { label: t("candles_processed_label"), value: formatDecimal(item.candlesProcessed) },
    ].forEach((metric) => {
      const group = document.createElement("div");
      const label = document.createElement("dt");
      const value = document.createElement("dd");
      label.textContent = metric.label;
      if (metric.help) label.title = metric.help;
      value.textContent = metric.value;
      if (metric.className) value.classList.add(metric.className);
      group.append(label, value);
      metrics.append(group);
    });

    row.append(header, meta, metrics);
    list.append(row);
  });

  backtestHistoryEl.className = "backtest-history";
  backtestHistoryEl.append(...fragments, list);
}

function cooldownText(bot) {
  if (!bot) return "—";
  if (bot.cooldownActive) {
    return bot.cooldownUntil
      ? `${t("active_until")} ${formatDateTime(bot.cooldownUntil)}`
      : t("active");
  }
  if (bot.cooldownSeconds) return t("configured_seconds", { value: formatDecimal(bot.cooldownSeconds) });
  return t("not_active");
}

function modeLabel(isPaper) {
  if (isPaper === null || isPaper === undefined) return t("mode_loading");
  return isPaper === false ? t("live_mode") : t("paper_mode");
}

function stateLabel(bot) {
  if (!bot) return t("mode_ready");
  if (bot.isPaused || bot.status === "paused") return t("paused_state");
  if (isRunnableStatus(bot.status)) return t("ready_to_run");
  return t("not_runnable");
}

function actionHelpText(bot) {
  if (!bot) {
    return t("select_bot_to_view_actions");
  }

  if (isLoadingSummary && !selectedBotConfig) {
    return t("loading_actions");
  }

  if (bot.status === "draft") {
    if (!selectedExecutionProfile && !isLoadingSummary) {
      return t("execution_settings_required_to_activate");
    }
    return t("activate_draft_before_running");
  }

  if (bot.isPaused || bot.status === "paused") {
    return t("resume_automatic_checks");
  }

  if (selectedBotConfig?.isPaper === false) {
    return t("live_mode_orders");
  }

  return t("paper_mode_orders");
}

const ACTIVITY_MESSAGE_LABELS = {
  buy_filled: "activity_buy_filled",
  sell_filled: "activity_sell_filled",
  order_filled: "activity_order_filled",
  order_rejected: "activity_order_rejected",
  buy_signal: "activity_buy_signal",
  sell_signal: "activity_sell_signal",
  evaluation_skipped: "activity_evaluation_skipped",
  evaluation_no_signal: "activity_evaluation_no_signal",
  bot_paused: "activity_bot_paused",
  bot_resumed: "activity_bot_resumed",
  bot_resume_requested: "activity_bot_resume_requested",
  bot_skipped_paused: "activity_bot_skipped_paused",
  bot_not_active: "activity_bot_not_active",
  execution_profile_missing: "activity_execution_profile_missing",
  execution_profile_disabled: "activity_execution_profile_disabled",
  cooldown_active: "activity_cooldown_active",
  live_mode_not_implemented: "activity_live_mode_not_implemented",
  unsupported_strategy_type: "activity_unsupported_strategy_type",
  strategy_inactive: "activity_strategy_inactive",
  risk_limit_blocked: "risk_limit_blocked_message",
  missing_price: "risk_missing_price",
  started: "activity_started",
  stopped: "activity_stopped",
  error: "activity_error",
};

function normalizeActivityMessage(message) {
  return String(message || "")
    .trim()
    .toLowerCase();
}

function normalizeRiskReason(reason) {
  return normalizeActivityMessage(reason)
    .replaceAll("-", "_")
    .replace(/[^\w\s]/g, "")
    .replace(/\s+/g, "_");
}

function formatRiskReason(reason, fallback = t("activity_update")) {
  return getRiskMessage(reason) || humanizeMessage(reason, fallback);
}

function getRiskMessage(value) {
  const translationKey = RISK_MESSAGE_LABELS[normalizeRiskReason(value)];
  return translationKey ? t(translationKey) : "";
}

function firstRiskMessage(...values) {
  for (const value of values) {
    const riskMessage = getRiskMessage(value);
    if (riskMessage) return riskMessage;
  }
  return "";
}

function formatRunLifecycleMessage(message) {
  const normalized = normalizeActivityMessage(message);

  if (normalized === "run requested via system trigger") {
    return t("activity_run_requested_system");
  }
  if (normalized === "run requested via manual trigger") {
    return t("activity_run_requested_manual");
  }
  if (normalized === "run status changed from requested to running") {
    return t("activity_run_started");
  }
  if (normalized.startsWith("run status changed from ")) {
    return t("activity_run_status_updated");
  }

  return "";
}

function formatActivityMessageText(message, fallback = t("activity_update")) {
  const normalized = normalizeActivityMessage(message);
  const lifecycleLabel = formatRunLifecycleMessage(normalized);
  if (lifecycleLabel) return lifecycleLabel;

  const messageKey = normalizeRiskReason(message);
  const riskTranslationKey = RISK_MESSAGE_LABELS[messageKey];
  if (riskTranslationKey) return t(riskTranslationKey);

  const translationKey = ACTIVITY_MESSAGE_LABELS[messageKey] ?? ACTIVITY_MESSAGE_LABELS[normalized];
  if (translationKey) return t(translationKey);

  return humanizeMessage(message, fallback);
}

function formatActivityMessage(item) {
  return formatActivityMessageText(item?.message || item?.status || item?.type);
}

function activityStatus(item) {
  const message = normalizeRiskReason(item?.message);
  const type = normalizeRiskReason(item?.type);

  if (message === "buy_filled" || message === "sell_filled" || type === "order_filled") {
    return { label: t("activity_success"), className: "activity-status-success" };
  }
  if (
    [
      "bot_not_active",
      "bot_skipped_paused",
      "evaluation_skipped",
      "evaluation_no_signal",
      "execution_profile_missing",
      "execution_profile_disabled",
      "cooldown_active",
      "live_mode_not_implemented",
      "unsupported_strategy_type",
      "strategy_inactive",
      "risk_limit_blocked",
      "missing_price",
    ].includes(message)
  ) {
    return { label: t("activity_skipped"), className: "activity-status-skipped" };
  }
  if (
    message.includes("failed") ||
    message.includes("error") ||
    type.includes("failed") ||
    type.includes("error")
  ) {
    return { label: t("activity_failed"), className: "activity-status-failed" };
  }
  if (
    message.includes("pending") ||
    message.includes("running") ||
    message.includes("started") ||
    type.includes("pending") ||
    type.includes("running")
  ) {
    return { label: t("activity_running"), className: "activity-status-running" };
  }
  return { label: t("activity_event"), className: "activity-status-neutral" };
}

function formatActivityType(item) {
  const type = normalizeRiskReason(item?.type);
  if (type === "order_filled") return t("order_filled");
  if (type === "run_event") return t("run_event");
  if (type === "bot_event") return t("bot_event");
  return humanizeMessage(item?.type, t("activity_event"));
}

function formatActivitySide(side) {
  const normalized = normalizeActivityMessage(side);
  if (normalized === "buy") return t("activity_side_buy");
  if (normalized === "sell") return t("activity_side_sell");
  return humanizeMessage(side);
}

function activityRiskReason(item) {
  return firstAvailable(
    item?.reason,
    item?.detail,
    item?.details?.reason,
    item?.details?.detail,
    item?.payload?.reason,
    item?.payload?.detail,
    item?.decision_explanation?.reason,
    item?.decisionExplanation?.reason,
  );
}

function activityDetailParts(item) {
  const parts = [];
  const reason = activityRiskReason(item);

  if (item?.side) {
    parts.push(`${t("side_label")}: ${formatActivitySide(item.side)}`);
  }
  if (item?.price !== null && item?.price !== undefined && item?.price !== "") {
    parts.push(`${t("price_label")}: ${formatDecimal(item.price)}`);
  }
  if (item?.quantity !== null && item?.quantity !== undefined && item?.quantity !== "") {
    parts.push(`${t("quantity_label")}: ${formatDecimal(item.quantity)}`);
  }
  if (item?.cooldown_until) {
    parts.push(`${t("cooldown_until")} ${formatDateTime(item.cooldown_until)}`);
  }
  if (reason) {
    parts.push(`${t("reason_label")}: ${formatRiskReason(reason)}`);
  }

  return parts;
}

function activityBotName() {
  const bot = selectedSummary || bots.find((item) => botIdsEqual(item.id, selectedBotId));
  return bot?.name ? String(bot.name) : "";
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  let data = null;

  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    const detail =
      data?.detail?.message ??
      data?.detail ??
      data?.message ??
      `Request failed with ${response.status}`;
    const error = new Error(String(detail));
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

function requestErrorMessage(error, fallback) {
  if (error?.status === 404) return t("request_failed_404");
  if (error?.status === 422) return t("request_failed_422");
  return error?.message || fallback;
}

function validationErrorsMessage(errors, fallback) {
  if (!Array.isArray(errors) || errors.length === 0) return fallback;
  const fieldLabels = {
    name: "name",
    exchange_name: "exchange name",
    strategy_id: "strategy",
  };
  const fields = [
    ...new Set(
      errors
        .map((item) => item.loc?.[item.loc.length - 1])
        .filter(Boolean)
        .map((field) => fieldLabels[field] || field),
    ),
  ];
  if (fields.length === 0) return fallback;
  return `${t("request_failed_422")} ${fields.join(", ")}.`;
}

function strategyOptionLabel(strategy) {
  const details = [strategy.symbol, strategy.timeframe, humanizeMessage(strategy.strategyType, "")]
    .filter(Boolean)
    .join(" — ");
  return details ? `${strategy.name || t("unnamed_strategy")} — ${details}` : t("unnamed_strategy");
}

function strategyLabelForHistory(strategyId) {
  const strategy = strategies.find((item) => String(item.id) === String(strategyId));
  if (strategy) return strategy.name || t("unnamed_strategy");
  return t("backtest_strategy_fallback", { id: strategyId ?? "—" });
}

function renderStrategySelect(selectEl, selectedId) {
  const strategyOptions = [];

  if (isLoadingStrategies) {
    strategyOptions.push(`<option value="">${t("loading_strategies")}</option>`);
  } else if (strategyLoadError) {
    strategyOptions.push(`<option value="">${t("strategies_unavailable")}</option>`);
  } else if (strategies.length === 0) {
    strategyOptions.push(`<option value="">${t("no_strategies_available")}</option>`);
  } else {
    strategies.forEach((strategy) => {
      strategyOptions.push(
        `<option value="${strategy.id}"${
          String(strategy.id) === String(selectedId) ? " selected" : ""
        }>${strategyOptionLabel(strategy)}</option>`,
      );
    });
  }

  selectEl.innerHTML = strategyOptions.join("");
  if ((selectedId === null || selectedId === "" || selectedId === undefined) && strategies.length > 0) {
    selectEl.value = String(strategies[0].id);
  }
  selectEl.disabled = isLoadingStrategies || strategies.length === 0 || Boolean(strategyLoadError);
}

function selectedBacktestStrategyId() {
  if (backtestStrategyTouched && backtestStrategyId.value) return backtestStrategyId.value;
  const selectedStrategyId = strategyIdForSelectedBot();
  if (selectedStrategyId && strategies.some((strategy) => String(strategy.id) === String(selectedStrategyId))) {
    return selectedStrategyId;
  }
  return backtestStrategyId.value || strategies[0]?.id || "";
}

function selectedBacktestStrategy() {
  const strategyId = selectedBacktestStrategyId();
  return strategies.find((strategy) => botIdsEqual(strategy.id, strategyId)) ?? null;
}

function selectedBacktestCandleTarget() {
  const strategy = selectedBacktestStrategy();
  const symbol = formatValue(strategy?.symbol || selectedSummary?.symbol, "").trim().toUpperCase();
  const timeframe = formatValue(strategy?.timeframe || selectedSummary?.strategyTimeframe, "").trim();
  return { strategy, symbol, timeframe };
}

function parseBacktestCandleLimit() {
  const trimmed = backtestCandleLimit.value.trim();
  if (!/^[1-9]\d*$/.test(trimmed)) return null;
  const parsed = Number(trimmed);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= 500 ? parsed : null;
}

function optimizationStrategyType() {
  return normalizeStrategyType(selectedBacktestStrategy()?.strategyType || selectedSummary?.strategyType);
}

function commaValues(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parsePositiveOptimizationValues(value) {
  const values = commaValues(value);
  if (values.length === 0) return null;
  return values.every((item) => parsePositiveParameter(item) !== null) ? values : null;
}

function parsePositiveOptimizationIntegers(value) {
  const values = commaValues(value);
  if (values.length === 0) return null;
  return values.every((item) => parsePositiveIntegerParameter(item) !== null) ? values : null;
}

function parseNonNegativeInteger(value) {
  const trimmed = String(value ?? "").trim();
  if (!/^\d+$/.test(trimmed)) return null;
  const parsed = Number(trimmed);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

function nearbyOptimizationValues(value, fallback) {
  const parsed = Number(value);
  const base = Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  return [base * 0.98, base, base * 1.02]
    .map((item) => item.toFixed(8).replace(/\.?0+$/, ""))
    .join(", ");
}

function populateOptimizationDefaults() {
  if (backtestOptimizationTouched) return;
  const strategy = selectedBacktestStrategy();
  const parameters = strategy?.parameters ?? {};
  const strategyType = optimizationStrategyType();

  if (strategyType === "moving_average_cross") {
    optimizationFirstValues.value = "5, 10";
    optimizationSecondValues.value = "20, 30";
    optimizationQuantity.value = formatValue(parameters.quantity, "1");
    return;
  }

  optimizationFirstValues.value = nearbyOptimizationValues(parameters.buy_below, 100);
  optimizationSecondValues.value = nearbyOptimizationValues(parameters.sell_above, 110);
  optimizationQuantity.value = formatValue(parameters.quantity, "1");
}

function optimizationParameterSets() {
  const strategyType = optimizationStrategyType();
  const quantity = optimizationQuantity.value.trim();
  if (parsePositiveParameter(quantity) === null) return { error: t("optimization_positive_numbers") };

  if (strategyType === "price_threshold") {
    const buyBelowValues = parsePositiveOptimizationValues(optimizationFirstValues.value);
    const sellAboveValues = parsePositiveOptimizationValues(optimizationSecondValues.value);
    if (!buyBelowValues || !sellAboveValues) return { error: t("optimization_positive_numbers") };
    const parameterSets = buyBelowValues.flatMap((buyBelow) =>
      sellAboveValues.map((sellAbove) => ({ buy_below: buyBelow, sell_above: sellAbove, quantity })),
    );
    return parameterSets.length > 50 ? { error: t("optimization_max_sets") } : { parameterSets };
  }

  if (strategyType === "moving_average_cross") {
    const shortWindowValues = parsePositiveOptimizationIntegers(optimizationFirstValues.value);
    const longWindowValues = parsePositiveOptimizationIntegers(optimizationSecondValues.value);
    if (!shortWindowValues || !longWindowValues) return { error: t("optimization_integer_windows") };
    const parameterSets = shortWindowValues.flatMap((shortWindow) =>
      longWindowValues.map((longWindow) => ({ short_window: shortWindow, long_window: longWindow, quantity })),
    );
    if (parameterSets.some((parameters) => Number(parameters.short_window) >= Number(parameters.long_window))) {
      return { error: t("optimization_short_less_than_long") };
    }
    return parameterSets.length > 50 ? { error: t("optimization_max_sets") } : { parameterSets };
  }

  return { error: t("optimization_unsupported_strategy") };
}

function validateBacktestForm() {
  if (strategyLoadError) {
    return t("could_not_load_strategies", { detail: strategyLoadError });
  }
  if (isLoadingStrategies) {
    return t("strategies_still_loading");
  }
  if (!selectedBacktestStrategyId()) {
    return t("select_strategy_for_backtest");
  }
  const initialBalance = backtestInitialBalance.value.trim();
  const parsedBalance = Number(initialBalance);
  if (!initialBalance || !Number.isFinite(parsedBalance) || parsedBalance <= 0) {
    return t("enter_positive_initial_balance");
  }
  return "";
}

function backtestHistoryStrategyId() {
  return strategyIdForSelectedBot();
}

async function loadBacktestHistory() {
  const requestId = backtestHistoryRequestId + 1;
  backtestHistoryRequestId = requestId;
  isLoadingBacktestHistory = true;
  backtestHistoryError = "";
  render();

  const params = new URLSearchParams({ limit: "5" });
  const strategyId = backtestHistoryStrategyId();
  if (strategyId) {
    params.set("strategy_id", String(strategyId));
  }

  try {
    const data = await fetchJson(`/api/v1/backtests?${params.toString()}`);
    if (requestId !== backtestHistoryRequestId) return;
    backtestHistory = normalizeBacktestHistoryResponse(data);
  } catch (error) {
    if (requestId !== backtestHistoryRequestId) return;
    backtestHistory = [];
    backtestHistoryError = friendlyBacktestErrorMessage(error, t("failed_to_load_backtest_history"));
  } finally {
    if (requestId !== backtestHistoryRequestId) return;
    isLoadingBacktestHistory = false;
    render();
  }
}

async function loadStrategies() {
  isLoadingStrategies = true;
  strategyLoadError = "";
  render();

  try {
    const data = await fetchJson("/api/v1/strategies");
    strategies = normalizeStrategiesResponse(data);
  } catch (error) {
    strategies = [];
    strategyLoadError = requestErrorMessage(error, t("could_not_load_strategies", { detail: "" }).trim());
  } finally {
    isLoadingStrategies = false;
    render();
  }
}

async function loadExecutionProfile(botId) {
  try {
    const data = await fetchJson(`/api/v1/bots/${botId}/execution-profile`);
    return normalizeExecutionProfile(data);
  } catch (error) {
    if (error?.status === 404) return null;
    throw error;
  }
}

function describeManualRunResult(result) {
  const explanation = result?.decision_explanation ?? {};
  const riskMessage = firstRiskMessage(
    result?.message,
    explanation.reason,
    explanation.detail,
    explanation.message,
    result?.recent_activity_preview?.[0]?.message,
  );
  if (riskMessage) {
    return {
      text: riskMessage,
      type: "note",
    };
  }

  const latestActivity = result?.recent_activity_preview?.[0]?.message;
  const activityMessage = latestActivity || result?.message;
  const activityLabel = formatActivityMessageText(
    activityMessage,
    t("activity_update"),
  );

  if (result?.action === "bought" || result?.action === "sold") {
    return {
      text: t("manual_run_completed", { activity: activityLabel }),
      type: "success",
    };
  }

  if (result?.action === "skipped") {
    return {
      text: t("manual_run_skipped", { activity: activityLabel }),
      type: "note",
    };
  }

  return {
    text: t("manual_run_checked", { activity: activityLabel }),
    type: "success",
  };
}

function decisionClass(decision) {
  const normalized = String(decision || "").toLowerCase();
  if (["buy", "bought"].includes(normalized)) return "decision-buy";
  if (["sell", "sold"].includes(normalized)) return "decision-sell";
  if (["hold", "no_action"].includes(normalized)) return "decision-hold";
  return "decision-skipped";
}

function formatDecisionLabel(decision) {
  const normalized = normalizeRiskReason(decision);
  const labels = {
    bought: "decision_bought",
    sold: "decision_sold",
    buy: "decision_buy",
    sell: "decision_sell",
    hold: "decision_hold",
    no_action: "decision_hold",
    skipped: "decision_skipped",
  };
  const translationKey = labels[normalized];
  return translationKey ? t(translationKey) : humanizeMessage(decision, t("activity_event"));
}

function getDecisionReasonMessage(reason) {
  const normalized = normalizeRiskReason(reason);
  if (normalized.startsWith("unsupported_strategy_type")) {
    return t("decision_reason_strategy_not_supported");
  }

  const translationKey = DECISION_REASON_LABELS[normalized];
  return translationKey ? t(translationKey) : "";
}

function formatDecisionReason(explanation) {
  return (
    firstRiskMessage(explanation?.reason, explanation?.detail, explanation?.message) ||
    getDecisionReasonMessage(explanation?.reason) ||
    getDecisionReasonMessage(explanation?.detail) ||
    getDecisionReasonMessage(explanation?.message) ||
    formatActivityMessageText(
      explanation?.reason,
      explanation?.reasonLabel || formatDecisionLabel(explanation?.decision),
    )
  );
}

function clearSelectedBotMessages() {
  actionMessage = "";
  actionMessageType = "";
  editBotMessage = "";
  editBotMessageType = "";
  executionSettingsMessage = "";
  executionSettingsMessageType = "";
  resetExecutionSettingsForm();
  latestDecisionExplanation = null;
  strategyParametersMessage = "";
  strategyParametersMessageType = "";
  riskSettingsMessage = "";
  riskSettingsMessageType = "";
  backtestMessage = "";
  backtestMessageType = "";
  backtestImportMessage = "";
  backtestImportMessageType = "";
  backtestOptimizationMessage = "";
  backtestOptimizationMessageType = "";
  backtestResult = null;
  backtestOptimizationResult = null;
  showMeaningfulOptimizationOnly = false;
  showPassedOptimizationOnly = false;
  backtestHistory = [];
  backtestHistoryError = "";
  backtestHistoryRequestId += 1;
  isLoadingBacktestHistory = false;
  backtestStrategyTouched = false;
  isEditingStrategyParameters = false;
}

function hasInFlightAction() {
  return (
    isLoadingSummary ||
    isTogglingPause ||
    isRunningNow ||
    isUpdatingPrice ||
    isFetchingBinancePrice ||
    isCreatingBot ||
    isLoadingEditBot ||
    isSavingEditBot ||
    isDeletingBot ||
    isCreatingExecutionProfile ||
    isSavingStrategyParameters ||
    isSavingRiskSettings ||
    isRunningBacktest ||
    isImportingBacktestCandles ||
    isRunningBacktestOptimization ||
    isApplyingOptimizationParameters
  );
}

async function loadBots() {
  isLoadingBots = true;
  botListError = "";
  render();

  try {
    const previousSelectedBotId = selectedBotId;
    const data = await fetchJson("/api/v1/bots");
    bots = normalizeBotsResponse(data);
    const sortedBotList = sortedBots(bots);

    selectedBotId = chooseSelectedBotId(sortedBotList);
    if (!selectedBotId || !botIdsEqual(selectedBotId, previousSelectedBotId)) {
      isEditBotOpen = false;
      selectedBotConfig = null;
      selectedExecutionProfile = null;
    }
    if (!botIdsEqual(selectedBotId, previousSelectedBotId)) {
      clearSelectedBotMessages();
    }
    refreshMessage = "";
    refreshMessageType = "";
    lastRefreshedAt = new Date();
    isLoadingBots = false;
    render();
    if (selectedBotId) {
      await loadSelectedSummary(selectedBotId);
    } else {
      await loadBacktestHistory();
    }
  } catch (error) {
    bots = [];
    selectedBotId = null;
    selectedSummary = null;
    selectedExecutionProfile = null;
    isLoadingBots = false;
    botListError = requestErrorMessage(error, t("could_not_load_bots"));
    render();
  }
}

async function refreshSelectedData() {
  const currentBotId = selectedBotId;
  const data = await fetchJson("/api/v1/bots");
  bots = normalizeBotsResponse(data);
  const sortedBotList = sortedBots(bots);

  selectedBotId = chooseSelectedBotId(sortedBotList);

  if (!botIdsEqual(selectedBotId, currentBotId)) {
    clearSelectedBotMessages();
  }

  if (selectedBotId) {
    const [summary, config] = await Promise.all([
      fetchJson(`/api/v1/bots/${selectedBotId}/summary`),
      fetchJson(`/api/v1/bots/${selectedBotId}`),
    ]);
    selectedSummary = normalizeSummary(summary);
    selectedBotConfig = normalizeBotConfig(config);
    selectedExecutionProfile = await loadExecutionProfile(selectedBotId);
  } else {
    selectedSummary = null;
    isEditBotOpen = false;
    selectedBotConfig = null;
    selectedExecutionProfile = null;
  }
  await loadBacktestHistory();
  refreshMessage = "";
  refreshMessageType = "";
  lastRefreshedAt = new Date();
}

async function refreshDashboardData({ silent = false } = {}) {
  if (isRefreshing) return;

  const currentBotId = selectedBotId;
  isRefreshing = true;
  if (!silent) {
    refreshMessage = "";
    refreshMessageType = "";
  }
  render();

  try {
    const data = await fetchJson("/api/v1/bots");
    bots = normalizeBotsResponse(data);
    const sortedBotList = sortedBots(bots);
    botListError = "";

    selectedBotId = chooseSelectedBotId(sortedBotList);

    if (!botIdsEqual(selectedBotId, currentBotId)) {
      clearSelectedBotMessages();
    }

    if (selectedBotId) {
      const [summary, config] = await Promise.all([
        fetchJson(`/api/v1/bots/${selectedBotId}/summary`),
        fetchJson(`/api/v1/bots/${selectedBotId}`),
      ]);
      selectedSummary = normalizeSummary(summary);
      selectedBotConfig = normalizeBotConfig(config);
      selectedExecutionProfile = await loadExecutionProfile(selectedBotId);
      summaryError = "";
    } else {
      selectedSummary = null;
      selectedBotConfig = null;
      selectedExecutionProfile = null;
      summaryError = "";
    }
    await loadBacktestHistory();
    refreshMessage = "";
    refreshMessageType = "";
    lastRefreshedAt = new Date();
  } catch (error) {
    refreshMessage = silent
      ? t("auto_refresh_failed", { detail: requestErrorMessage(error, t("please_try_again")) })
      : requestErrorMessage(error, t("could_not_refresh"));
    refreshMessageType = "error";
  } finally {
    isRefreshing = false;
    render();
  }
}

function stopAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  autoRefreshTimer = setInterval(() => {
    if (!document.hidden) {
      refreshDashboardData({ silent: true });
    }
  }, AUTO_REFRESH_MS);
}

function updateAutoRefresh() {
  if (autoRefresh.checked && !document.hidden) {
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }
}

async function togglePauseResume() {
  const bot = selectedSummary || bots.find((item) => botIdsEqual(item.id, selectedBotId));
  if (!bot || isTogglingPause) return;

  if (bot.status === "draft" && !selectedExecutionProfile) {
    actionMessage = t("execution_settings_required_to_activate");
    actionMessageType = "note";
    render();
    return;
  }

  const action = bot.status === "draft" || !shouldPause(bot.status) ? "resume" : "pause";
  hasUserSelectedBot = true;
  isTogglingPause = true;
  actionMessage = "";
  actionMessageType = "";
  render();

  try {
    await fetchJson(`/api/v1/bots/${bot.id}/${action}`, { method: "POST" });
    await refreshSelectedData();
  } catch (error) {
    actionMessage = requestErrorMessage(
      error,
      bot.status === "draft"
        ? t("could_not_activate_bot")
        : action === "pause"
          ? t("could_not_pause_bot")
          : t("could_not_resume_bot"),
    );
    actionMessageType = "error";
  } finally {
    isTogglingPause = false;
    render();
  }
}

async function runSelectedBotNow() {
  const bot = selectedSummary || bots.find((item) => botIdsEqual(item.id, selectedBotId));
  if (!bot || isRunningNow) return;

  isRunningNow = true;
  actionMessage = "";
  actionMessageType = "";
  latestDecisionExplanation = null;
  render();

  try {
    const result = await fetchJson(`/api/v1/bots/${bot.id}/run`, { method: "POST" });
    const feedback = describeManualRunResult(result);
    actionMessage = feedback.text;
    actionMessageType = feedback.type;
    latestDecisionExplanation = normalizeDecisionExplanation(result.decision_explanation);
    await refreshSelectedData();
  } catch (error) {
    actionMessage = requestErrorMessage(error, t("could_not_run_bot"));
    actionMessageType = "error";
  } finally {
    isRunningNow = false;
    render();
  }
}

async function deleteSelectedBot() {
  const bot = selectedSummary || bots.find((item) => botIdsEqual(item.id, selectedBotId));
  if (!bot || isDeletingBot) return;

  const botName = formatValue(bot.name, t("unnamed_bot"));
  if (!window.confirm(t("delete_bot_confirm", { name: botName }))) return;

  isDeletingBot = true;
  actionMessage = "";
  actionMessageType = "";
  refreshMessage = "";
  refreshMessageType = "";
  render();

  try {
    await fetchJson(`/api/v1/bots/${bot.id}`, { method: "DELETE" });
    bots = bots.filter((item) => !botIdsEqual(item.id, bot.id));
    hasUserSelectedBot = false;
    selectedBotId = null;
    selectedSummary = null;
    selectedBotConfig = null;
    selectedExecutionProfile = null;
    isEditBotOpen = false;
    await refreshDashboardData();

    const successMessage = t("deleted_bot_success", { name: botName });
    if (selectedBotId) {
      actionMessage = successMessage;
      actionMessageType = "success";
    } else {
      refreshMessage = successMessage;
      refreshMessageType = "success";
    }
  } catch (error) {
    actionMessage = requestErrorMessage(error, t("could_not_delete_bot"));
    actionMessageType = "error";
  } finally {
    isDeletingBot = false;
    render();
  }
}

function validationMessage(error) {
  return error?.status === 422
    ? t("check_symbol_positive_price")
    : requestErrorMessage(error, t("could_not_update_price"));
}

function createBotValidationMessage(error) {
  if (error?.status === 422) {
    return validationErrorsMessage(error?.data?.errors, t("check_bot_fields"));
  }
  return requestErrorMessage(error, t("could_not_create_bot"));
}

function editBotValidationMessage(error) {
  if (error?.status === 422) {
    return validationErrorsMessage(error?.data?.errors, t("check_bot_fields"));
  }
  return requestErrorMessage(error, t("could_not_update_bot"));
}

function binancePriceErrorMessage(error) {
  const message = String(error?.message || "");
  if (error?.status === 400 || message.includes("status 400")) {
    return t("binance_symbol_not_found");
  }
  return requestErrorMessage(error, t("could_not_fetch_binance_price"));
}

function validateCreateBotForm() {
  if (!createBotName.value.trim()) {
    return t("enter_bot_name");
  }
  if (!createBotExchangeName.value.trim()) {
    return t("enter_exchange_name");
  }
  if (strategyLoadError) {
    return t("could_not_load_strategies", { detail: strategyLoadError });
  }
  if (isLoadingStrategies) {
    return t("strategies_still_loading");
  }
  if (strategies.length === 0) {
    return t("create_strategy_first_then_create_bot");
  }
  if (!createBotStrategyId.value) {
    return t("select_strategy");
  }
  return "";
}

function validateEditBotForm() {
  if (!editBotName.value.trim()) {
    return t("enter_bot_name");
  }
  if (!editBotExchangeName.value.trim()) {
    return t("enter_exchange_name");
  }
  if (strategyLoadError) {
    return t("could_not_load_strategies", { detail: strategyLoadError });
  }
  if (isLoadingStrategies) {
    return t("strategies_still_loading");
  }
  if (strategies.length === 0) {
    return t("create_strategy_first_then_edit_bot");
  }
  if (!editBotStrategyId.value) {
    return t("select_strategy");
  }
  return "";
}

function resetCreateBotForm() {
  createBotName.value = "";
  createBotStrategyId.value = strategies[0] ? String(strategies[0].id) : "";
  createBotExchangeName.value = "binance";
  createBotNotes.value = "";
}

function populateEditBotForm(botConfig) {
  editBotName.value = botConfig?.name ?? "";
  editBotStrategyId.value = botConfig?.strategyId ? String(botConfig.strategyId) : "";
  editBotExchangeName.value = botConfig?.exchangeName ?? "";
  editBotNotes.value = botConfig?.notes ?? "";
}

async function openEditBotForm() {
  if (!selectedBotId || isLoadingEditBot) return;

  if (strategies.length === 0 && !isLoadingStrategies && !strategyLoadError) {
    await loadStrategies();
  }

  isLoadingEditBot = true;
  isEditBotOpen = true;
  editBotMessage = "";
  editBotMessageType = "";
  render();

  try {
    const data = await fetchJson(`/api/v1/bots/${selectedBotId}`);
    selectedBotConfig = normalizeBotConfig(data);
    populateEditBotForm(selectedBotConfig);
  } catch (error) {
    editBotMessage = requestErrorMessage(error, t("could_not_load_bot_settings"));
    editBotMessageType = "error";
  } finally {
    isLoadingEditBot = false;
    render();
  }
}

function closeEditBotForm() {
  isEditBotOpen = false;
  isLoadingEditBot = false;
  editBotMessage = "";
  editBotMessageType = "";
  render();
}

function openStrategyParametersForm() {
  if (!selectedBotId || !selectedSummary || !strategyIdForSelectedBot() || isSavingStrategyParameters) {
    strategyParametersMessage = t("strategy_details_unavailable");
    strategyParametersMessageType = "error";
    render();
    return;
  }

  if (!canEditSelectedStrategyParameters()) {
    isEditingStrategyParameters = false;
    strategyParametersMessage = t("strategy_parameters_edit_unavailable");
    strategyParametersMessageType = "note";
    render();
    return;
  }

  populateStrategyParametersForm();
  isEditingStrategyParameters = true;
  strategyParametersMessage = "";
  strategyParametersMessageType = "";
  render();
}

function closeStrategyParametersForm() {
  isEditingStrategyParameters = false;
  isSavingStrategyParameters = false;
  strategyParametersMessage = "";
  strategyParametersMessageType = "";
  populateStrategyParametersForm();
  render();
}

async function submitCreateBot(event) {
  event.preventDefault();
  if (isCreatingBot) return;

  const validationError = validateCreateBotForm();
  if (validationError) {
    createBotMessage = validationError;
    createBotMessageType = "error";
    isCreateBotOpen = true;
    render();
    return;
  }

  isCreatingBot = true;
  createBotMessage = "";
  createBotMessageType = "";
  render();

  const payload = {
    name: createBotName.value.trim(),
    strategy_id: Number(createBotStrategyId.value.trim()),
    exchange_name: createBotExchangeName.value.trim(),
  };

  const notes = createBotNotes.value.trim();
  if (notes) {
    payload.notes = notes;
  }

  try {
    const createdBot = await fetchJson("/api/v1/bots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    clearSelectedBotMessages();
    hasUserSelectedBot = true;
    selectedBotId = createdBot.id;
    await refreshDashboardData();
    createBotMessage = t("created_bot_success", { name: createdBot.name });
    createBotMessageType = "success";
    isCreateBotOpen = true;
    resetCreateBotForm();
  } catch (error) {
    createBotMessage = createBotValidationMessage(error);
    createBotMessageType = "error";
    isCreateBotOpen = true;
  } finally {
    isCreatingBot = false;
    render();
  }
}

async function submitEditBot(event) {
  event.preventDefault();
  if (!selectedBotId || isSavingEditBot) return;

  const validationError = validateEditBotForm();
  if (validationError) {
    editBotMessage = validationError;
    editBotMessageType = "error";
    isEditBotOpen = true;
    render();
    return;
  }

  const payload = {
    name: editBotName.value.trim(),
    strategy_id: Number(editBotStrategyId.value.trim()),
    exchange_name: editBotExchangeName.value.trim(),
    notes: editBotNotes.value.trim() || null,
  };

  isSavingEditBot = true;
  editBotMessage = "";
  editBotMessageType = "";
  render();

  try {
    const updatedBot = await fetchJson(`/api/v1/bots/${selectedBotId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await refreshDashboardData();
    actionMessage = t("updated_bot_success", { name: updatedBot.name });
    actionMessageType = "success";
    closeEditBotForm();
  } catch (error) {
    editBotMessage = editBotValidationMessage(error);
    editBotMessageType = "error";
    isEditBotOpen = true;
    render();
  } finally {
    isSavingEditBot = false;
    render();
  }
}

async function submitExecutionSettings(event) {
  event.preventDefault();
  if (!selectedBotId || selectedExecutionProfile || isCreatingExecutionProfile) return;

  const validationError = validateExecutionSettingsForm();
  if (validationError) {
    executionSettingsMessage = validationError;
    executionSettingsMessageType = "error";
    render();
    return;
  }

  isCreatingExecutionProfile = true;
  executionSettingsMessage = "";
  executionSettingsMessageType = "";
  hasUserSelectedBot = true;
  render();

  try {
    const botUpdatePayload = executionBotUpdatePayload();
    if (Object.keys(botUpdatePayload).length > 0) {
      const updatedBot = await fetchJson(`/api/v1/bots/${selectedBotId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(botUpdatePayload),
      });
      selectedBotConfig = normalizeBotConfig(updatedBot);
    }

    const createdProfile = await fetchJson(`/api/v1/bots/${selectedBotId}/execution-profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(executionProfilePayload()),
    });
    selectedExecutionProfile = normalizeExecutionProfile(createdProfile);
    actionMessage = t("execution_settings_created");
    actionMessageType = "success";
    await refreshSelectedData();
  } catch (error) {
    executionSettingsMessage = requestErrorMessage(error, t("execution_settings_create_failed"));
    executionSettingsMessageType = "error";
  } finally {
    isCreatingExecutionProfile = false;
    render();
  }
}

async function submitStrategyParameters(event) {
  event.preventDefault();
  if (isSavingStrategyParameters) return;

  const strategyId = strategyIdForSelectedBot();
  const validationError = validateStrategyParametersForm();
  if (validationError) {
    strategyParametersMessage = validationError;
    strategyParametersMessageType = "error";
    isEditingStrategyParameters = true;
    render();
    return;
  }

  isSavingStrategyParameters = true;
  strategyParametersMessage = "";
  strategyParametersMessageType = "";
  render();

  const parameters = strategyParameterPayload();

  try {
    await fetchJson(`/api/v1/strategies/${strategyId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters }),
    });
    await loadSelectedSummary(selectedBotId);
    isEditingStrategyParameters = false;
    strategyParametersMessage = t("strategy_parameters_updated");
    strategyParametersMessageType = "success";
  } catch (error) {
    strategyParametersMessage = requestErrorMessage(error, t("strategy_parameters_save_failed"));
    strategyParametersMessageType = "error";
    isEditingStrategyParameters = true;
  } finally {
    isSavingStrategyParameters = false;
    render();
  }
}

async function submitRiskSettings(event) {
  event.preventDefault();
  if (!selectedBotId || isSavingRiskSettings) return;

  const validationError = validateRiskSettingsForm();
  if (validationError) {
    riskSettingsMessage = validationError;
    riskSettingsMessageType = "error";
    render();
    return;
  }

  isSavingRiskSettings = true;
  riskSettingsMessage = "";
  riskSettingsMessageType = "";
  render();

  try {
    const updatedProfile = await fetchJson(`/api/v1/bots/${selectedBotId}/execution-profile`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(riskSettingsPayload()),
    });
    selectedExecutionProfile = normalizeExecutionProfile(updatedProfile);
    riskSettingsMessage = t("risk_settings_updated");
    riskSettingsMessageType = "success";
  } catch (error) {
    riskSettingsMessage = requestErrorMessage(error, t("risk_settings_save_failed"));
    riskSettingsMessageType = "error";
  } finally {
    isSavingRiskSettings = false;
    render();
  }
}

async function submitBacktest(event) {
  event.preventDefault();
  if (isRunningBacktest) return;

  const validationError = validateBacktestForm();
  if (validationError) {
    backtestMessage = validationError;
    backtestMessageType = "error";
    render();
    return;
  }

  const payload = {
    strategy_id: Number(selectedBacktestStrategyId()),
    initial_balance: backtestInitialBalance.value.trim(),
  };
  const source = backtestSource.value.trim();
  if (source) {
    payload.source = source;
  }

  isRunningBacktest = true;
  backtestMessage = "";
  backtestMessageType = "";
  render();

  try {
    const result = await fetchJson("/api/v1/backtests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    backtestResult = normalizeBacktestResult(result);
    backtestMessage = t("backtest_completed");
    backtestMessageType = "success";
    isRunningBacktest = false;
    render();
    await loadBacktestHistory();
  } catch (error) {
    backtestResult = null;
    backtestMessage =
      error?.status === 404
        ? t("backtest_strategy_not_found")
        : friendlyBacktestErrorMessage(error, t("could_not_run_backtest"));
    backtestMessageType = "error";
  } finally {
    isRunningBacktest = false;
    render();
  }
}

async function importBacktestBinanceCandles(event) {
  event.preventDefault();
  if (isImportingBacktestCandles || isRunningBacktest) return;

  const { symbol, timeframe } = selectedBacktestCandleTarget();
  const limit = parseBacktestCandleLimit();
  if (!symbol || !timeframe) {
    backtestImportMessage = t("candle_import_strategy_missing");
    backtestImportMessageType = "error";
    render();
    return;
  }
  if (limit === null) {
    backtestImportMessage = t("candle_import_validation_failed");
    backtestImportMessageType = "error";
    render();
    return;
  }

  isImportingBacktestCandles = true;
  backtestImportMessage = "";
  backtestImportMessageType = "";
  render();

  try {
    const result = await fetchJson("/api/v1/market/binance/candles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, timeframe, limit }),
    });
    backtestSource.value = "binance";
    backtestImportMessage = t("candle_import_completed", {
      count: formatDecimal(result?.stored_count ?? result?.candles?.length ?? 0),
      symbol: formatValue(result?.symbol, symbol),
      timeframe: formatValue(result?.timeframe, timeframe),
    });
    backtestImportMessageType = "success";
    await loadBacktestHistory();
  } catch (error) {
    backtestImportMessage = friendlyCandleImportErrorMessage(error);
    backtestImportMessageType = "error";
  } finally {
    isImportingBacktestCandles = false;
    render();
  }
}

async function submitBacktestOptimization(event) {
  event.preventDefault();
  if (isRunningBacktestOptimization || isRunningBacktest || isImportingBacktestCandles) return;

  const validationError = validateBacktestForm();
  if (validationError) {
    backtestOptimizationMessage = validationError;
    backtestOptimizationMessageType = "error";
    render();
    return;
  }

  const generated = optimizationParameterSets();
  if (generated.error) {
    backtestOptimizationMessage = generated.error;
    backtestOptimizationMessageType = "error";
    render();
    return;
  }

  const minClosedTrades = parseNonNegativeInteger(optimizationMinClosedTrades.value);
  if (minClosedTrades === null) {
    backtestOptimizationMessage = t("optimization_quality_filters_invalid");
    backtestOptimizationMessageType = "error";
    render();
    return;
  }

  const payload = {
    strategy_id: Number(selectedBacktestStrategyId()),
    initial_balance: backtestInitialBalance.value.trim(),
    parameter_sets: generated.parameterSets,
    min_closed_trades: minClosedTrades,
    require_closed_position: optimizationRequireClosedPosition.checked,
  };
  const source = backtestSource.value.trim();
  if (source) {
    payload.source = source;
  }

  isRunningBacktestOptimization = true;
  backtestOptimizationMessage = "";
  backtestOptimizationMessageType = "";
  backtestOptimizationResult = null;
  showMeaningfulOptimizationOnly = false;
  showPassedOptimizationOnly = false;
  render();

  try {
    const result = await fetchJson("/api/v1/backtests/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    backtestOptimizationResult = normalizeOptimizationResponse(result);
    backtestOptimizationMessage = t("optimization_completed", {
      count: formatDecimal(backtestOptimizationResult.totalRuns),
    });
    backtestOptimizationMessageType = "success";
  } catch (error) {
    backtestOptimizationMessage = requestErrorMessage(error, t("optimization_failed"));
    backtestOptimizationMessageType = "error";
  } finally {
    isRunningBacktestOptimization = false;
    render();
  }
}

async function applyOptimizationParametersToStrategy(resultItem) {
  if (isApplyingOptimizationParameters) return;

  const strategyId = backtestOptimizationResult?.strategyId ?? selectedBacktestStrategyId();
  const strategy = optimizationResultStrategy();
  const strategyName = strategy?.name || selectedSummary?.strategyName || t("unnamed_strategy");
  const appliedParameters = optimizationApplyParameters(resultItem);
  const selectedBotStrategyId = strategyIdForSelectedBot();
  const selectedBotUsesStrategy = botIdsEqual(selectedBotStrategyId, strategyId);
  if (!strategyId || (!strategy && !selectedBotUsesStrategy) || Object.keys(appliedParameters).length === 0) {
    backtestOptimizationMessage = t("optimization_apply_unavailable");
    backtestOptimizationMessageType = "error";
    render();
    return;
  }

  const parameterSummary = optimizationParametersLabel(appliedParameters);
  if (
    !window.confirm(
      t("optimization_apply_confirm", {
        strategy: strategyName,
        parameters: parameterSummary,
      }),
    )
  ) {
    return;
  }

  const currentParameters = selectedBotUsesStrategy
    ? selectedSummary?.strategyParameters
    : strategy?.parameters;
  const parameters = {
    ...(currentParameters && typeof currentParameters === "object" ? currentParameters : {}),
    ...appliedParameters,
  };

  isApplyingOptimizationParameters = true;
  backtestOptimizationMessage = "";
  backtestOptimizationMessageType = "";
  strategyParametersMessage = "";
  strategyParametersMessageType = "";
  hasUserSelectedBot = Boolean(selectedBotId);
  render();

  try {
    const updatedStrategy = await fetchJson(`/api/v1/strategies/${strategyId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters }),
    });
    updateStrategyInList(updatedStrategy);
    await loadStrategies();
    if (selectedBotId) {
      await loadSelectedSummary(selectedBotId);
    } else {
      await loadBacktestHistory();
    }
    if (selectedBotUsesStrategy) {
      isEditingStrategyParameters = false;
      strategyParametersMessage = t("strategy_parameters_updated");
      strategyParametersMessageType = "success";
    }
    backtestOptimizationMessage = t("optimization_apply_success", { strategy: strategyName });
    backtestOptimizationMessageType = "success";
  } catch (error) {
    backtestOptimizationMessage = requestErrorMessage(error, t("optimization_apply_failed"));
    backtestOptimizationMessageType = "error";
  } finally {
    isApplyingOptimizationParameters = false;
    render();
  }
}

async function updateMarketPrice(event) {
  event.preventDefault();
  if (isUpdatingPrice) return;

  const symbol = priceSymbol.value.trim().toUpperCase();
  const price = priceValue.value.trim();

  isUpdatingPrice = true;
  priceMessage = "";
  priceMessageType = "";
  render();

  try {
    await fetchJson("/api/v1/market/price", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, price }),
    });
    priceSymbol.value = symbol;
    priceMessage = t("price_updated");
    priceMessageType = "success";

    if (selectedBotId) {
      await refreshSelectedData();
    }
  } catch (error) {
    priceMessage = validationMessage(error);
    priceMessageType = "error";
  } finally {
    isUpdatingPrice = false;
    render();
  }
}

async function fetchBinancePriceForSelectedBot() {
  if (isFetchingBinancePrice) return;

  const symbol = selectedBotSymbol();
  if (!selectedBotId) {
    priceMessage = t("select_bot_for_binance_price");
    priceMessageType = "error";
    render();
    return;
  }
  if (!symbol) {
    priceMessage = t("missing_symbol_for_binance_price");
    priceMessageType = "error";
    render();
    return;
  }

  isFetchingBinancePrice = true;
  priceMessage = "";
  priceMessageType = "";
  render();

  try {
    const result = await fetchJson("/api/v1/market/binance/price", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol }),
    });
    priceSymbol.value = result.symbol ?? symbol;
    priceValue.value = formatDecimal(result.price, "");
    priceMessage = t("fetched_binance_price", {
      symbol: result.symbol ?? symbol,
      price: formatDecimal(result.price),
    });
    priceMessageType = "success";

    if (selectedBotId) {
      await refreshSelectedData();
    }
  } catch (error) {
    priceMessage = binancePriceErrorMessage(error);
    priceMessageType = "error";
  } finally {
    isFetchingBinancePrice = false;
    render();
  }
}

async function loadSelectedSummary(botId) {
  summaryError = "";
  actionMessage = "";
  actionMessageType = "";
  isLoadingSummary = true;
  selectedSummary = null;
  selectedBotConfig = null;
  selectedExecutionProfile = null;
  render();

  try {
    const [summaryResult, configResult, profileResult] = await Promise.allSettled([
      fetchJson(`/api/v1/bots/${botId}/summary`),
      fetchJson(`/api/v1/bots/${botId}`),
      fetchJson(`/api/v1/bots/${botId}/execution-profile`),
    ]);

    if (summaryResult.status !== "fulfilled") {
      throw summaryResult.reason;
    }

    selectedSummary = normalizeSummary(summaryResult.value);
    if (configResult.status === "fulfilled") {
      selectedBotConfig = normalizeBotConfig(configResult.value);
    }
    if (profileResult.status === "fulfilled") {
      selectedExecutionProfile = normalizeExecutionProfile(profileResult.value);
    }
  } catch (error) {
    selectedSummary = null;
    selectedBotConfig = null;
    selectedExecutionProfile = null;
    summaryError = requestErrorMessage(error, t("could_not_load_bot_details"));
  } finally {
    isLoadingSummary = false;
  }

  render();
  await loadBacktestHistory();
}

function renderBotList() {
  botList.innerHTML = "";
  botSearch.value = botSearchQuery;

  if (isLoadingBots) {
    botCount.textContent = t("loading_generic");
    botList.innerHTML = `<div class="state-message loading">${t("loading_bots")}</div>`;
    return;
  }

  if (botListError) {
    botCount.textContent = t("activity_failed");
    botList.innerHTML = `<div class="state-message error">${botListError}</div>`;
    return;
  }

  const visibleBots = filteredBots();
  botCount.textContent = botSearchQuery
    ? t("filtered_bot_count", { visible: visibleBots.length, total: bots.length })
    : botCountText(bots.length);

  if (bots.length === 0) {
    botList.innerHTML = `<div class="state-message">${t("no_bots_yet")}</div>`;
    return;
  }

  if (visibleBots.length === 0) {
    botList.innerHTML = `<div class="state-message">${t("no_bots_match_search")}</div>`;
    return;
  }

  visibleBots.forEach((bot) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "bot-row";
    row.setAttribute("aria-selected", String(botIdsEqual(bot.id, selectedBotId)));
    row.addEventListener("click", async () => {
      if (botIdsEqual(bot.id, selectedBotId)) return;
      clearSelectedBotMessages();
      hasUserSelectedBot = true;
      selectedBotId = bot.id;
      isEditBotOpen = false;
      selectedBotConfig = null;
      await loadSelectedSummary(bot.id);
    });

    row.innerHTML = `
      <span class="bot-row-main">
        <strong class="bot-row-name">${formatValue(bot.name, t("unnamed_bot"))}</strong>
        <span class="bot-row-symbol">${formatValue(bot.symbol)}</span>
      </span>
      <span class="bot-meta">
        <span class="list-status ${statusClass(bot.status)}">${formatStatus(bot.status)}</span>
        <span>${formatDateTime(bot.updatedAt)}</span>
      </span>
    `;

    botList.appendChild(row);
  });
}

function renderCreateBotForm() {
  createBotForm.setAttribute("data-open", String(isCreateBotOpen));
  toggleCreateBot.textContent = isCreateBotOpen ? t("close") : t("create_bot");
  toggleCreateBot.disabled = isCreatingBot;
  createBotSubmit.textContent = isCreatingBot ? t("creating") : t("create_draft_bot");
  createBotSubmit.disabled =
    isCreatingBot || isLoadingStrategies || strategies.length === 0 || Boolean(strategyLoadError);
  renderStrategySelect(createBotStrategyId, createBotStrategyId.value);

  createBotStrategyHelp.textContent = isLoadingStrategies
    ? t("loading_available_strategies")
    : strategyLoadError
      ? t("could_not_load_strategies", { detail: strategyLoadError })
      : strategies.length === 0
        ? t("create_strategy_first_create_bot")
        : "";
  createBotStrategyHelp.className = strategyLoadError
    ? "create-bot-help error"
    : "create-bot-help";

  createBotMessageEl.textContent = createBotMessage;
  createBotMessageEl.className = createBotMessageType
    ? `form-message ${createBotMessageType}`
    : "form-message";
}

function renderEditBotForm() {
  editBotForm.setAttribute("data-open", String(isEditBotOpen));
  editBot.textContent = isLoadingEditBot ? t("loading_generic") : t("edit");
  editBot.disabled =
    !selectedBotId || isLoadingSummary || isLoadingEditBot || isSavingEditBot || isDeletingBot;
  editBotSubmit.textContent = isSavingEditBot ? t("saving") : t("save_changes");
  editBotSubmit.disabled =
    isSavingEditBot ||
    isLoadingEditBot ||
    isLoadingStrategies ||
    strategies.length === 0 ||
    Boolean(strategyLoadError) ||
    !selectedBotId;
  editBotCancel.disabled = isSavingEditBot;
  editBotStatus.textContent = formatStatus(selectedBotConfig?.status ?? selectedSummary?.status ?? "draft");
  editBotStatus.className = `status-pill ${statusClass(
    selectedBotConfig?.status ?? selectedSummary?.status ?? "draft",
  )}`;
  editBotMode.textContent = selectedBotConfig?.isPaper === false ? t("live_mode") : t("paper_mode");
  editBotCancel.textContent = t("cancel");

  if (!isSavingEditBot) {
    renderStrategySelect(editBotStrategyId, selectedBotConfig?.strategyId ?? editBotStrategyId.value);
  }

  editBotStrategyHelp.textContent = isLoadingStrategies
    ? t("loading_available_strategies")
    : strategyLoadError
      ? t("could_not_load_strategies", { detail: strategyLoadError })
      : strategies.length === 0
        ? t("create_strategy_first_edit_bot")
        : "";
  editBotStrategyHelp.className = strategyLoadError
    ? "create-bot-help error"
    : "create-bot-help";

  editBotMessageEl.textContent = editBotMessage;
  editBotMessageEl.className = editBotMessageType
    ? `form-message ${editBotMessageType}`
    : "form-message";
}

function renderStrategyParameters(bot) {
  strategyParametersContent.innerHTML = "";

  if (!bot) {
    strategyParametersContent.textContent = selectedBotId
      ? t("strategy_details_unavailable")
      : t("no_strategy_selected");
    strategyParametersContent.className = "strategy-parameters-content empty";
    return;
  }

  if (selectedBotId && isLoadingSummary && !selectedSummary) {
    strategyParametersContent.textContent = t("loading_details");
    strategyParametersContent.className = "strategy-parameters-content empty loading";
    return;
  }

  if (!selectedSummary) {
    strategyParametersContent.textContent = t("strategy_details_unavailable");
    strategyParametersContent.className = summaryError
      ? "strategy-parameters-content empty error"
      : "strategy-parameters-content empty";
    return;
  }

  const strategyRows = [
    {
      label: t("strategy_name_label"),
      value: formatValue(selectedSummary.strategyName, t("unnamed_strategy")),
    },
    {
      label: t("strategy_type_label"),
      value: humanizeMessage(selectedSummary.strategyType),
    },
    {
      label: t("symbol"),
      value: formatValue(selectedSummary.symbol),
    },
    {
      label: t("timeframe_label"),
      value: formatValue(selectedSummary.strategyTimeframe),
    },
  ];
  const parameterRows = orderedStrategyParameters(selectedSummary.strategyParameters);
  const grid = document.createElement("dl");
  grid.className = "strategy-parameters-grid";

  [...strategyRows, ...parameterRows].forEach((item) => {
    const row = document.createElement("div");
    const label = document.createElement("dt");
    const value = document.createElement("dd");
    label.textContent = item.label;
    value.textContent = formatParameterValue(item.value);
    row.append(label, value);
    grid.append(row);
  });

  strategyParametersContent.className = "strategy-parameters-content";
  strategyParametersContent.append(grid);

  if (parameterRows.length === 0) {
    const empty = document.createElement("p");
    empty.className = "strategy-parameters-empty";
    empty.textContent = t("no_strategy_parameters_configured");
    strategyParametersContent.append(empty);
  }
}

function renderBotSettings(bot) {
  botSettingsContent.innerHTML = "";

  if (selectedBotId && isLoadingSummary && !selectedSummary) {
    botSettingsContent.textContent = t("loading_details");
    botSettingsContent.className = "bot-settings-content empty loading";
    return;
  }

  if (!bot) {
    botSettingsContent.textContent = botListError
      ? t("bot_settings_unavailable")
      : bots.length === 0
        ? t("no_bots_available_yet")
        : t("select_bot_to_view_details");
    botSettingsContent.className = botListError
      ? "bot-settings-content empty error"
      : "bot-settings-content empty";
    return;
  }

  if (summaryError && !selectedSummary) {
    botSettingsContent.textContent = t("bot_settings_unavailable");
    botSettingsContent.className = "bot-settings-content empty error";
    return;
  }

  const exchangeName = selectedBotConfig?.exchangeName;
  const isPaper = selectedBotConfig?.isPaper;
  const rows = [
    {
      label: t("bot_name_label"),
      value: formatValue(firstAvailable(selectedBotConfig?.name, bot.name), t("unnamed_bot")),
    },
    {
      label: t("status_label"),
      value: formatStatus(firstAvailable(selectedBotConfig?.status, bot.status)),
    },
    {
      label: t("symbol"),
      value: formatValue(bot.symbol, "—"),
    },
    {
      label: t("strategy_type_label"),
      value: bot.strategyType ? humanizeMessage(bot.strategyType) : "—",
    },
    {
      label: t("exchange"),
      value: formatValue(exchangeName, "—"),
    },
    {
      label: t("paper_live_mode_label"),
      value: isPaper === null || isPaper === undefined ? "—" : modeLabel(isPaper),
    },
    {
      label: t("paused_label"),
      value: formatBoolean(bot.isPaused || bot.status === "paused"),
    },
    {
      label: t("cooldown_active_label"),
      value: formatBoolean(bot.cooldownActive),
    },
    {
      label: t("cooldown_until"),
      value: formatDateTime(bot.cooldownUntil),
    },
    {
      label: t("current_position_qty_label"),
      value: formatDecimal(bot.currentPositionQty),
    },
    {
      label: t("selected_price_label"),
      value: formatDecimal(bot.lastPrice),
    },
    {
      label: t("updated_time_label"),
      value: formatDateTime(bot.updatedAt),
    },
  ];

  const grid = document.createElement("dl");
  grid.className = "bot-settings-grid";

  rows.forEach((item) => {
    const row = document.createElement("div");
    const label = document.createElement("dt");
    const value = document.createElement("dd");
    label.textContent = item.label;
    value.textContent = item.value;
    row.append(label, value);
    grid.append(row);
  });

  botSettingsContent.className = "bot-settings-content";
  botSettingsContent.append(grid);
}

function renderSummary() {
  const listBot = bots.find((bot) => botIdsEqual(bot.id, selectedBotId));
  const bot = selectedSummary || listBot;
  const botMode = modeLabel(selectedBotConfig?.isPaper);
  const canRunNow = Boolean(selectedBotId && bot && isRunnableStatus(bot.status) && !bot.isPaused);
  const canUseLifecycleControl = Boolean(selectedBotId && bot);
  const binanceSymbol = selectedBotSymbol();
  const binanceHelpMessage = !selectedBotId
    ? t("select_bot_for_binance_price")
    : !binanceSymbol
      ? t("missing_symbol_for_binance_price")
      : "";

  if (!bot) {
    isEditingStrategyParameters = false;
    selectedSymbol.textContent = "";
    selectedName.textContent = botListError
      ? t("details_unavailable")
      : bots.length === 0
        ? t("no_bots_available_yet")
        : t("select_bot_to_view_details");
    selectedStatus.textContent = "idle";
    selectedStatus.className = "status-pill status-idle";
    selectedState.textContent = t("mode_ready");
    selectedMode.textContent = t("paper_mode");
    selectedStrategy.textContent = "—";
    selectedCooldown.textContent = bots.length === 0 ? t("add_bot_to_get_started") : "—";
    selectedPrice.textContent = "—";
    selectedLastRun.textContent = bots.length === 0 ? t("no_bot_activity_yet") : "—";
    renderBotSettings(null);
    renderExecutionSettingsForm();
    renderStrategyParameters(null);
    renderRiskSettingsForm();
    pauseResume.textContent = t("pause");
    pauseResume.disabled = true;
    runNow.textContent = t("run_now");
    runNow.disabled = true;
    editBot.textContent = t("edit");
    editBot.disabled = true;
    deleteBot.textContent = t("delete_bot");
    deleteBot.disabled = true;
    actionHelp.textContent = actionHelpText(null);
    if (!symbolTouched) {
      priceSymbol.value = "";
    }
    priceSubmit.textContent = isUpdatingPrice ? t("updating") : t("set_price");
    priceSubmit.disabled = isUpdatingPrice;
    binancePriceFetch.textContent = isFetchingBinancePrice
      ? t("fetching_binance_price")
      : t("fetch_binance_price");
    binancePriceFetch.disabled = true;
    actionMessageEl.textContent = "";
    actionMessageEl.className = "action-message";
    priceMessageEl.textContent = priceMessage || binanceHelpMessage;
    priceMessageEl.className = priceMessageType
      ? `form-message ${priceMessageType}`
      : "form-message";
    return;
  }

  selectedSymbol.textContent = formatValue(bot.symbol);
  selectedName.textContent = isLoadingSummary
    ? t("loading_details")
    : formatValue(bot.name, t("unnamed_bot"));
  selectedStatus.textContent = formatStatus(bot.status);
  selectedStatus.className = `status-pill ${statusClass(bot.status)}`;
  selectedState.textContent = stateLabel(bot);
  selectedMode.textContent = botMode;
  selectedStrategy.textContent = bot.strategyType ? humanizeMessage(bot.strategyType) : "—";
  selectedCooldown.textContent = cooldownText(bot);
  selectedPrice.textContent = formatDecimal(bot.lastPrice);
  selectedLastRun.textContent = formatDateTime(bot.updatedAt);
  renderBotSettings(bot);
  renderExecutionSettingsForm();
  renderStrategyParameters(bot);
  renderRiskSettingsForm();
  pauseResume.textContent = isTogglingPause
    ? pauseResumeLoadingLabel(bot.status)
    : pauseResumeLabel(bot.status);
  pauseResume.disabled =
    !canUseLifecycleControl ||
    isTogglingPause ||
    isDeletingBot ||
    isLoadingSummary ||
    isRunningNow ||
    isCreatingExecutionProfile;
  runNow.textContent = isRunningNow ? t("running_now") : t("run_now");
  runNow.disabled =
    !canRunNow ||
    isRunningNow ||
    isDeletingBot ||
    isLoadingSummary ||
    isTogglingPause ||
    isCreatingExecutionProfile;
  editBot.textContent = isLoadingEditBot ? t("loading_generic") : t("edit");
  editBot.disabled =
    !selectedBotId ||
    isLoadingSummary ||
    isLoadingEditBot ||
    isSavingEditBot ||
    isDeletingBot ||
    isRunningNow ||
    isTogglingPause ||
    isCreatingExecutionProfile;
  deleteBot.textContent = isDeletingBot ? t("deleting_bot") : t("delete_bot");
  deleteBot.disabled =
    !selectedBotId ||
    isDeletingBot ||
    isLoadingSummary ||
    isLoadingEditBot ||
    isSavingEditBot ||
    isRunningNow ||
    isTogglingPause ||
    isCreatingExecutionProfile;
  actionHelp.textContent = actionHelpText(bot);
  if (!symbolTouched) {
    priceSymbol.value = formatValue(bot.symbol, "");
  }
  if (!priceValue.value) {
    priceValue.value = formatDecimal(bot.lastPrice, "");
  }
  priceSubmit.textContent = isUpdatingPrice ? t("updating") : t("set_price");
  priceSubmit.disabled = isUpdatingPrice;
  binancePriceFetch.textContent = isFetchingBinancePrice
    ? t("fetching_binance_price")
    : t("fetch_binance_price");
  binancePriceFetch.disabled =
    isFetchingBinancePrice ||
    isLoadingSummary ||
    isRunningNow ||
    isTogglingPause ||
    isDeletingBot ||
    !selectedBotId ||
    !binanceSymbol;
  actionMessageEl.textContent = actionMessage;
  actionMessageEl.className = actionMessageType
    ? `action-message ${actionMessageType}`
    : "action-message";
  priceMessageEl.textContent = priceMessage || binanceHelpMessage;
  priceMessageEl.className = priceMessageType
    ? `form-message ${priceMessageType}`
    : "form-message";
}

function renderDecisionExplanation() {
  decisionPanel.innerHTML = "";
  decisionPanel.hidden = !latestDecisionExplanation;
  decisionPanel.setAttribute("aria-label", t("decision_explanation"));

  if (!latestDecisionExplanation) return;

  const decision = latestDecisionExplanation.decision || t("activity_event");
  const decisionLabel = formatDecisionLabel(decision);
  const reasonLabel = formatDecisionReason(latestDecisionExplanation);
  const riskReason = firstRiskMessage(
    latestDecisionExplanation.detail,
    latestDecisionExplanation.message,
    latestDecisionExplanation.reason,
  );
  const rows = [
    { label: t("decision_reason_label"), value: reasonLabel },
    { label: t("current_price_label"), value: formatDecimal(latestDecisionExplanation.currentPrice) },
    { label: t("buy_threshold_label"), value: formatDecimal(latestDecisionExplanation.buyBelow) },
    { label: t("sell_threshold_label"), value: formatDecimal(latestDecisionExplanation.sellAbove) },
    { label: t("position_qty_label"), value: formatDecimal(latestDecisionExplanation.positionQty) },
  ];

  const grid = document.createElement("dl");
  grid.className = "decision-grid";
  rows.forEach((item) => {
    const row = document.createElement("div");
    const label = document.createElement("dt");
    const value = document.createElement("dd");
    if (item.label === t("decision_reason_label")) {
      row.className = "decision-reason-cell";
    }
    label.textContent = item.label;
    value.textContent = item.value;
    row.append(label, value);
    grid.append(row);
  });

  const heading = document.createElement("div");
  heading.className = "decision-heading";
  const title = document.createElement("h2");
  const badge = document.createElement("span");
  title.textContent = t("decision_explanation");
  badge.className = `decision-badge ${decisionClass(decision)}`;
  badge.textContent = decisionLabel;
  heading.append(title, badge);

  const chips = document.createElement("div");
  chips.className = "decision-chips";
  const decisionChip = document.createElement("span");
  decisionChip.className = `decision-chip ${decisionClass(decision)}`;
  decisionChip.textContent = `${t("decision_label")}: ${decisionLabel}`;
  chips.append(decisionChip);
  if (riskReason) {
    const riskChip = document.createElement("span");
    riskChip.className = "decision-chip decision-risk";
    riskChip.textContent = `${t("risk_reason_label")}: ${riskReason}`;
    chips.append(riskChip);
  }

  decisionPanel.append(heading, chips, grid);
}

function renderRefreshControl() {
  refreshDashboard.textContent = isRefreshing ? t("refreshing") : t("refresh");
  refreshDashboard.disabled = isRefreshing || hasInFlightAction();
  refreshMessageEl.textContent = refreshMessage;
  refreshMessageEl.className = refreshMessage
    ? `refresh-message ${refreshMessageType || "error"}`
    : "refresh-message";
}

function renderHeaderMeta() {
  headerMeta.textContent = `${botCountText(bots.length)} · ${t("last_refreshed")}: ${formatTime(lastRefreshedAt)}`;
}

function renderActivity() {
  activityList.innerHTML = "";

  if (summaryError) {
    activityList.innerHTML = `<li><span class="activity-empty error">${t("failed_to_load_recent_activity")} ${summaryError}</span></li>`;
    return;
  }

  const activity = selectedSummary?.recentActivity ?? [];
  const botName = activityBotName();

  if (selectedBotId && isLoadingSummary) {
    activityList.innerHTML = `<li><span class="activity-empty loading">${t("loading_recent_activity")}</span></li>`;
    return;
  }

  if (selectedBotId && selectedSummary && activity.length === 0) {
    activityList.innerHTML = `<li><span class="activity-empty">${t("no_recent_activity_yet")}</span></li>`;
    return;
  }

  if (!selectedBotId || !selectedSummary) {
    activityList.innerHTML = `<li><span class="activity-empty">${
      bots.length === 0
        ? t("no_bots_activity_after_create")
        : t("select_bot_to_view_activity")
    }</span></li>`;
    return;
  }

  activity.forEach((item) => {
    const row = document.createElement("li");
    const status = activityStatus(item);
    const details = activityDetailParts(item);
    if (botName) {
      details.unshift(`${t("bot_prefix")}: ${botName}`);
    }
    row.innerHTML = `
      <span class="activity-main">
        <span class="activity-meta">
          <span class="activity-status ${status.className}">${status.label}</span>
          <span class="activity-type">${formatActivityType(item)}</span>
        </span>
        <span class="activity-message">${formatActivityMessage(item)}</span>
        ${details.length > 0 ? `<span class="activity-details">${details.join(" · ")}</span>` : ""}
      </span>
      <span class="activity-time">${formatDateTime(item.timestamp ?? item.created_at)}</span>
    `;
    activityList.appendChild(row);
  });
}

function render() {
  renderHeaderMeta();
  renderRefreshControl();
  renderCreateBotForm();
  renderBotList();
  renderSummary();
  renderDecisionExplanation();
  renderStrategyParametersForm();
  renderBacktestPanel();
  renderBacktestHistory();
  renderEditBotForm();
  renderActivity();
}

langEn.addEventListener("click", () => setLanguage("en"));
langAm.addEventListener("click", () => setLanguage("am"));
refreshDashboard.addEventListener("click", () => refreshDashboardData());
autoRefresh.addEventListener("change", updateAutoRefresh);
toggleCreateBot.addEventListener("click", () => {
  isCreateBotOpen = !isCreateBotOpen;
  if (isCreateBotOpen && strategies.length === 0 && !isLoadingStrategies && !strategyLoadError) {
    loadStrategies();
  }
  if (!isCreateBotOpen && !isCreatingBot) {
    createBotMessage = "";
    createBotMessageType = "";
  }
  render();
});
botSearch.addEventListener("input", () => {
  botSearchQuery = botSearch.value;
  renderBotList();
});
document.addEventListener("visibilitychange", updateAutoRefresh);
window.addEventListener("beforeunload", stopAutoRefresh);
pauseResume.addEventListener("click", togglePauseResume);
runNow.addEventListener("click", runSelectedBotNow);
editBot.addEventListener("click", openEditBotForm);
deleteBot.addEventListener("click", deleteSelectedBot);
editBotCancel.addEventListener("click", closeEditBotForm);
editStrategyParameters.addEventListener("click", openStrategyParametersForm);
strategyParametersCancel.addEventListener("click", closeStrategyParametersForm);
createBotForm.addEventListener("submit", submitCreateBot);
editBotForm.addEventListener("submit", submitEditBot);
executionSettingsForm.addEventListener("submit", submitExecutionSettings);
strategyParametersForm.addEventListener("submit", submitStrategyParameters);
riskSettingsForm.addEventListener("submit", submitRiskSettings);
backtestForm.addEventListener("submit", submitBacktest);
backtestSubmit.addEventListener("click", submitBacktest);
backtestImportBinance.addEventListener("click", importBacktestBinanceCandles);
backtestOptimizationForm.addEventListener("submit", submitBacktestOptimization);
refreshBacktestHistory.addEventListener("click", loadBacktestHistory);
priceForm.addEventListener("submit", updateMarketPrice);
binancePriceFetch.addEventListener("click", fetchBinancePriceForSelectedBot);
priceSymbol.addEventListener("input", () => {
  symbolTouched = true;
});
backtestStrategyId.addEventListener("change", () => {
  backtestStrategyTouched = true;
  backtestResult = null;
  backtestMessage = "";
  backtestMessageType = "";
  backtestImportMessage = "";
  backtestImportMessageType = "";
  backtestOptimizationMessage = "";
  backtestOptimizationMessageType = "";
  backtestOptimizationResult = null;
  showMeaningfulOptimizationOnly = false;
  showPassedOptimizationOnly = false;
  backtestOptimizationTouched = false;
  optimizationMinClosedTrades.value = "0";
  optimizationRequireClosedPosition.checked = false;
  renderBacktestPanel();
});
[optimizationFirstValues, optimizationSecondValues, optimizationQuantity, optimizationMinClosedTrades].forEach((input) => {
  input.addEventListener("input", () => {
    backtestOptimizationTouched = true;
  });
});
optimizationRequireClosedPosition.addEventListener("change", () => {
  backtestOptimizationTouched = true;
});

document.documentElement.lang = currentLanguage === "am" ? "hy" : "en";
renderLanguageSwitcher();
applyStaticTranslations();
loadBots();
loadStrategies();
