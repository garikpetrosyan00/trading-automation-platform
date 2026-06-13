const API_BASE_URL = "";
const AUTO_REFRESH_MS = 10000;
const LIVE_MARKET_REFRESH_MS = 10000;
const CANDLE_CHART_WIDTH = 720;
const CANDLE_CHART_HEIGHT = 300;
const CANDLE_CHART_PLOT = {
  left: 44,
  right: 82,
  top: 16,
  bottom: 40,
};
CANDLE_CHART_PLOT.width = CANDLE_CHART_WIDTH - CANDLE_CHART_PLOT.left - CANDLE_CHART_PLOT.right;
CANDLE_CHART_PLOT.height = CANDLE_CHART_HEIGHT - CANDLE_CHART_PLOT.top - CANDLE_CHART_PLOT.bottom;
const LANGUAGE_STORAGE_KEY = "dashboard.language";
const LIVE_MARKET_STORAGE_KEY = "dashboard.liveMarketSymbols";
const LIVE_MARKET_AUTO_REFRESH_STORAGE_KEY = "dashboard.liveMarketAutoRefresh";
const DEFAULT_LANGUAGE = "en";
const SUPPORTED_LANGUAGES = new Set(["en", "am"]);
const DEFAULT_LIVE_MARKET_SYMBOLS = ["BTCUSDT", "ETHUSDT"];

let bots = [];
let strategies = [];
let selectedBotId = null;
let selectedSummary = null;
let selectedPerformance = null;
let paperPortfolio = null;
let recentPaperOrders = [];
let executionSafetyStatus = null;
let reconciliationWorkerStatus = null;
let recentReconciliationJobs = [];
let latestDecisionExplanation = null;
let isLoadingBots = true;
let isLoadingSummary = false;
let isLoadingPerformance = false;
let isLoadingPaperPortfolio = true;
let isLoadingRecentPaperOrders = false;
let isLoadingExecutionSafety = false;
let isLoadingReconciliationWorker = true;
let isLoadingRecentReconciliationJobs = true;
let isLoadingStrategies = false;
let isTogglingPause = false;
let isRunningNow = false;
let isUpdatingPrice = false;
let isFetchingBinancePrice = false;
let isRefreshing = false;
let isCreatingBot = false;
let isCreateBotOpen = false;
let isCreatingStrategy = false;
let isCreateStrategyOpen = false;
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
let performanceError = "";
let paperPortfolioError = "";
let recentPaperOrdersError = "";
let executionSafetyError = "";
let reconciliationWorkerError = "";
let recentReconciliationJobsError = "";
let actionMessage = "";
let actionMessageType = "";
let createBotMessage = "";
let createBotMessageType = "";
let createStrategyMessage = "";
let createStrategyMessageType = "";
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
let backtestHistoryScope = "selected";
let highlightedBacktestRunTimeout = null;
const expandedBacktestDetails = new Set();
let strategyLoadError = "";
let priceMessage = "";
let priceMessageType = "";
let liveMarketSymbols = getStoredLiveMarketSymbols();
let isRefreshingLiveMarket = false;
let liveMarketAutoRefreshEnabled = getStoredLiveMarketAutoRefresh();
let liveMarketTimer = null;
let liveMarketMessage = "";
let liveMarketMessageType = "";
let candleModal = {
  isOpen: false,
  symbol: "",
  timeframe: "1m",
  limit: 50,
  candleDate: "",
  candles: [],
  visibleStart: 0,
  visibleCount: null,
  isLoadingOlder: false,
  olderMessage: "",
  isLoading: false,
  error: "",
  requestId: 0,
};
let candleModalPreviousFocus = null;
let candleDragState = null;
let candleWheelPanRemainder = 0;
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
    create_strategy: "Create Strategy",
    strategies_heading: "Strategies",
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
    bot_performance: "Bot Performance",
    bot_performance_aria: "Bot Performance",
    bot_performance_unavailable: "Performance unavailable",
    bot_performance_loading: "Loading performance…",
    bot_performance_select_bot: "Select a bot to view performance.",
    bot_performance_no_activity: "No activity recorded yet.",
    draft_balance: "Draft Balance",
    draft_balance_aria: "Draft Balance",
    draft_balance_help: "Paper balance only. Not real exchange funds.",
    paper_portfolio_loading: "Loading paper portfolio…",
    paper_portfolio_unavailable: "Paper portfolio unavailable",
    paper_portfolio_empty: "No paper account activity yet.",
    paper_portfolio_no_open_positions: "No open positions.",
    starting_balance_label: "Starting balance",
    positions_value_label: "Positions value",
    total_equity_label: "Total equity",
    open_positions_label: "Open positions",
    average_entry_label: "Average entry",
    market_value_label: "Market value",
    unrealized_pnl_percent_label: "Unrealized %",
    price_unavailable: "Price unavailable",
    recent_paper_orders: "Recent Paper Orders",
    recent_paper_orders_aria: "Recent Paper Orders",
    recent_paper_orders_help: "Read-only paper execution audit for the selected bot.",
    recent_paper_orders_loading: "Loading recent paper orders…",
    recent_paper_orders_unavailable: "Recent paper orders unavailable",
    recent_paper_orders_select_bot: "Select a bot to view recent paper orders.",
    recent_paper_orders_empty: "No recent paper orders for this bot.",
    order_side_buy: "Buy",
    order_side_sell: "Sell",
    order_status_created: "Created",
    order_status_submitted: "Submitted",
    order_status_filled: "Filled",
    order_status_rejected: "Rejected",
    order_status_cancelled: "Cancelled",
    order_status_blocked: "Blocked",
    order_status_pending: "Pending",
    order_status_unknown: "Unknown",
    order_quantity_label: "Quantity",
    order_filled_quantity_label: "Filled qty",
    order_fill_count_label: "Fills",
    order_price_label: "Price",
    order_reason_label: "Reason",
    order_created_time_label: "Created",
    order_mode_label: "Mode",
    order_type_label: "Order type",
    order_strategy_label: "Strategy",
    execution_safety: "Execution Safety",
    execution_safety_aria: "Execution Safety",
    execution_safety_help: "Read-only execution safety state for the selected bot.",
    execution_safety_loading: "Loading execution safety…",
    execution_safety_unavailable: "Execution safety unavailable",
    execution_safety_select_bot: "Select a bot to view execution safety.",
    execution_safety_allowed: "Allowed",
    execution_safety_blocked: "Blocked",
    execution_safety_enabled: "Enabled",
    execution_safety_disabled: "Disabled",
    execution_safety_configured: "Configured",
    execution_safety_not_configured: "Not configured",
    execution_safety_reason_label: "Reason",
    execution_safety_metadata_label: "Details",
    execution_safety_utc_day_start_label: "UTC day start",
    reconciliation_worker: "Reconciliation Worker",
    reconciliation_worker_aria: "Reconciliation Worker",
    reconciliation_worker_help: "Read-only delayed reconciliation worker status.",
    reconciliation_worker_loading: "Loading reconciliation worker…",
    reconciliation_worker_unavailable: "Reconciliation worker status unavailable",
    reconciliation_worker_not_started: "Never started",
    reconciliation_worker_disabled_summary: "Configured disabled. No automatic worker is expected.",
    reconciliation_worker_recent_summary: "Running with a recent heartbeat.",
    reconciliation_worker_stale_summary: "Running with a stale heartbeat.",
    reconciliation_worker_stopped_summary: "Stopped.",
    reconciliation_worker_unknown_summary: "Worker state unknown.",
    reconciliation_worker_configured_label: "Configured",
    reconciliation_worker_initialized_label: "Initialized",
    reconciliation_worker_state_label: "State",
    reconciliation_worker_heartbeat_label: "Heartbeat",
    reconciliation_worker_stale_threshold_label: "Stale threshold",
    reconciliation_worker_last_started_label: "Last started",
    reconciliation_worker_last_heartbeat_label: "Last heartbeat",
    reconciliation_worker_last_stopped_label: "Last stopped",
    reconciliation_worker_last_cycle_finished_label: "Last cycle finished",
    reconciliation_worker_last_result_label: "Last result",
    reconciliation_worker_last_job_label: "Last job",
    reconciliation_worker_updated_label: "Updated",
    reconciliation_worker_recent_heartbeat: "Recent",
    reconciliation_worker_stale_heartbeat: "Stale",
    reconciliation_worker_not_available: "—",
    reconciliation_worker_initialized: "Initialized",
    reconciliation_worker_never_started: "Never started",
    reconciliation_worker_seconds: "{seconds}s",
    recent_reconciliation_jobs: "Recent Reconciliation Jobs",
    recent_reconciliation_jobs_aria: "Recent Reconciliation Jobs",
    recent_reconciliation_jobs_help: "Read-only durable reconciliation job audit.",
    recent_reconciliation_jobs_loading: "Loading reconciliation jobs…",
    recent_reconciliation_jobs_unavailable: "Reconciliation jobs unavailable",
    recent_reconciliation_jobs_empty: "No reconciliation jobs found.",
    reconciliation_job_status_pending: "Pending",
    reconciliation_job_status_claimed: "Claimed",
    reconciliation_job_status_resolved: "Resolved",
    reconciliation_job_status_exhausted: "Exhausted",
    reconciliation_job_status_unknown: "Unknown",
    reconciliation_job_id_label: "Job",
    reconciliation_job_execution_attempt_label: "Execution attempt",
    reconciliation_job_bot_label: "Bot",
    reconciliation_job_attempt_count_label: "Attempts",
    reconciliation_job_claimed_label: "Claimed",
    reconciliation_job_created_label: "Created",
    reconciliation_job_exhausted_label: "Exhausted",
    reconciliation_job_max_attempts_label: "Max attempts",
    reconciliation_job_next_attempt_label: "Next attempt",
    reconciliation_job_result_label: "Result",
    reconciliation_job_failure_label: "Failure",
    reconciliation_job_resolved_label: "Resolved",
    reconciliation_job_updated_label: "Updated",
    global_execution_enabled_label: "Global execution",
    paper_execution_enabled_label: "Paper execution",
    live_execution_enabled_label: "Live execution",
    binance_testnet_enabled_label: "Binance testnet",
    binance_order_submission_enabled_label: "Binance order submission",
    binance_credentials_configured_label: "Binance credentials",
    max_order_notional_label: "Max order notional",
    max_daily_order_count_label: "Max daily orders",
    current_daily_accepted_order_count_label: "Accepted today",
    remaining_daily_capacity_label: "Remaining capacity",
    max_daily_loss_label: "Max daily loss",
    current_daily_realized_loss_label: "Current daily loss",
    health_label: "Health",
    latest_price_label: "Latest price",
    last_decision_label: "Last decision",
    last_event_time_label: "Last event",
    total_event_count_label: "Total events",
    buy_signal_count_label: "Buy signals",
    sell_signal_count_label: "Sell signals",
    hold_signal_count_label: "Hold signals",
    risk_blocked_count_label: "Risk blocked",
    order_filled_count_label: "Orders filled",
    health_healthy: "Healthy",
    health_inactive: "Inactive",
    health_no_activity: "No activity",
    health_unknown: "Unknown",
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
    price_threshold_label: "Price Threshold",
    moving_average_cross_label: "Moving Average Cross",
    rsi_threshold_label: "RSI Threshold",
    bollinger_bands_label: "Bollinger Bands",
    macd_crossover_label: "MACD Crossover",
    period_label: "Period",
    stddev_multiplier_label: "Stddev multiplier",
    fast_period_label: "Fast period",
    slow_period_label: "Slow period",
    signal_period_label: "Signal period",
    oversold_label: "Oversold",
    overbought_label: "Overbought",
    no_strategy_selected: "No strategy selected",
    no_strategy_parameters_configured: "No strategy parameters configured",
    strategy_details_unavailable: "Strategy details unavailable",
    edit_strategy_parameters: "Edit",
    edit_strategy_parameters_aria: "Edit strategy parameters",
    save: "Save",
    save_strategy: "Save strategy",
    strategy_name_form_label: "Strategy name",
    create_strategy_aria: "Create strategy",
    create_strategy_hint_name: "Bollinger BTC 1m",
    create_strategy_success:
      "Created {name}. It is now available for Bot assignment and backtesting.",
    create_strategy_failed: "Could not create Strategy.",
    creating_strategy: "Saving…",
    select_strategy_type: "Select a strategy type.",
    enter_strategy_name: "Enter a Strategy name.",
    enter_strategy_symbol: "Enter a symbol.",
    enter_strategy_timeframe: "Enter a timeframe.",
    check_strategy_fields: "Check the Strategy form fields and try again.",
    strategy_parameters_updated: "Strategy parameters updated.",
    strategy_parameters_save_failed: "Could not update Strategy parameters.",
    enter_strategy_parameters: "Enter buy below, sell above, and quantity.",
    enter_moving_average_parameters: "Enter short window and long window.",
    enter_rsi_parameters: "Enter period, oversold, overbought, and quantity.",
    enter_bollinger_parameters: "Enter period, stddev multiplier, and quantity.",
    enter_macd_parameters: "Enter fast period, slow period, signal period, and quantity.",
    strategy_parameters_must_be_numbers: "Strategy parameters must be positive numbers.",
    sell_above_must_exceed_buy_below: "Sell above must be greater than buy below.",
    moving_average_windows_must_be_integers: "Short window and long window must be positive integers.",
    moving_average_short_less_than_long: "Short window must be smaller than long window.",
    bollinger_period_must_be_at_least_two: "Bollinger period must be an integer of 2 or more.",
    bollinger_parameters_must_be_positive: "Bollinger stddev multiplier and quantity must be positive.",
    macd_periods_must_be_integers: "MACD periods must be positive integers.",
    macd_fast_less_than_slow: "Fast period must be less than slow period.",
    macd_quantity_must_be_positive: "MACD quantity must be positive.",
    rsi_period_must_be_integer: "RSI period must be a positive integer.",
    rsi_thresholds_must_be_numbers: "RSI thresholds must be numbers greater than 0 and less than 100.",
    rsi_oversold_less_than_overbought: "Oversold must be less than overbought.",
    rsi_quantity_must_be_positive: "RSI quantity must be positive.",
    moving_average_parameters_help:
      "Short window must be smaller than long window. Both windows must be positive integers.",
    price_threshold_parameters_help:
      "Buy below is the entry trigger, sell above is the exit trigger, and quantity is the simulated trade amount.",
    rsi_threshold_parameters_help:
      "RSI Threshold buys near the oversold level and sells near the overbought level.",
    bollinger_bands_parameters_help:
      "Bollinger Bands buys near the lower band and sells near the upper band.",
    macd_crossover_parameters_help:
      "MACD Crossover buys on bullish MACD/signal crossover and sells on bearish crossover.",
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
    live_market: "Live Market",
    live_market_aria: "Live Market",
    live_market_help:
      "Track public Binance prices locally. Simulated dashboard only; no orders are placed.",
    live_market_add_symbol_aria: "Add market symbol",
    live_market_symbol_label: "Symbol",
    live_market_add_symbol: "Add symbol",
    live_market_refresh: "Refresh market",
    live_market_refreshing: "Refreshing…",
    live_market_auto_refresh: "Auto-refresh",
    live_market_empty: "No market symbols tracked yet.",
    live_market_empty_hint: "Add a Binance symbol such as BTCUSDT.",
    live_market_symbol_required: "Enter a symbol to watch.",
    live_market_duplicate_symbol: "{symbol} is already in the watchlist.",
    live_market_added_symbol: "Added {symbol} to Live Market.",
    live_market_removed_symbol: "Removed {symbol}.",
    live_market_price_error: "Could not load Binance price.",
    live_market_latest_price: "Latest price",
    live_market_previous_price: "Previous price",
    live_market_absolute_change: "Change",
    live_market_percent_change: "Change %",
    live_market_direction: "Direction",
    live_market_last_updated: "Last updated",
    live_market_loading: "Loading price…",
    live_market_direction_up: "Up",
    live_market_direction_down: "Down",
    live_market_direction_flat: "Flat",
    live_market_remove_symbol: "Remove {symbol}",
    live_market_chart: "Chart",
    live_market_chart_aria: "Open candle chart for {symbol}",
    candle_modal_eyebrow: "Live Market",
    candle_modal_title: "{symbol} candles",
    candle_timeframe_label: "Timeframe",
    candle_limit_label: "Candles",
    candle_date_label: "Date",
    candle_latest_candles: "Latest candles",
    candle_refresh: "Refresh candles",
    candle_refreshing: "Loading…",
    candle_loading: "Loading candles…",
    candle_empty: "No candle data returned for this symbol.",
    candle_error: "Could not load Binance candles.",
    candle_chart_help: "Wheel to zoom. Drag or Shift+wheel to move through time.",
    candle_load_older: "Load older",
    candle_loading_older: "Loading older candles…",
    candle_no_older_loaded: "No older candles loaded.",
    candle_older_loaded: "Loaded {count} older candles.",
    candle_older_error: "Could not load older candles.",
    candle_window_previous: "Previous",
    candle_window_next: "Next",
    candle_window_reset: "Reset zoom",
    candle_open_label: "Open",
    candle_high_label: "High",
    candle_low_label: "Low",
    candle_close_label: "Close",
    candle_volume_label: "Volume",
    candle_time_label: "Candle time",
    candle_chart_label: "Candlestick chart",
    candle_range_high_label: "Range high",
    candle_range_low_label: "Range low",
    candle_first_open_label: "First open",
    candle_last_close_label: "Last close",
    candle_net_change_label: "Net change",
    candle_net_change_percent_label: "Net change %",
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
    optimization_rsi_thresholds_invalid:
      "RSI optimization values need positive integer periods, thresholds between 0 and 100, and oversold below overbought.",
    optimization_bollinger_invalid:
      "Bollinger optimization values need periods of 2 or more, positive stddev multipliers, and positive quantities.",
    optimization_macd_invalid:
      "MACD optimization values need positive integer periods, fast period below slow period, and positive quantities.",
    optimization_unsupported_strategy: "Optimization is not available for this strategy type yet.",
    optimization_price_help: "Comma-separated buy/sell thresholds generate every combination with the quantity.",
    optimization_ma_help: "Comma-separated short/long windows generate every combination with the quantity.",
    optimization_rsi_help:
      "Comma-separated RSI periods, oversold levels, overbought levels, and quantities generate every valid combination.",
    optimization_bollinger_help:
      "Comma-separated periods, stddev multipliers, and quantities generate every valid Bollinger combination.",
    optimization_macd_help:
      "Comma-separated MACD fast, slow, signal periods, and quantities generate every valid combination.",
    optimization_presets_title: "Optimization presets",
    optimization_presets_help:
      "Use presets as starting points, then review results before applying. Quality filters help identify more reliable combinations.",
    optimization_preset_conservative_range: "Conservative range",
    optimization_preset_balanced_range: "Balanced range",
    optimization_preset_wider_range: "Wider range",
    optimization_preset_fast_signals: "Fast signals",
    optimization_preset_balanced_windows: "Balanced windows",
    optimization_preset_slower_signals: "Slower signals",
    optimization_preset_standard_rsi: "Standard RSI",
    optimization_preset_sensitive_rsi: "Sensitive RSI",
    optimization_preset_conservative_rsi: "Conservative RSI",
    optimization_preset_standard_bands: "Standard Bands",
    optimization_preset_tight_bands: "Tight Bands",
    optimization_preset_wide_bands: "Wide Bands",
    optimization_preset_standard_macd: "Standard MACD",
    optimization_preset_fast_macd: "Fast MACD",
    optimization_preset_slow_macd: "Slow MACD",
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
    period_values_label: "Period values",
    stddev_multiplier_values_label: "Stddev multiplier values",
    fast_period_values_label: "Fast period values",
    slow_period_values_label: "Slow period values",
    signal_period_values_label: "Signal period values",
    oversold_values_label: "Oversold values",
    overbought_values_label: "Overbought values",
    quantity_values_label: "Quantity values",
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
    backtest_history_scope_aria: "Recent Backtests scope",
    backtest_history_scope_selected: "Selected strategy",
    backtest_history_scope_all: "All recent runs",
    backtest_history_scope_selected_help: "Showing runs for the selected strategy.",
    backtest_history_scope_all_help: "Showing all loaded recent runs.",
    view_details: "View details",
    hide_details: "Hide details",
    backtest_details: "Backtest details",
    visible_runs_label: "Visible runs",
    best_visible_return_label: "Best return",
    average_return_label: "Average return",
    profitable_runs_label: "Profitable runs",
    with_closed_trades_label: "With closed trades",
    backtest_strategy_fallback: "Strategy #{id}",
    winning_losing_trades_label: "Wins / losses",
    best_recent_run: "Best recent run",
    best_recent_run_help: "Based on recent saved backtests for this strategy.",
    run_more_backtests_to_compare: "Run more backtests to compare recent results.",
    strategy_performance_comparison: "Strategy Performance Comparison",
    strategy_performance_comparison_aria: "Strategy Performance Comparison",
    strategy_performance_comparison_help:
      "Compares strategies using the limited recent backtests currently loaded, not all-time performance.",
    loading_strategy_comparison: "Loading strategy comparison...",
    loading_strategy_comparison_hint: "Recent backtest history is being prepared for comparison.",
    strategy_comparison_error: "Could not load strategy comparison.",
    strategy_comparison_error_hint: "Recent backtest history is unavailable right now. Try refreshing.",
    no_strategy_comparison: "No strategy comparison yet.",
    no_strategy_comparison_hint: "Run backtests for different strategies to compare recent performance.",
    no_comparable_strategy_runs: "No comparable strategy runs found.",
    no_comparable_strategy_runs_hint:
      "Recent backtests are missing strategy IDs, so they cannot be compared safely.",
    best_return_label: "Best return",
    latest_return_label: "Latest return",
    recent_runs_label: "Recent runs",
    last_backtest_label: "Last backtest",
    selected_bot_strategy_label: "Selected bot strategy",
    best_performer_badge: "Best performer",
    needs_more_runs_badge: "Needs more runs",
    no_closed_trades_badge: "No closed trades",
    view_latest_run: "View latest run",
    latest_run_not_visible: "Latest run not visible",
    latest_run_not_visible_hint: "Latest run is not visible in the current recent list.",
    use_for_new_backtest: "Use for new backtest",
    strategy_not_available_for_backtest: "Strategy is not available in the backtest form.",
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
    create_strategy: "Ստեղծել Strategy",
    strategies_heading: "Strategy-ներ",
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
    bot_performance: "Bot-ի արդյունավետություն",
    bot_performance_aria: "Bot-ի արդյունավետություն",
    bot_performance_unavailable: "Արդյունավետությունը հասանելի չէ",
    bot_performance_loading: "Արդյունավետությունը բեռնվում է…",
    bot_performance_select_bot: "Ընտրիր Bot՝ արդյունավետությունը դիտելու համար։",
    bot_performance_no_activity: "Activity դեռ չի գրանցվել։",
    draft_balance: "Փորձնական հաշվեկշիռ",
    draft_balance_aria: "Փորձնական հաշվեկշիռ",
    draft_balance_help: "Միայն paper հաշվեկշիռ է։ Իրական բորսայի միջոցներ չեն։",
    paper_portfolio_loading: "Paper պորտֆելը բեռնվում է…",
    paper_portfolio_unavailable: "Paper պորտֆելը հասանելի չէ",
    paper_portfolio_empty: "Paper հաշվում activity դեռ չկա։",
    paper_portfolio_no_open_positions: "Բաց position-ներ չկան։",
    starting_balance_label: "Սկզբնական հաշվեկշիռ",
    positions_value_label: "Position-ների արժեք",
    total_equity_label: "Ընդհանուր equity",
    open_positions_label: "Բաց position-ներ",
    average_entry_label: "Միջին մուտք",
    market_value_label: "Շուկայական արժեք",
    unrealized_pnl_percent_label: "Չիրացված %",
    price_unavailable: "Գինը հասանելի չէ",
    recent_paper_orders: "Վերջին փորձնական պատվերներ",
    recent_paper_orders_aria: "Վերջին փորձնական պատվերներ",
    recent_paper_orders_help: "Ընտրված Bot-ի paper execution audit-ը՝ միայն դիտելու համար։",
    recent_paper_orders_loading: "Վերջին paper պատվերները բեռնվում են…",
    recent_paper_orders_unavailable: "Վերջին paper պատվերները հասանելի չեն",
    recent_paper_orders_select_bot: "Ընտրիր Bot՝ վերջին paper պատվերները դիտելու համար։",
    recent_paper_orders_empty: "Այս Bot-ի համար վերջին paper պատվերներ չկան։",
    order_side_buy: "Գնում",
    order_side_sell: "Վաճառք",
    order_status_created: "Ստեղծված",
    order_status_submitted: "Ուղարկված",
    order_status_filled: "Լրացված",
    order_status_rejected: "Մերժված",
    order_status_cancelled: "Չեղարկված",
    order_status_blocked: "Արգելված",
    order_status_pending: "Սպասող",
    order_status_unknown: "Անհայտ",
    order_quantity_label: "Քանակ",
    order_filled_quantity_label: "Լրացված քանակ",
    order_fill_count_label: "Fill-եր",
    order_price_label: "Գին",
    order_reason_label: "Պատճառ",
    order_created_time_label: "Ստեղծվել է",
    order_mode_label: "Ռեժիմ",
    order_type_label: "Order-ի տեսակ",
    order_strategy_label: "Strategy",
    execution_safety: "Կատարման անվտանգություն",
    execution_safety_aria: "Կատարման անվտանգություն",
    execution_safety_help: "Ընտրված Bot-ի կատարման անվտանգության վիճակը՝ միայն դիտելու համար։",
    execution_safety_loading: "Կատարման անվտանգությունը բեռնվում է…",
    execution_safety_unavailable: "Կատարման անվտանգությունը հասանելի չէ",
    execution_safety_select_bot: "Ընտրիր Bot՝ կատարման անվտանգությունը դիտելու համար։",
    execution_safety_allowed: "Թույլատրված",
    execution_safety_blocked: "Արգելված",
    execution_safety_enabled: "Միացված",
    execution_safety_disabled: "Անջատված",
    execution_safety_configured: "Կարգավորված",
    execution_safety_not_configured: "Կարգավորված չէ",
    execution_safety_reason_label: "Պատճառ",
    execution_safety_metadata_label: "Մանրամասներ",
    execution_safety_utc_day_start_label: "UTC օրվա սկիզբ",
    reconciliation_worker: "Համադրման worker",
    reconciliation_worker_aria: "Համադրման worker",
    reconciliation_worker_help: "Delayed reconciliation worker-ի վիճակը՝ միայն դիտելու համար։",
    reconciliation_worker_loading: "Համադրման worker-ը բեռնվում է…",
    reconciliation_worker_unavailable: "Համադրման worker-ի վիճակը հասանելի չէ",
    reconciliation_worker_not_started: "Երբեք չի մեկնարկել",
    reconciliation_worker_disabled_summary: "Կարգավորված է անջատված։ Ավտոմատ worker չի սպասվում։",
    reconciliation_worker_recent_summary: "Աշխատում է՝ վերջին heartbeat-ով։",
    reconciliation_worker_stale_summary: "Աշխատում է՝ հնացած heartbeat-ով։",
    reconciliation_worker_stopped_summary: "Կանգնեցված է։",
    reconciliation_worker_unknown_summary: "Worker-ի վիճակը անհայտ է։",
    reconciliation_worker_configured_label: "Կարգավորում",
    reconciliation_worker_initialized_label: "Սկզբնավորված",
    reconciliation_worker_state_label: "Վիճակ",
    reconciliation_worker_heartbeat_label: "Heartbeat",
    reconciliation_worker_stale_threshold_label: "Հնանալու շեմ",
    reconciliation_worker_last_started_label: "Վերջին մեկնարկ",
    reconciliation_worker_last_heartbeat_label: "Վերջին heartbeat",
    reconciliation_worker_last_stopped_label: "Վերջին կանգ",
    reconciliation_worker_last_cycle_finished_label: "Վերջին ցիկլի ավարտ",
    reconciliation_worker_last_result_label: "Վերջին արդյունք",
    reconciliation_worker_last_job_label: "Վերջին job",
    reconciliation_worker_updated_label: "Թարմացվել է",
    reconciliation_worker_recent_heartbeat: "Վերջին",
    reconciliation_worker_stale_heartbeat: "Հնացած",
    reconciliation_worker_not_available: "—",
    reconciliation_worker_initialized: "Սկզբնավորված",
    reconciliation_worker_never_started: "Երբեք չի մեկնարկել",
    reconciliation_worker_seconds: "{seconds}վ",
    recent_reconciliation_jobs: "Վերջին համադրման job-երը",
    recent_reconciliation_jobs_aria: "Վերջին համադրման job-երը",
    recent_reconciliation_jobs_help: "Durable reconciliation job-երի audit-ը՝ միայն դիտելու համար։",
    recent_reconciliation_jobs_loading: "Համադրման job-երը բեռնվում են…",
    recent_reconciliation_jobs_unavailable: "Համադրման job-երը հասանելի չեն",
    recent_reconciliation_jobs_empty: "Համադրման job-եր չկան։",
    reconciliation_job_status_pending: "Սպասում է",
    reconciliation_job_status_claimed: "Claimed",
    reconciliation_job_status_resolved: "Լուծված",
    reconciliation_job_status_exhausted: "Սպառված",
    reconciliation_job_status_unknown: "Անհայտ",
    reconciliation_job_id_label: "Job",
    reconciliation_job_execution_attempt_label: "Execution attempt",
    reconciliation_job_bot_label: "Bot",
    reconciliation_job_attempt_count_label: "Փորձեր",
    reconciliation_job_claimed_label: "Claimed",
    reconciliation_job_created_label: "Ստեղծվել է",
    reconciliation_job_exhausted_label: "Սպառվել է",
    reconciliation_job_max_attempts_label: "Առավելագույն փորձեր",
    reconciliation_job_next_attempt_label: "Հաջորդ փորձ",
    reconciliation_job_result_label: "Արդյունք",
    reconciliation_job_failure_label: "Խափանում",
    reconciliation_job_resolved_label: "Լուծվել է",
    reconciliation_job_updated_label: "Թարմացվել է",
    global_execution_enabled_label: "Ընդհանուր կատարում",
    paper_execution_enabled_label: "Paper կատարում",
    live_execution_enabled_label: "Live կատարում",
    binance_testnet_enabled_label: "Binance testnet",
    binance_order_submission_enabled_label: "Binance order ուղարկում",
    binance_credentials_configured_label: "Binance credentials",
    max_order_notional_label: "Առավելագույն order notional",
    max_daily_order_count_label: "Օրվա առավելագույն order-ներ",
    current_daily_accepted_order_count_label: "Այսօր ընդունված",
    remaining_daily_capacity_label: "Մնացած կարողություն",
    max_daily_loss_label: "Օրվա առավելագույն կորուստ",
    current_daily_realized_loss_label: "Օրվա ընթացիկ կորուստ",
    health_label: "Առողջություն",
    latest_price_label: "Վերջին գին",
    last_decision_label: "Վերջին որոշում",
    last_event_time_label: "Վերջին իրադարձություն",
    total_event_count_label: "Իրադարձություններ",
    buy_signal_count_label: "Գնման signal-ներ",
    sell_signal_count_label: "Վաճառքի signal-ներ",
    hold_signal_count_label: "Hold signal-ներ",
    risk_blocked_count_label: "Risk-ով արգելված",
    order_filled_count_label: "Լրացված order-ներ",
    health_healthy: "Առողջ",
    health_inactive: "Ակտիվ չէ",
    health_no_activity: "Activity չկա",
    health_unknown: "Անհայտ",
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
    price_threshold_label: "Գնի շեմ",
    moving_average_cross_label: "Moving Average հատում",
    rsi_threshold_label: "RSI Threshold",
    bollinger_bands_label: "Bollinger Bands",
    macd_crossover_label: "MACD Crossover",
    period_label: "Պարբերություն",
    stddev_multiplier_label: "Stddev բազմապատկիչ",
    fast_period_label: "Արագ period",
    slow_period_label: "Դանդաղ period",
    signal_period_label: "Signal period",
    oversold_label: "Oversold շեմ",
    overbought_label: "Overbought շեմ",
    no_strategy_selected: "Strategy ընտրված չէ",
    no_strategy_parameters_configured: "Strategy-ի parameters-ները կարգավորված չեն",
    strategy_details_unavailable: "Strategy-ի մանրամասները հասանելի չեն",
    edit_strategy_parameters: "Խմբագրել",
    edit_strategy_parameters_aria: "Խմբագրել Strategy-ի parameters-ները",
    save: "Պահպանել",
    save_strategy: "Պահպանել Strategy-ն",
    strategy_name_form_label: "Strategy-ի անուն",
    create_strategy_aria: "Ստեղծել Strategy",
    create_strategy_hint_name: "Bollinger BTC 1m",
    create_strategy_success:
      "Ստեղծվեց {name}։ Այն հասանելի է Bot-ին կցելու և backtest-ի համար։",
    create_strategy_failed: "Չհաջողվեց ստեղծել Strategy։",
    creating_strategy: "Պահպանվում է…",
    select_strategy_type: "Ընտրիր strategy type։",
    enter_strategy_name: "Մուտքագրիր Strategy-ի անունը։",
    enter_strategy_symbol: "Մուտքագրիր symbol։",
    enter_strategy_timeframe: "Մուտքագրիր timeframe։",
    check_strategy_fields: "Ստուգիր Strategy-ի ձևի դաշտերը և նորից փորձիր։",
    strategy_parameters_updated: "Strategy-ի parameters-ները թարմացվեցին։",
    strategy_parameters_save_failed: "Չհաջողվեց թարմացնել Strategy-ի parameters-ները։",
    enter_strategy_parameters: "Մուտքագրիր buy below, sell above և quantity արժեքները։",
    enter_moving_average_parameters: "Մուտքագրիր short window և long window արժեքները։",
    enter_rsi_parameters: "Մուտքագրիր period, oversold, overbought և quantity արժեքները։",
    enter_bollinger_parameters: "Մուտքագրիր period, stddev multiplier և quantity արժեքները։",
    enter_macd_parameters: "Մուտքագրիր fast period, slow period, signal period և quantity արժեքները։",
    strategy_parameters_must_be_numbers: "Strategy-ի parameters-ները պետք է լինեն դրական թվեր։",
    sell_above_must_exceed_buy_below: "Sell above-ը պետք է մեծ լինի buy below-ից։",
    moving_average_windows_must_be_integers: "Short window-ը և long window-ը պետք է լինեն դրական ամբողջ թվեր։",
    moving_average_short_less_than_long: "Short window-ը պետք է փոքր լինի long window-ից։",
    bollinger_period_must_be_at_least_two: "Bollinger period-ը պետք է լինի 2 կամ մեծ ամբողջ թիվ։",
    bollinger_parameters_must_be_positive: "Bollinger stddev multiplier-ը և quantity-ն պետք է լինեն դրական։",
    macd_periods_must_be_integers: "MACD period-ները պետք է լինեն դրական ամբողջ թվեր։",
    macd_fast_less_than_slow: "Fast period-ը պետք է փոքր լինի slow period-ից։",
    macd_quantity_must_be_positive: "MACD quantity-ն պետք է լինի դրական։",
    rsi_period_must_be_integer: "RSI period-ը պետք է լինի դրական ամբողջ թիվ։",
    rsi_thresholds_must_be_numbers: "RSI շեմերը պետք է լինեն 0-ից մեծ և 100-ից փոքր թվեր։",
    rsi_oversold_less_than_overbought: "Oversold-ը պետք է փոքր լինի overbought-ից։",
    rsi_quantity_must_be_positive: "RSI quantity-ն պետք է լինի դրական։",
    moving_average_parameters_help:
      "Short window-ը պետք է փոքր լինի long window-ից։ Երկու window-ներն էլ պետք է դրական ամբողջ թվեր լինեն։",
    price_threshold_parameters_help:
      "Buy below-ը մուտքի trigger-ն է, sell above-ը՝ ելքի trigger-ը, իսկ quantity-ն՝ simulated գործարքի քանակը։",
    rsi_threshold_parameters_help:
      "RSI Threshold-ը գնում է oversold շեմի մոտ և վաճառում է overbought շեմի մոտ։",
    bollinger_bands_parameters_help:
      "Bollinger Bands-ը գնում է ստորին band-ի մոտ և վաճառում է վերին band-ի մոտ։",
    macd_crossover_parameters_help:
      "MACD Crossover-ը գնում է bullish MACD/signal հատման ժամանակ և վաճառում է bearish հատման ժամանակ։",
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
    live_market: "Live Market",
    live_market_aria: "Live Market",
    live_market_help:
      "Հետևիր Binance-ի public գներին տեղային watchlist-ով։ Սա միայն simulation dashboard է․ order-ներ չեն տեղադրվում։",
    live_market_add_symbol_aria: "Ավելացնել market symbol",
    live_market_symbol_label: "Symbol",
    live_market_add_symbol: "Ավելացնել symbol",
    live_market_refresh: "Թարմացնել market-ը",
    live_market_refreshing: "Թարմացվում է…",
    live_market_auto_refresh: "Auto-refresh",
    live_market_empty: "Market symbol-ներ դեռ չեն հետևվում։",
    live_market_empty_hint: "Ավելացրու Binance symbol, օրինակ՝ BTCUSDT։",
    live_market_symbol_required: "Մուտքագրիր symbol՝ հետևելու համար։",
    live_market_duplicate_symbol: "{symbol}-ն արդեն watchlist-ում է։",
    live_market_added_symbol: "{symbol}-ը ավելացվեց Live Market-ում։",
    live_market_removed_symbol: "{symbol}-ը հեռացվեց։",
    live_market_price_error: "Չհաջողվեց բեռնել Binance գինը։",
    live_market_latest_price: "Վերջին գին",
    live_market_previous_price: "Նախորդ գին",
    live_market_absolute_change: "Փոփոխություն",
    live_market_percent_change: "Փոփոխություն %",
    live_market_direction: "Ուղղություն",
    live_market_last_updated: "Վերջին թարմացում",
    live_market_loading: "Գինը բեռնվում է…",
    live_market_direction_up: "Վերև",
    live_market_direction_down: "Ներքև",
    live_market_direction_flat: "Կայուն",
    live_market_remove_symbol: "Հեռացնել {symbol}",
    live_market_chart: "Գրաֆիկ",
    live_market_chart_aria: "Բացել {symbol}-ի candle գրաֆիկը",
    candle_modal_eyebrow: "Live Market",
    candle_modal_title: "{symbol} candle-ներ",
    candle_timeframe_label: "Timeframe",
    candle_limit_label: "Candle-ներ",
    candle_date_label: "Date",
    candle_latest_candles: "Latest candles",
    candle_refresh: "Թարմացնել candle-ները",
    candle_refreshing: "Բեռնվում է…",
    candle_loading: "Candle-ները բեռնվում են…",
    candle_empty: "Այս symbol-ի համար candle տվյալներ չվերադարձան։",
    candle_error: "Չհաջողվեց բեռնել Binance candle-ները։",
    candle_chart_help: "Wheel to zoom. Drag or Shift+wheel to move through time.",
    candle_load_older: "Բեռնել հները",
    candle_loading_older: "Հին candle-ները բեռնվում են…",
    candle_no_older_loaded: "Հին candle-ներ չբեռնվեցին։",
    candle_older_loaded: "Բեռնվեց {count} հին candle։",
    candle_older_error: "Չհաջողվեց բեռնել հին candle-ները։",
    candle_window_previous: "Previous",
    candle_window_next: "Next",
    candle_window_reset: "Reset zoom",
    candle_open_label: "Open",
    candle_high_label: "High",
    candle_low_label: "Low",
    candle_close_label: "Close",
    candle_volume_label: "Volume",
    candle_time_label: "Candle-ի ժամանակ",
    candle_chart_label: "Candlestick chart",
    candle_range_high_label: "Range high",
    candle_range_low_label: "Range low",
    candle_first_open_label: "First open",
    candle_last_close_label: "Last close",
    candle_net_change_label: "Net change",
    candle_net_change_percent_label: "Net change %",
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
    optimization_rsi_thresholds_invalid:
      "RSI optimization-ի արժեքներին պետք են դրական ամբողջ period-ներ, 0-ից 100 շեմեր և oversold-ը պետք է փոքր լինի overbought-ից։",
    optimization_bollinger_invalid:
      "Bollinger optimization-ի արժեքներին պետք են 2 կամ մեծ period-ներ, դրական stddev multiplier-ներ և դրական quantity-ներ։",
    optimization_macd_invalid:
      "MACD optimization-ի արժեքներին պետք են դրական ամբողջ period-ներ, fast period-ը slow period-ից փոքր և դրական quantity-ներ։",
    optimization_unsupported_strategy: "Այս strategy type-ի համար optimization-ը դեռ հասանելի չէ։",
    optimization_price_help: "Ստորակետերով buy/sell շեմերը quantity-ի հետ ստեղծում են բոլոր combination-ները։",
    optimization_ma_help: "Ստորակետերով short/long window-ները quantity-ի հետ ստեղծում են բոլոր combination-ները։",
    optimization_rsi_help:
      "Ստորակետերով RSI period-ները, oversold շեմերը, overbought շեմերը և quantity-ները ստեղծում են բոլոր valid combination-ները։",
    optimization_bollinger_help:
      "Ստորակետերով period-ները, stddev multiplier-ները և quantity-ները ստեղծում են Bollinger-ի բոլոր valid combination-ները։",
    optimization_macd_help:
      "Ստորակետերով MACD fast, slow, signal period-ները և quantity-ները ստեղծում են բոլոր valid combination-ները։",
    optimization_presets_title: "Optimization preset-ներ",
    optimization_presets_help:
      "Preset-ները օգտագործիր որպես մեկնարկային կետ, հետո արդյունքները վերանայիր մինչև կիրառելը։ Որակի ֆիլտրերը օգնում են գտնել ավելի հուսալի combination-ներ։",
    optimization_preset_conservative_range: "Զուսպ միջակայք",
    optimization_preset_balanced_range: "Հավասարակշռված միջակայք",
    optimization_preset_wider_range: "Ավելի լայն միջակայք",
    optimization_preset_fast_signals: "Արագ signal-ներ",
    optimization_preset_balanced_windows: "Հավասարակշռված window-ներ",
    optimization_preset_slower_signals: "Ավելի դանդաղ signal-ներ",
    optimization_preset_standard_rsi: "Ստանդարտ RSI",
    optimization_preset_sensitive_rsi: "Զգայուն RSI",
    optimization_preset_conservative_rsi: "Զուսպ RSI",
    optimization_preset_standard_bands: "Ստանդարտ bands",
    optimization_preset_tight_bands: "Նեղ bands",
    optimization_preset_wide_bands: "Լայն bands",
    optimization_preset_standard_macd: "Ստանդարտ MACD",
    optimization_preset_fast_macd: "Արագ MACD",
    optimization_preset_slow_macd: "Դանդաղ MACD",
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
    period_values_label: "Period արժեքներ",
    stddev_multiplier_values_label: "Stddev multiplier արժեքներ",
    fast_period_values_label: "Fast period արժեքներ",
    slow_period_values_label: "Slow period արժեքներ",
    signal_period_values_label: "Signal period արժեքներ",
    oversold_values_label: "Oversold արժեքներ",
    overbought_values_label: "Overbought արժեքներ",
    quantity_values_label: "Quantity արժեքներ",
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
    cash_balance_label: "Կանխիկ հաշվեկշիռ",
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
    backtest_history_scope_aria: "Վերջին Backtest-երի scope",
    backtest_history_scope_selected: "Ընտրված strategy",
    backtest_history_scope_all: "Բոլոր վերջին run-երը",
    backtest_history_scope_selected_help: "Ցուցադրվում են ընտրված strategy-ի run-երը։",
    backtest_history_scope_all_help: "Ցուցադրվում են բեռնված բոլոր վերջին run-երը։",
    view_details: "Տեսնել մանրամասները",
    hide_details: "Թաքցնել մանրամասները",
    backtest_details: "Backtest-ի մանրամասներ",
    visible_runs_label: "Երևացող run-եր",
    best_visible_return_label: "Լավագույն եկամտաբերություն",
    average_return_label: "Միջին եկամտաբերություն",
    profitable_runs_label: "Շահութաբեր run-եր",
    with_closed_trades_label: "Փակված գործարքներով",
    backtest_strategy_fallback: "Strategy #{id}",
    winning_losing_trades_label: "Հաղթ. / պարտ.",
    best_recent_run: "Լավագույն վերջին run-ը",
    best_recent_run_help: "Հիմնված է այս strategy-ի վերջին պահպանված backtest-երի վրա։",
    run_more_backtests_to_compare: "Գործարկիր ավելի շատ backtest-եր՝ վերջին արդյունքները համեմատելու համար։",
    strategy_performance_comparison: "Strategy-ների performance-ի համեմատություն",
    strategy_performance_comparison_aria: "Strategy-ների performance-ի համեմատություն",
    strategy_performance_comparison_help:
      "Համեմատում է strategy-ները՝ օգտագործելով այժմ բեռնված սահմանափակ վերջին backtest-երը, ոչ թե ամբողջ պատմությունը։",
    loading_strategy_comparison: "Բեռնվում է strategy-ների համեմատությունը...",
    loading_strategy_comparison_hint: "Վերջին backtest history-ն պատրաստվում է համեմատության համար։",
    strategy_comparison_error: "Չհաջողվեց բեռնել strategy-ների համեմատությունը։",
    strategy_comparison_error_hint: "Վերջին backtest history-ն այժմ հասանելի չէ։ Փորձիր թարմացնել։",
    no_strategy_comparison: "Strategy-ների համեմատություն դեռ չկա։",
    no_strategy_comparison_hint: "Գործարկիր backtest-եր տարբեր strategy-ների համար՝ վերջին performance-ը համեմատելու համար։",
    no_comparable_strategy_runs: "Համեմատելի strategy run-եր չգտնվեցին։",
    no_comparable_strategy_runs_hint:
      "Վերջին backtest-երում strategy ID-ները բացակայում են, ուստի դրանք անվտանգ համեմատել հնարավոր չէ։",
    best_return_label: "Լավագույն վերադարձ",
    latest_return_label: "Վերջին վերադարձ",
    recent_runs_label: "Վերջին run-եր",
    last_backtest_label: "Վերջին backtest",
    selected_bot_strategy_label: "Ընտրված Bot-ի strategy",
    best_performer_badge: "Լավագույն արդյունք",
    needs_more_runs_badge: "Պետք են ավելի շատ run-եր",
    no_closed_trades_badge: "Փակված գործարքներ չկան",
    view_latest_run: "Տեսնել վերջին run-ը",
    latest_run_not_visible: "Վերջին run-ը տեսանելի չէ",
    latest_run_not_visible_hint: "Վերջին run-ը ընթացիկ recent list-ում տեսանելի չէ։",
    use_for_new_backtest: "Օգտագործել նոր backtest-ի համար",
    strategy_not_available_for_backtest: "Strategy-ն հասանելի չէ backtest-ի ձևում։",
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
const createStrategyPanel = document.querySelector(".create-strategy-panel");
const createStrategyHeading = document.querySelector("#create-strategy-heading");
const toggleCreateStrategy = document.querySelector("#toggle-create-strategy");
const createStrategyForm = document.querySelector("#create-strategy-form");
const createStrategyNameLabel = document.querySelector("#create-strategy-name-label");
const createStrategySymbolLabel = document.querySelector("#create-strategy-symbol-label");
const createStrategyTimeframeLabel = document.querySelector("#create-strategy-timeframe-label");
const createStrategyTypeLabel = document.querySelector("#create-strategy-type-label");
const createStrategyName = document.querySelector("#create-strategy-name");
const createStrategySymbol = document.querySelector("#create-strategy-symbol");
const createStrategyTimeframe = document.querySelector("#create-strategy-timeframe");
const createStrategyType = document.querySelector("#create-strategy-type");
const createStrategyParamOneLabel = document.querySelector("#create-strategy-param-one-label");
const createStrategyParamTwoLabel = document.querySelector("#create-strategy-param-two-label");
const createStrategyParamThreeLabel = document.querySelector("#create-strategy-param-three-label");
const createStrategyParamFourField = document.querySelector("#create-strategy-param-four-field");
const createStrategyParamFourLabel = document.querySelector("#create-strategy-param-four-label");
const createStrategyParamOne = document.querySelector("#create-strategy-param-one");
const createStrategyParamTwo = document.querySelector("#create-strategy-param-two");
const createStrategyParamThree = document.querySelector("#create-strategy-param-three");
const createStrategyParamFour = document.querySelector("#create-strategy-param-four");
const createStrategySubmit = document.querySelector("#create-strategy-submit");
const createStrategyCancel = document.querySelector("#create-strategy-cancel");
const createStrategyMessageEl = document.querySelector("#create-strategy-message");
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
const botPerformancePanel = document.querySelector(".bot-performance-panel");
const botPerformanceHeading = document.querySelector("#bot-performance-heading");
const botPerformanceContent = document.querySelector("#bot-performance-content");
const paperPortfolioPanel = document.querySelector(".paper-portfolio-panel");
const paperPortfolioHeading = document.querySelector("#paper-portfolio-heading");
const paperPortfolioHelp = document.querySelector("#paper-portfolio-help");
const paperPortfolioContent = document.querySelector("#paper-portfolio-content");
const recentPaperOrdersPanel = document.querySelector(".recent-paper-orders-panel");
const recentPaperOrdersHeading = document.querySelector("#recent-paper-orders-heading");
const recentPaperOrdersHelp = document.querySelector("#recent-paper-orders-help");
const recentPaperOrdersContent = document.querySelector("#recent-paper-orders-content");
const executionSafetyPanel = document.querySelector(".execution-safety-panel");
const executionSafetyHeading = document.querySelector("#execution-safety-heading");
const executionSafetyHelp = document.querySelector("#execution-safety-help");
const executionSafetyContent = document.querySelector("#execution-safety-content");
const reconciliationWorkerPanel = document.querySelector(".reconciliation-worker-panel");
const reconciliationWorkerHeading = document.querySelector("#reconciliation-worker-heading");
const reconciliationWorkerHelp = document.querySelector("#reconciliation-worker-help");
const reconciliationWorkerContent = document.querySelector("#reconciliation-worker-content");
const recentReconciliationJobsPanel = document.querySelector(".recent-reconciliation-jobs-panel");
const recentReconciliationJobsHeading = document.querySelector("#recent-reconciliation-jobs-heading");
const recentReconciliationJobsHelp = document.querySelector("#recent-reconciliation-jobs-help");
const recentReconciliationJobsContent = document.querySelector("#recent-reconciliation-jobs-content");
const liveMarketPanel = document.querySelector(".live-market-panel");
const liveMarketHeading = document.querySelector("#live-market-heading");
const liveMarketHelp = document.querySelector("#live-market-help");
const liveMarketForm = document.querySelector("#live-market-form");
const liveMarketSymbolLabel = document.querySelector("#live-market-symbol-label");
const liveMarketSymbol = document.querySelector("#live-market-symbol");
const liveMarketAdd = document.querySelector("#live-market-add");
const liveMarketRefresh = document.querySelector("#live-market-refresh");
const liveMarketAutoRefresh = document.querySelector("#live-market-auto-refresh");
const liveMarketAutoRefreshLabel = document.querySelector("#live-market-auto-refresh-label");
const liveMarketMessageEl = document.querySelector("#live-market-message");
const liveMarketWatchlist = document.querySelector("#live-market-watchlist");
const candleModalEl = document.querySelector("#live-market-candle-modal");
const candleModalEyebrow = document.querySelector("#candle-modal-eyebrow");
const candleModalTitle = document.querySelector("#candle-modal-title");
const candleModalClose = document.querySelector("#candle-modal-close");
const candleTimeframeLabel = document.querySelector("#candle-timeframe-label");
const candleTimeframe = document.querySelector("#candle-timeframe");
const candleLimitLabel = document.querySelector("#candle-limit-label");
const candleLimit = document.querySelector("#candle-limit");
const candleDateLabel = document.querySelector("#candle-date-label");
const candleDate = document.querySelector("#candle-date");
const candleDateClear = document.querySelector("#candle-date-clear");
const candleRefresh = document.querySelector("#candle-refresh");
const candleModalMessage = document.querySelector("#candle-modal-message");
const candleChartHelp = document.querySelector("#candle-chart-help");
const candleLoadOlder = document.querySelector("#candle-load-older");
const candleOlderMessage = document.querySelector("#candle-older-message");
const candleWindowPrev = document.querySelector("#candle-window-prev");
const candleWindowReset = document.querySelector("#candle-window-reset");
const candleWindowNext = document.querySelector("#candle-window-next");
const candleChart = document.querySelector("#candle-chart");
const candleSummary = document.querySelector("#candle-summary");
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
const strategyExtraParameterField = document.querySelector("#strategy-extra-parameter-field");
const strategyExtraParameterLabel = document.querySelector("#strategy-extra-parameter-label");
const strategyBuyBelow = document.querySelector("#strategy-buy-below");
const strategySellAbove = document.querySelector("#strategy-sell-above");
const strategyQuantity = document.querySelector("#strategy-quantity");
const strategyExtraParameter = document.querySelector("#strategy-extra-parameter");
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
const optimizationPresetsTitle = document.querySelector("#optimization-presets-title");
const optimizationPresetsHelp = document.querySelector("#optimization-presets-help");
const optimizationPriceConservative = document.querySelector("#optimization-price-conservative");
const optimizationPriceBalanced = document.querySelector("#optimization-price-balanced");
const optimizationPriceWide = document.querySelector("#optimization-price-wide");
const optimizationMaFast = document.querySelector("#optimization-ma-fast");
const optimizationMaBalanced = document.querySelector("#optimization-ma-balanced");
const optimizationMaSlow = document.querySelector("#optimization-ma-slow");
const optimizationRsiStandard = document.querySelector("#optimization-rsi-standard");
const optimizationRsiSensitive = document.querySelector("#optimization-rsi-sensitive");
const optimizationRsiConservative = document.querySelector("#optimization-rsi-conservative");
const optimizationBollingerStandard = document.querySelector("#optimization-bollinger-standard");
const optimizationBollingerTight = document.querySelector("#optimization-bollinger-tight");
const optimizationBollingerWide = document.querySelector("#optimization-bollinger-wide");
const optimizationMacdStandard = document.querySelector("#optimization-macd-standard");
const optimizationMacdFast = document.querySelector("#optimization-macd-fast");
const optimizationMacdSlow = document.querySelector("#optimization-macd-slow");
const optimizationFirstValuesLabel = document.querySelector("#optimization-first-values-label");
const optimizationFirstValues = document.querySelector("#optimization-first-values");
const optimizationSecondValuesLabel = document.querySelector("#optimization-second-values-label");
const optimizationSecondValues = document.querySelector("#optimization-second-values");
const optimizationThirdValuesField = document.querySelector("#optimization-third-values-field");
const optimizationThirdValuesLabel = document.querySelector("#optimization-third-values-label");
const optimizationThirdValues = document.querySelector("#optimization-third-values");
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
const backtestComparisonPanel = document.querySelector(".backtest-comparison-panel");
const backtestComparisonHeading = document.querySelector("#backtest-comparison-heading");
const backtestComparisonHelp = document.querySelector("#backtest-comparison-help");
const backtestComparisonEl = document.querySelector("#backtest-comparison");
const backtestHistoryPanel = document.querySelector(".backtest-history-panel");
const backtestHistoryHeading = document.querySelector("#backtest-history-heading");
const backtestHistoryScopeControl = document.querySelector(".backtest-history-scope");
const backtestHistoryScopeSelected = document.querySelector("#backtest-history-scope-selected");
const backtestHistoryScopeAll = document.querySelector("#backtest-history-scope-all");
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

function normalizeMarketSymbol(value) {
  return String(value || "")
    .trim()
    .toUpperCase();
}

function liveMarketSymbolItem(symbol) {
  return {
    symbol,
    price: null,
    previousPrice: null,
    updatedAt: null,
    isLoading: false,
    error: "",
  };
}

function getStoredLiveMarketSymbols() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(LIVE_MARKET_STORAGE_KEY) || "null");
    const symbols = Array.isArray(stored)
      ? stored.map(normalizeMarketSymbol).filter(Boolean)
      : DEFAULT_LIVE_MARKET_SYMBOLS;
    return [...new Set(symbols)].map(liveMarketSymbolItem);
  } catch (error) {
    return DEFAULT_LIVE_MARKET_SYMBOLS.map(liveMarketSymbolItem);
  }
}

function getStoredLiveMarketAutoRefresh() {
  try {
    return window.localStorage.getItem(LIVE_MARKET_AUTO_REFRESH_STORAGE_KEY) === "true";
  } catch (error) {
    return false;
  }
}

function persistLiveMarketSymbols() {
  try {
    window.localStorage.setItem(
      LIVE_MARKET_STORAGE_KEY,
      JSON.stringify(liveMarketSymbols.map((item) => item.symbol)),
    );
  } catch (error) {
    // Keep the watchlist usable in memory when browser storage is unavailable.
  }
}

function persistLiveMarketAutoRefresh() {
  try {
    window.localStorage.setItem(
      LIVE_MARKET_AUTO_REFRESH_STORAGE_KEY,
      String(liveMarketAutoRefreshEnabled),
    );
  } catch (error) {
    // Auto-refresh still works for the current page session without storage.
  }
}

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
  createStrategyPanel?.setAttribute("aria-label", t("create_strategy_aria"));
  createStrategyForm.setAttribute("aria-label", t("create_strategy_aria"));
  createStrategyHeading.textContent = t("strategies_heading");
  createStrategyNameLabel.textContent = t("strategy_name_form_label");
  createStrategySymbolLabel.textContent = t("symbol");
  createStrategyTimeframeLabel.textContent = t("timeframe_label");
  createStrategyTypeLabel.textContent = t("strategy_type_label");
  createStrategyName.placeholder = t("create_strategy_hint_name");
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
  botPerformancePanel?.setAttribute("aria-label", t("bot_performance_aria"));
  botPerformanceHeading.textContent = t("bot_performance");
  paperPortfolioPanel?.setAttribute("aria-label", t("draft_balance_aria"));
  paperPortfolioHeading.textContent = t("draft_balance");
  paperPortfolioHelp.textContent = t("draft_balance_help");
  recentPaperOrdersPanel?.setAttribute("aria-label", t("recent_paper_orders_aria"));
  recentPaperOrdersHeading.textContent = t("recent_paper_orders");
  recentPaperOrdersHelp.textContent = t("recent_paper_orders_help");
  executionSafetyPanel?.setAttribute("aria-label", t("execution_safety_aria"));
  executionSafetyHeading.textContent = t("execution_safety");
  executionSafetyHelp.textContent = t("execution_safety_help");
  reconciliationWorkerPanel?.setAttribute("aria-label", t("reconciliation_worker_aria"));
  reconciliationWorkerHeading.textContent = t("reconciliation_worker");
  reconciliationWorkerHelp.textContent = t("reconciliation_worker_help");
  recentReconciliationJobsPanel?.setAttribute("aria-label", t("recent_reconciliation_jobs_aria"));
  recentReconciliationJobsHeading.textContent = t("recent_reconciliation_jobs");
  recentReconciliationJobsHelp.textContent = t("recent_reconciliation_jobs_help");
  liveMarketPanel?.setAttribute("aria-label", t("live_market_aria"));
  liveMarketHeading.textContent = t("live_market");
  liveMarketHelp.textContent = t("live_market_help");
  liveMarketForm.setAttribute("aria-label", t("live_market_add_symbol_aria"));
  liveMarketSymbolLabel.textContent = t("live_market_symbol_label");
  liveMarketAdd.textContent = t("live_market_add_symbol");
  liveMarketRefresh.textContent = isRefreshingLiveMarket
    ? t("live_market_refreshing")
    : t("live_market_refresh");
  liveMarketAutoRefreshLabel.textContent = t("live_market_auto_refresh");
  candleModalEyebrow.textContent = t("candle_modal_eyebrow");
  candleModalClose.textContent = t("close");
  candleTimeframeLabel.textContent = t("candle_timeframe_label");
  candleLimitLabel.textContent = t("candle_limit_label");
  candleDateLabel.textContent = t("candle_date_label");
  candleDateClear.textContent = t("candle_latest_candles");
  candleChartHelp.textContent = t("candle_chart_help");
  candleLoadOlder.textContent = candleModal.isLoadingOlder ? t("candle_loading_older") : t("candle_load_older");
  candleWindowPrev.textContent = t("candle_window_previous");
  candleWindowReset.textContent = t("candle_window_reset");
  candleWindowNext.textContent = t("candle_window_next");
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
  optimizationPresetsTitle.textContent = t("optimization_presets_title");
  optimizationPresetsHelp.textContent = t("optimization_presets_help");
  optimizationPriceConservative.textContent = t("optimization_preset_conservative_range");
  optimizationPriceBalanced.textContent = t("optimization_preset_balanced_range");
  optimizationPriceWide.textContent = t("optimization_preset_wider_range");
  optimizationMaFast.textContent = t("optimization_preset_fast_signals");
  optimizationMaBalanced.textContent = t("optimization_preset_balanced_windows");
  optimizationMaSlow.textContent = t("optimization_preset_slower_signals");
  optimizationRsiStandard.textContent = t("optimization_preset_standard_rsi");
  optimizationRsiSensitive.textContent = t("optimization_preset_sensitive_rsi");
  optimizationRsiConservative.textContent = t("optimization_preset_conservative_rsi");
  optimizationBollingerStandard.textContent = t("optimization_preset_standard_bands");
  optimizationBollingerTight.textContent = t("optimization_preset_tight_bands");
  optimizationBollingerWide.textContent = t("optimization_preset_wide_bands");
  optimizationMacdStandard.textContent = t("optimization_preset_standard_macd");
  optimizationMacdFast.textContent = t("optimization_preset_fast_macd");
  optimizationMacdSlow.textContent = t("optimization_preset_slow_macd");
  optimizationMinClosedTradesLabel.textContent = t("optimization_min_closed_trades_label");
  optimizationRequireClosedPositionLabel.textContent = t("optimization_require_closed_position_label");
  backtestComparisonPanel?.setAttribute("aria-label", t("strategy_performance_comparison_aria"));
  backtestComparisonHeading.textContent = t("strategy_performance_comparison");
  backtestComparisonHelp.textContent = t("strategy_performance_comparison_help");
  backtestHistoryPanel?.setAttribute("aria-label", t("recent_backtests_aria"));
  backtestHistoryHeading.textContent = t("recent_backtests");
  backtestHistoryScopeControl?.setAttribute("aria-label", t("backtest_history_scope_aria"));
  backtestHistoryScopeSelected.textContent = t("backtest_history_scope_selected");
  backtestHistoryScopeSelected.title = t("backtest_history_scope_selected_help");
  backtestHistoryScopeAll.textContent = t("backtest_history_scope_all");
  backtestHistoryScopeAll.title = t("backtest_history_scope_all_help");
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

function normalizePerformance(rawPerformance) {
  if (!rawPerformance || typeof rawPerformance !== "object") return null;
  return {
    botId: rawPerformance.bot_id ?? rawPerformance.botId ?? null,
    name: rawPerformance.name ?? "",
    symbol: rawPerformance.symbol ?? "",
    strategyType: normalizeStrategyType(rawPerformance.strategy_type ?? rawPerformance.strategyType ?? ""),
    latestMarketPrice: rawPerformance.latest_market_price ?? rawPerformance.latestMarketPrice ?? null,
    currentPositionQuantity:
      rawPerformance.current_position_quantity ?? rawPerformance.currentPositionQuantity ?? null,
    lastDecision: rawPerformance.last_decision ?? rawPerformance.lastDecision ?? "",
    lastDecisionReason: rawPerformance.last_decision_reason ?? rawPerformance.lastDecisionReason ?? "",
    lastRunEventAt: rawPerformance.last_run_event_at ?? rawPerformance.lastRunEventAt ?? null,
    recentRunEventCount: rawPerformance.recent_run_event_count ?? rawPerformance.recentRunEventCount ?? 0,
    buyDecisionCount: rawPerformance.buy_decision_count ?? rawPerformance.buyDecisionCount ?? 0,
    sellDecisionCount: rawPerformance.sell_decision_count ?? rawPerformance.sellDecisionCount ?? 0,
    holdDecisionCount: rawPerformance.hold_decision_count ?? rawPerformance.holdDecisionCount ?? 0,
    riskBlockedEventCount:
      rawPerformance.risk_blocked_event_count ?? rawPerformance.riskBlockedEventCount ?? 0,
    filledOrderEventCount:
      rawPerformance.filled_order_event_count ?? rawPerformance.filledOrderEventCount ?? 0,
    realizedPnl: rawPerformance.realized_pnl ?? rawPerformance.realizedPnl ?? null,
    unrealizedPnl: rawPerformance.unrealized_pnl ?? rawPerformance.unrealizedPnl ?? null,
    health: normalizeRiskReason(rawPerformance.health || "unknown"),
  };
}

function normalizePaperPortfolioPosition(rawPosition) {
  return {
    symbol: rawPosition.symbol ?? "",
    quantity: rawPosition.quantity ?? null,
    averageEntryPrice: rawPosition.average_entry_price ?? rawPosition.averageEntryPrice ?? null,
    latestMarketPrice:
      rawPosition.latest_market_price ??
      rawPosition.latestMarketPrice ??
      rawPosition.latest_price ??
      rawPosition.latestPrice ??
      null,
    marketValue: rawPosition.market_value ?? rawPosition.marketValue ?? null,
    realizedPnl: rawPosition.realized_pnl ?? rawPosition.realizedPnl ?? null,
    unrealizedPnl: rawPosition.unrealized_pnl ?? rawPosition.unrealizedPnl ?? null,
    unrealizedPnlPercent:
      rawPosition.unrealized_pnl_percent ?? rawPosition.unrealizedPnlPercent ?? null,
    priceAvailable: Boolean(rawPosition.price_available ?? rawPosition.priceAvailable),
    updatedAt: rawPosition.updated_at ?? rawPosition.updatedAt ?? null,
  };
}

function normalizePaperPortfolio(rawPortfolio) {
  if (!rawPortfolio || typeof rawPortfolio !== "object") return null;
  const currency =
    rawPortfolio.account_currency ??
    rawPortfolio.accountCurrency ??
    rawPortfolio.base_currency ??
    rawPortfolio.baseCurrency ??
    "USDT";
  const rawPositions = Array.isArray(rawPortfolio.positions) ? rawPortfolio.positions : [];
  return {
    accountCurrency: currency,
    startingBalance: rawPortfolio.starting_balance ?? rawPortfolio.startingBalance ?? null,
    cashBalance: rawPortfolio.cash_balance ?? rawPortfolio.cashBalance ?? null,
    positionsMarketValue:
      rawPortfolio.positions_market_value ??
      rawPortfolio.positionsMarketValue ??
      rawPortfolio.total_market_value ??
      rawPortfolio.totalMarketValue ??
      null,
    totalEquity: rawPortfolio.total_equity ?? rawPortfolio.totalEquity ?? null,
    totalRealizedPnl: rawPortfolio.total_realized_pnl ?? rawPortfolio.totalRealizedPnl ?? null,
    totalUnrealizedPnl: rawPortfolio.total_unrealized_pnl ?? rawPortfolio.totalUnrealizedPnl ?? null,
    openPositionCount: rawPortfolio.open_position_count ?? rawPortfolio.openPositionCount ?? rawPositions.length,
    updatedAt: rawPortfolio.updated_at ?? rawPortfolio.updatedAt ?? null,
    positions: rawPositions.map(normalizePaperPortfolioPosition),
  };
}

function normalizePaperOrder(rawOrder) {
  const fills = Array.isArray(rawOrder.fills) ? rawOrder.fills : [];
  return {
    id: rawOrder.id ?? null,
    botId: rawOrder.bot_id ?? rawOrder.botId ?? null,
    strategyId: rawOrder.strategy_id ?? rawOrder.strategyId ?? null,
    symbol: rawOrder.symbol ?? "",
    side: rawOrder.side ?? "",
    status: rawOrder.status ?? "",
    mode: rawOrder.mode ?? "",
    orderType: rawOrder.order_type ?? rawOrder.orderType ?? "",
    quantity: rawOrder.quantity ?? null,
    requestedPrice:
      rawOrder.requested_price ??
      rawOrder.requestedPrice ??
      rawOrder.requested_price_snapshot ??
      rawOrder.requestedPriceSnapshot ??
      null,
    rejectionReason: rawOrder.rejection_reason ?? rawOrder.rejectionReason ?? "",
    decisionReason: rawOrder.decision_reason ?? rawOrder.decisionReason ?? "",
    fillCount: rawOrder.fill_count ?? rawOrder.fillCount ?? fills.length,
    fills: fills.map((fill) => ({
      fillPrice: fill.fill_price ?? fill.fillPrice ?? null,
      fillQuantity: fill.fill_quantity ?? fill.fillQuantity ?? null,
    })),
    createdAt: rawOrder.created_at ?? rawOrder.createdAt ?? null,
    updatedAt: rawOrder.updated_at ?? rawOrder.updatedAt ?? null,
  };
}

function normalizePaperOrders(data) {
  const rawOrders = Array.isArray(data) ? data : data?.items ?? [];
  return Array.isArray(rawOrders) ? rawOrders.map(normalizePaperOrder) : [];
}

function normalizeExecutionSafety(rawStatus) {
  if (!rawStatus || typeof rawStatus !== "object") return null;
  return {
    globalExecutionEnabled:
      rawStatus.global_execution_enabled ?? rawStatus.globalExecutionEnabled ?? null,
    liveExecutionEnabled: rawStatus.live_execution_enabled ?? rawStatus.liveExecutionEnabled ?? null,
    paperExecutionAllowed:
      rawStatus.paper_execution_allowed ?? rawStatus.paperExecutionAllowed ?? null,
    binanceTestnetBrokerEnabled:
      rawStatus.binance_testnet_broker_enabled ??
      rawStatus.binanceTestnetBrokerEnabled ??
      null,
    binanceTestnetOrderSubmissionEnabled:
      rawStatus.binance_testnet_order_submission_enabled ??
      rawStatus.binanceTestnetOrderSubmissionEnabled ??
      null,
    binanceTestnetCredentialsConfigured:
      rawStatus.binance_testnet_credentials_configured ??
      rawStatus.binanceTestnetCredentialsConfigured ??
      null,
    maxOrderNotional: rawStatus.max_order_notional ?? rawStatus.maxOrderNotional ?? null,
    maxDailyOrderCount: rawStatus.max_daily_order_count ?? rawStatus.maxDailyOrderCount ?? null,
    maxDailyLoss: rawStatus.max_daily_loss ?? rawStatus.maxDailyLoss ?? null,
    utcDayStart: rawStatus.utc_day_start ?? rawStatus.utcDayStart ?? null,
    currentDailyAcceptedOrderCount:
      rawStatus.current_daily_attempt_count ??
      rawStatus.currentDailyAttemptCount ??
      rawStatus.current_daily_accepted_order_count ??
      rawStatus.currentDailyAcceptedOrderCount ??
      null,
    remainingDailyOrderCapacity:
      rawStatus.remaining_daily_order_capacity ??
      rawStatus.remainingDailyOrderCapacity ??
      null,
    currentDailyRealizedLoss:
      rawStatus.current_daily_realized_loss ?? rawStatus.currentDailyRealizedLoss ?? null,
    isExecutionCurrentlyAllowed:
      rawStatus.is_execution_currently_allowed ??
      rawStatus.isExecutionCurrentlyAllowed ??
      null,
    blockingReason: rawStatus.blocking_reason ?? rawStatus.blockingReason ?? "",
    metadata:
      rawStatus.metadata && typeof rawStatus.metadata === "object" && !Array.isArray(rawStatus.metadata)
        ? rawStatus.metadata
        : {},
  };
}

function normalizeReconciliationWorkerStatus(rawStatus) {
  if (!rawStatus || typeof rawStatus !== "object") return null;
  return {
    initialized: rawStatus.initialized ?? null,
    configuredEnabled: rawStatus.configured_enabled ?? rawStatus.configuredEnabled ?? null,
    state: rawStatus.state ?? null,
    lastStartedAt: rawStatus.last_started_at ?? rawStatus.lastStartedAt ?? null,
    lastHeartbeatAt: rawStatus.last_heartbeat_at ?? rawStatus.lastHeartbeatAt ?? null,
    lastStoppedAt: rawStatus.last_stopped_at ?? rawStatus.lastStoppedAt ?? null,
    lastCycleFinishedAt:
      rawStatus.last_cycle_finished_at ?? rawStatus.lastCycleFinishedAt ?? null,
    lastCycleResultCode:
      rawStatus.last_cycle_result_code ?? rawStatus.lastCycleResultCode ?? null,
    lastProcessedReconciliationJobId:
      rawStatus.last_processed_reconciliation_job_id ??
      rawStatus.lastProcessedReconciliationJobId ??
      null,
    heartbeatStaleAfterSeconds:
      rawStatus.heartbeat_stale_after_seconds ?? rawStatus.heartbeatStaleAfterSeconds ?? null,
    isStale: rawStatus.is_stale ?? rawStatus.isStale ?? null,
    updatedAt: rawStatus.updated_at ?? rawStatus.updatedAt ?? null,
  };
}

function normalizeReconciliationJob(rawJob) {
  if (!rawJob || typeof rawJob !== "object") return null;
  return {
    id: rawJob.id ?? null,
    executionAttemptId: rawJob.execution_attempt_id ?? rawJob.executionAttemptId ?? null,
    botId: rawJob.bot_id ?? rawJob.botId ?? null,
    status: rawJob.status ?? null,
    automaticAttemptCount:
      rawJob.automatic_attempt_count ?? rawJob.automaticAttemptCount ?? null,
    maxAutomaticAttempts:
      rawJob.max_automatic_attempts ?? rawJob.maxAutomaticAttempts ?? null,
    nextAttemptAt: rawJob.next_attempt_at ?? rawJob.nextAttemptAt ?? null,
    claimedAt: rawJob.claimed_at ?? rawJob.claimedAt ?? null,
    resolvedAt: rawJob.resolved_at ?? rawJob.resolvedAt ?? null,
    exhaustedAt: rawJob.exhausted_at ?? rawJob.exhaustedAt ?? null,
    lastResult: rawJob.last_result ?? rawJob.lastResult ?? null,
    lastFailure: rawJob.last_failure ?? rawJob.lastFailure ?? null,
    createdAt: rawJob.created_at ?? rawJob.createdAt ?? null,
    updatedAt: rawJob.updated_at ?? rawJob.updatedAt ?? null,
  };
}

function normalizeReconciliationJobs(data) {
  const rawJobs = Array.isArray(data) ? data : data?.items ?? [];
  if (!Array.isArray(rawJobs)) return [];
  return rawJobs.map(normalizeReconciliationJob).filter(Boolean);
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
    cashBalance: rawItem.cash_balance ?? rawItem.cashBalance ?? null,
    realizedPnl: rawItem.realized_pnl ?? null,
    unrealizedPnl: rawItem.unrealized_pnl ?? rawItem.unrealizedPnl ?? null,
    totalReturn: rawItem.total_return ?? null,
    totalReturnPercent: rawItem.total_return_percent ?? null,
    winRate: rawItem.win_rate ?? null,
    averageTradePnl: rawItem.average_trade_pnl ?? rawItem.averageTradePnl ?? null,
    bestTradePnl: rawItem.best_trade_pnl ?? rawItem.bestTradePnl ?? null,
    worstTradePnl: rawItem.worst_trade_pnl ?? rawItem.worstTradePnl ?? null,
    profitFactor: rawItem.profit_factor ?? null,
    numberOfTrades: rawItem.number_of_trades ?? 0,
    closedTrades: rawItem.closed_trades ?? rawItem.closedTrades ?? null,
    winningTrades: rawItem.winning_trades ?? null,
    losingTrades: rawItem.losing_trades ?? null,
    openPosition: rawItem.open_position ?? rawItem.openPosition ?? null,
    positionQuantity: rawItem.position_quantity ?? rawItem.positionQuantity ?? null,
    candleSource: rawItem.candle_source ?? rawItem.candleSource ?? rawItem.source ?? "",
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

function comparableTime(value) {
  const parsed = new Date(value || 0).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
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

    const itemTime = comparableTime(item.createdAt);
    const bestTime = comparableTime(best.createdAt);
    return itemTime > bestTime ? item : best;
  }, null);
}

function compareBacktestRuns(left, right) {
  const leftReturnPercent = comparableNumber(left?.totalReturnPercent);
  const rightReturnPercent = comparableNumber(right?.totalReturnPercent);
  if (leftReturnPercent !== rightReturnPercent) {
    if (leftReturnPercent === null) return 1;
    if (rightReturnPercent === null) return -1;
    return rightReturnPercent - leftReturnPercent;
  }

  const leftTotalReturn = comparableNumber(left?.totalReturn);
  const rightTotalReturn = comparableNumber(right?.totalReturn);
  if (leftTotalReturn !== rightTotalReturn) {
    if (leftTotalReturn === null) return 1;
    if (rightTotalReturn === null) return -1;
    return rightTotalReturn - leftTotalReturn;
  }

  const leftTime = comparableTime(left?.createdAt);
  const rightTime = comparableTime(right?.createdAt);
  return rightTime - leftTime;
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
  if (normalizeStrategyType(text) === "price_threshold") return t("price_threshold_label");
  if (normalizeStrategyType(text) === "moving_average_cross") return t("moving_average_cross_label");
  if (normalizeStrategyType(text) === "rsi_threshold") return t("rsi_threshold_label");
  if (normalizeStrategyType(text) === "bollinger_bands") return t("bollinger_bands_label");
  if (normalizeStrategyType(text) === "macd_crossover") return t("macd_crossover_label");
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

function formatUtcDateTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  const parts = new Intl.DateTimeFormat([], {
    timeZone: "UTC",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(parsed);
  const byType = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${byType.year}-${byType.month}-${byType.day} ${byType.hour}:${byType.minute} UTC`;
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

function formatPnlDecimal(value, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value);
  return new Intl.NumberFormat([], {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatMoney(value, currency, fallback = "—") {
  const formatted = formatDecimal(value, fallback);
  if (formatted === fallback) return fallback;
  return currency ? `${formatted} ${currency}` : formatted;
}

function formatPnlMoney(value, currency, fallback = "—") {
  const formatted = formatPnlDecimal(value, fallback);
  if (formatted === fallback) return fallback;
  return currency ? `${formatted} ${currency}` : formatted;
}

function formatCompactMoney(value, currency, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value);
  const formatted = new Intl.NumberFormat([], {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(parsed);
  return currency ? `${formatted} ${currency}` : formatted;
}

function formatCompactPnlMoney(value, currency, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value);
  const formatted = new Intl.NumberFormat([], {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed);
  return currency ? `${formatted} ${currency}` : formatted;
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
    period: t("period_label"),
    stddev_multiplier: t("stddev_multiplier_label"),
    fast_period: t("fast_period_label"),
    slow_period: t("slow_period_label"),
    signal_period: t("signal_period_label"),
    oversold: t("oversold_label"),
    overbought: t("overbought_label"),
    quantity: t("quantity"),
  };
  return knownLabels[key] ?? humanizeMessage(key, key);
}

function orderedStrategyParameters(parameters) {
  const safeParameters =
    parameters && typeof parameters === "object" && !Array.isArray(parameters)
      ? parameters
      : {};
  const knownOrder = [
    "buy_below",
    "sell_above",
    "short_window",
    "long_window",
    "fast_period",
    "slow_period",
    "signal_period",
    "period",
    "stddev_multiplier",
    "oversold",
    "overbought",
    "quantity",
  ];
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
  if (strategyType === "rsi_threshold") {
    return [
      { key: "period", label: t("period_label"), input: strategyBuyBelow, labelEl: strategyBuyBelowLabel },
      { key: "oversold", label: t("oversold_label"), input: strategySellAbove, labelEl: strategySellAboveLabel },
      { key: "overbought", label: t("overbought_label"), input: strategyQuantity, labelEl: strategyQuantityLabel },
      { key: "quantity", label: t("quantity"), input: strategyExtraParameter, labelEl: strategyExtraParameterLabel },
    ];
  }
  if (strategyType === "bollinger_bands") {
    return [
      { key: "period", label: t("period_label"), input: strategyBuyBelow, labelEl: strategyBuyBelowLabel },
      { key: "stddev_multiplier", label: t("stddev_multiplier_label"), input: strategySellAbove, labelEl: strategySellAboveLabel },
      { key: "quantity", label: t("quantity"), input: strategyQuantity, labelEl: strategyQuantityLabel },
    ];
  }
  if (strategyType === "macd_crossover") {
    return [
      { key: "fast_period", label: t("fast_period_label"), input: strategyBuyBelow, labelEl: strategyBuyBelowLabel },
      { key: "slow_period", label: t("slow_period_label"), input: strategySellAbove, labelEl: strategySellAboveLabel },
      { key: "signal_period", label: t("signal_period_label"), input: strategyQuantity, labelEl: strategyQuantityLabel },
      { key: "quantity", label: t("quantity"), input: strategyExtraParameter, labelEl: strategyExtraParameterLabel },
    ];
  }
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

const CREATE_STRATEGY_TYPES = [
  "price_threshold",
  "moving_average_cross",
  "rsi_threshold",
  "bollinger_bands",
  "macd_crossover",
];

function createStrategyParameterFields() {
  const strategyType = normalizeStrategyType(createStrategyType.value || "price_threshold");
  if (strategyType === "rsi_threshold") {
    return [
      { key: "period", label: t("period_label"), input: createStrategyParamOne, labelEl: createStrategyParamOneLabel },
      { key: "oversold", label: t("oversold_label"), input: createStrategyParamTwo, labelEl: createStrategyParamTwoLabel },
      { key: "overbought", label: t("overbought_label"), input: createStrategyParamThree, labelEl: createStrategyParamThreeLabel },
      { key: "quantity", label: t("quantity"), input: createStrategyParamFour, labelEl: createStrategyParamFourLabel },
    ];
  }
  if (strategyType === "bollinger_bands") {
    return [
      { key: "period", label: t("period_label"), input: createStrategyParamOne, labelEl: createStrategyParamOneLabel },
      { key: "stddev_multiplier", label: t("stddev_multiplier_label"), input: createStrategyParamTwo, labelEl: createStrategyParamTwoLabel },
      { key: "quantity", label: t("quantity"), input: createStrategyParamThree, labelEl: createStrategyParamThreeLabel },
    ];
  }
  if (strategyType === "macd_crossover") {
    return [
      { key: "fast_period", label: t("fast_period_label"), input: createStrategyParamOne, labelEl: createStrategyParamOneLabel },
      { key: "slow_period", label: t("slow_period_label"), input: createStrategyParamTwo, labelEl: createStrategyParamTwoLabel },
      { key: "signal_period", label: t("signal_period_label"), input: createStrategyParamThree, labelEl: createStrategyParamThreeLabel },
      { key: "quantity", label: t("quantity"), input: createStrategyParamFour, labelEl: createStrategyParamFourLabel },
    ];
  }
  if (strategyType === "moving_average_cross") {
    return [
      { key: "short_window", label: t("short_window_label"), input: createStrategyParamOne, labelEl: createStrategyParamOneLabel },
      { key: "long_window", label: t("long_window_label"), input: createStrategyParamTwo, labelEl: createStrategyParamTwoLabel },
      { key: "quantity", label: t("quantity"), input: createStrategyParamThree, labelEl: createStrategyParamThreeLabel },
    ];
  }
  return [
    { key: "buy_below", label: t("buy_below_label"), input: createStrategyParamOne, labelEl: createStrategyParamOneLabel },
    { key: "sell_above", label: t("sell_above_label"), input: createStrategyParamTwo, labelEl: createStrategyParamTwoLabel },
    { key: "quantity", label: t("quantity"), input: createStrategyParamThree, labelEl: createStrategyParamThreeLabel },
  ];
}

function createStrategyDefaults(strategyType) {
  if (strategyType === "rsi_threshold") {
    return { period: "14", oversold: "30", overbought: "70", quantity: "0.001" };
  }
  if (strategyType === "bollinger_bands") {
    return { period: "20", stddev_multiplier: "2", quantity: "0.001" };
  }
  if (strategyType === "macd_crossover") {
    return { fast_period: "12", slow_period: "26", signal_period: "9", quantity: "0.001" };
  }
  if (strategyType === "moving_average_cross") {
    return { short_window: "5", long_window: "20", quantity: "0.001" };
  }
  return { buy_below: "95000", sell_above: "105000", quantity: "0.001" };
}

function populateCreateStrategyParameters(strategyType = normalizeStrategyType(createStrategyType.value)) {
  const defaults = createStrategyDefaults(strategyType);
  [createStrategyParamOne, createStrategyParamTwo, createStrategyParamThree, createStrategyParamFour].forEach(
    (input) => {
      input.value = "";
      input.name = "";
    },
  );
  createStrategyParameterFields().forEach((field) => {
    field.input.value = defaults[field.key] ?? "";
    field.input.name = field.key;
  });
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
  [strategyBuyBelow, strategySellAbove, strategyQuantity, strategyExtraParameter].forEach((input) => {
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

function parseRsiThresholdParameter(value) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed > 0 && parsed < 100 ? trimmed : null;
}

function parseIntegerAtLeast(value, minimum) {
  const parsed = parsePositiveIntegerParameter(value);
  return parsed !== null && parsed >= minimum ? parsed : null;
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

  if (selectedStrategyType() === "rsi_threshold") {
    const period = parsePositiveIntegerParameter(strategyBuyBelow.value);
    const oversold = parseRsiThresholdParameter(strategySellAbove.value);
    const overbought = parseRsiThresholdParameter(strategyQuantity.value);
    const quantity = strategyExtraParameter.value.trim();
    if (
      !strategyBuyBelow.value.trim() ||
      !strategySellAbove.value.trim() ||
      !strategyQuantity.value.trim() ||
      !quantity
    ) {
      return t("enter_rsi_parameters");
    }
    if (period === null) return t("rsi_period_must_be_integer");
    if (oversold === null || overbought === null) return t("rsi_thresholds_must_be_numbers");
    if (Number(oversold) >= Number(overbought)) return t("rsi_oversold_less_than_overbought");
    if (parsePositiveParameter(quantity) === null) return t("rsi_quantity_must_be_positive");
    return "";
  }

  if (selectedStrategyType() === "bollinger_bands") {
    const period = parseIntegerAtLeast(strategyBuyBelow.value, 2);
    const stddevMultiplier = parsePositiveParameter(strategySellAbove.value);
    const quantity = parsePositiveParameter(strategyQuantity.value);
    if (!strategyBuyBelow.value.trim() || !strategySellAbove.value.trim() || !strategyQuantity.value.trim()) {
      return t("enter_bollinger_parameters");
    }
    if (period === null) return t("bollinger_period_must_be_at_least_two");
    if (stddevMultiplier === null || quantity === null) return t("bollinger_parameters_must_be_positive");
    return "";
  }

  if (selectedStrategyType() === "macd_crossover") {
    const fastPeriod = parsePositiveIntegerParameter(strategyBuyBelow.value);
    const slowPeriod = parsePositiveIntegerParameter(strategySellAbove.value);
    const signalPeriod = parsePositiveIntegerParameter(strategyQuantity.value);
    const quantity = parsePositiveParameter(strategyExtraParameter.value);
    if (
      !strategyBuyBelow.value.trim() ||
      !strategySellAbove.value.trim() ||
      !strategyQuantity.value.trim() ||
      !strategyExtraParameter.value.trim()
    ) {
      return t("enter_macd_parameters");
    }
    if (fastPeriod === null || slowPeriod === null || signalPeriod === null) {
      return t("macd_periods_must_be_integers");
    }
    if (fastPeriod >= slowPeriod) return t("macd_fast_less_than_slow");
    if (quantity === null) return t("macd_quantity_must_be_positive");
    return "";
  }

  const values = [strategyBuyBelow.value.trim(), strategySellAbove.value.trim(), strategyQuantity.value.trim()];
  if (values.some((value) => !value)) return t("enter_strategy_parameters");
  if (values.some((value) => parsePositiveParameter(value) === null)) return t("strategy_parameters_must_be_numbers");
  return "";
}

function validateCreateStrategyForm() {
  const strategyType = normalizeStrategyType(createStrategyType.value);
  if (!createStrategyName.value.trim()) return t("enter_strategy_name");
  if (!createStrategySymbol.value.trim()) return t("enter_strategy_symbol");
  if (!createStrategyTimeframe.value.trim()) return t("enter_strategy_timeframe");
  if (!CREATE_STRATEGY_TYPES.includes(strategyType)) return t("select_strategy_type");

  if (strategyType === "moving_average_cross") {
    const shortWindow = parsePositiveIntegerParameter(createStrategyParamOne.value);
    const longWindow = parsePositiveIntegerParameter(createStrategyParamTwo.value);
    const quantity = parsePositiveParameter(createStrategyParamThree.value);
    if (!createStrategyParamOne.value.trim() || !createStrategyParamTwo.value.trim() || !createStrategyParamThree.value.trim()) {
      return t("enter_moving_average_parameters");
    }
    if (shortWindow === null || longWindow === null) return t("moving_average_windows_must_be_integers");
    if (shortWindow >= longWindow) return t("moving_average_short_less_than_long");
    if (quantity === null) return t("strategy_parameters_must_be_numbers");
    return "";
  }

  if (strategyType === "rsi_threshold") {
    const period = parsePositiveIntegerParameter(createStrategyParamOne.value);
    const oversold = parseRsiThresholdParameter(createStrategyParamTwo.value);
    const overbought = parseRsiThresholdParameter(createStrategyParamThree.value);
    const quantity = parsePositiveParameter(createStrategyParamFour.value);
    if (
      !createStrategyParamOne.value.trim() ||
      !createStrategyParamTwo.value.trim() ||
      !createStrategyParamThree.value.trim() ||
      !createStrategyParamFour.value.trim()
    ) {
      return t("enter_rsi_parameters");
    }
    if (period === null) return t("rsi_period_must_be_integer");
    if (oversold === null || overbought === null) return t("rsi_thresholds_must_be_numbers");
    if (Number(oversold) >= Number(overbought)) return t("rsi_oversold_less_than_overbought");
    if (quantity === null) return t("rsi_quantity_must_be_positive");
    return "";
  }

  if (strategyType === "bollinger_bands") {
    const period = parseIntegerAtLeast(createStrategyParamOne.value, 2);
    const stddevMultiplier = parsePositiveParameter(createStrategyParamTwo.value);
    const quantity = parsePositiveParameter(createStrategyParamThree.value);
    if (!createStrategyParamOne.value.trim() || !createStrategyParamTwo.value.trim() || !createStrategyParamThree.value.trim()) {
      return t("enter_bollinger_parameters");
    }
    if (period === null) return t("bollinger_period_must_be_at_least_two");
    if (stddevMultiplier === null || quantity === null) return t("bollinger_parameters_must_be_positive");
    return "";
  }

  if (strategyType === "macd_crossover") {
    const fastPeriod = parsePositiveIntegerParameter(createStrategyParamOne.value);
    const slowPeriod = parsePositiveIntegerParameter(createStrategyParamTwo.value);
    const signalPeriod = parsePositiveIntegerParameter(createStrategyParamThree.value);
    const quantity = parsePositiveParameter(createStrategyParamFour.value);
    if (
      !createStrategyParamOne.value.trim() ||
      !createStrategyParamTwo.value.trim() ||
      !createStrategyParamThree.value.trim() ||
      !createStrategyParamFour.value.trim()
    ) {
      return t("enter_macd_parameters");
    }
    if (fastPeriod === null || slowPeriod === null || signalPeriod === null) {
      return t("macd_periods_must_be_integers");
    }
    if (fastPeriod >= slowPeriod) return t("macd_fast_less_than_slow");
    if (quantity === null) return t("macd_quantity_must_be_positive");
    return "";
  }

  const buyBelow = parsePositiveParameter(createStrategyParamOne.value);
  const sellAbove = parsePositiveParameter(createStrategyParamTwo.value);
  const quantity = parsePositiveParameter(createStrategyParamThree.value);
  if (!createStrategyParamOne.value.trim() || !createStrategyParamTwo.value.trim() || !createStrategyParamThree.value.trim()) {
    return t("enter_strategy_parameters");
  }
  if (buyBelow === null || sellAbove === null || quantity === null) {
    return t("strategy_parameters_must_be_numbers");
  }
  if (Number(sellAbove) <= Number(buyBelow)) return t("sell_above_must_exceed_buy_below");
  return "";
}

function createStrategyPayload() {
  const parameters = {};
  createStrategyParameterFields().forEach((field) => {
    const value = field.input.value.trim();
    if (!value) return;
    parameters[field.key] = Number(value);
  });
  return {
    name: createStrategyName.value.trim(),
    symbol: createStrategySymbol.value.trim().toUpperCase(),
    timeframe: createStrategyTimeframe.value.trim(),
    strategy_type: normalizeStrategyType(createStrategyType.value),
    parameters,
  };
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
      : hasStrategyDetails && strategyType === "rsi_threshold"
        ? t("rsi_threshold_parameters_help")
        : hasStrategyDetails && strategyType === "bollinger_bands"
          ? t("bollinger_bands_parameters_help")
          : hasStrategyDetails && strategyType === "macd_crossover"
            ? t("macd_crossover_parameters_help")
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
  [strategyBuyBelow, strategySellAbove, strategyQuantity, strategyExtraParameter].forEach((input) => {
    input.disabled = shouldDisable;
    input.closest("label").hidden = true;
  });
  fields.forEach((field) => {
    field.input.closest("label").hidden = false;
    field.input.inputMode = ["period", "short_window", "long_window"].includes(field.key) ? "numeric" : "decimal";
  });
  strategyExtraParameterField.hidden = !fields.some((field) => field.input === strategyExtraParameter);
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
  if (strategyType === "rsi_threshold") return ["period", "oversold", "overbought", "quantity"];
  if (strategyType === "bollinger_bands") return ["period", "stddev_multiplier", "quantity"];
  if (strategyType === "macd_crossover") return ["fast_period", "slow_period", "signal_period", "quantity"];
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
  const optimizationSupported = [
    "price_threshold",
    "moving_average_cross",
    "rsi_threshold",
    "bollinger_bands",
    "macd_crossover",
  ].includes(strategyType);
  const pricePresetButtons = [optimizationPriceConservative, optimizationPriceBalanced, optimizationPriceWide];
  const movingAveragePresetButtons = [optimizationMaFast, optimizationMaBalanced, optimizationMaSlow];
  const rsiPresetButtons = [optimizationRsiStandard, optimizationRsiSensitive, optimizationRsiConservative];
  const bollingerPresetButtons = [optimizationBollingerStandard, optimizationBollingerTight, optimizationBollingerWide];
  const macdPresetButtons = [optimizationMacdStandard, optimizationMacdFast, optimizationMacdSlow];
  optimizationFirstValuesLabel.textContent =
    strategyType === "moving_average_cross"
      ? t("short_window_values_label")
      : strategyType === "macd_crossover"
        ? t("fast_period_values_label")
      : strategyType === "rsi_threshold"
        ? t("period_values_label")
        : strategyType === "bollinger_bands"
          ? t("period_values_label")
        : t("buy_below_values_label");
  optimizationSecondValuesLabel.textContent =
    strategyType === "moving_average_cross"
      ? t("long_window_values_label")
      : strategyType === "macd_crossover"
        ? t("slow_period_values_label")
      : strategyType === "rsi_threshold"
        ? t("oversold_values_label")
        : strategyType === "bollinger_bands"
          ? t("stddev_multiplier_values_label")
        : t("sell_above_values_label");
  optimizationThirdValuesLabel.textContent =
    strategyType === "macd_crossover" ? t("signal_period_values_label") : t("overbought_values_label");
  optimizationThirdValuesField.hidden = strategyType !== "rsi_threshold" && strategyType !== "macd_crossover";
  optimizationQuantityLabel.textContent =
    strategyType === "rsi_threshold" || strategyType === "bollinger_bands" || strategyType === "macd_crossover"
      ? t("quantity_values_label")
      : t("quantity");
  optimizationMinClosedTradesLabel.textContent = t("optimization_min_closed_trades_label");
  optimizationRequireClosedPositionLabel.textContent = t("optimization_require_closed_position_label");
  backtestOptimizationHelp.textContent =
    t("parameter_optimization_help") +
    " " +
    (strategyType === "moving_average_cross"
      ? t("optimization_ma_help")
      : strategyType === "macd_crossover"
        ? t("optimization_macd_help")
      : strategyType === "rsi_threshold"
        ? t("optimization_rsi_help")
        : strategyType === "bollinger_bands"
          ? t("optimization_bollinger_help")
        : t("optimization_price_help"));
  const shouldDisableOptimization = shouldDisable || !optimizationSupported;
  [
    optimizationFirstValues,
    optimizationSecondValues,
    optimizationThirdValues,
    optimizationQuantity,
    optimizationMinClosedTrades,
  ].forEach((input) => {
    input.disabled = shouldDisableOptimization;
  });
  pricePresetButtons.forEach((button) => {
    button.hidden = strategyType !== "price_threshold";
    button.disabled = shouldDisableOptimization;
  });
  movingAveragePresetButtons.forEach((button) => {
    button.hidden = strategyType !== "moving_average_cross";
    button.disabled = shouldDisableOptimization;
  });
  rsiPresetButtons.forEach((button) => {
    button.hidden = strategyType !== "rsi_threshold";
    button.disabled = shouldDisableOptimization;
  });
  bollingerPresetButtons.forEach((button) => {
    button.hidden = strategyType !== "bollinger_bands";
    button.disabled = shouldDisableOptimization;
  });
  macdPresetButtons.forEach((button) => {
    button.hidden = strategyType !== "macd_crossover";
    button.disabled = shouldDisableOptimization;
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

function strategyMetadata(strategyId) {
  return strategies.find((strategy) => botIdsEqual(strategy.id, strategyId)) ?? null;
}

function strategyTypeForComparison(item, strategy) {
  return item?.strategyType || strategy?.strategyType || "";
}

function latestBacktestRun(items) {
  return [...items].sort((left, right) => {
    const leftTime = comparableTime(left?.createdAt);
    const rightTime = comparableTime(right?.createdAt);
    return rightTime - leftTime;
  })[0] ?? null;
}

function backtestComparisonRows() {
  const groups = new Map();
  backtestHistory.forEach((item) => {
    if (item.strategyId === null || item.strategyId === undefined || item.strategyId === "") return;
    const key = String(item.strategyId);
    groups.set(key, [...(groups.get(key) ?? []), item]);
  });

  return [...groups.entries()]
    .map(([strategyId, runs]) => {
      const strategy = strategyMetadata(strategyId);
      const bestRun = selectBestRecentBacktest(runs);
      const latestRun = latestBacktestRun(runs);
      return {
        strategyId,
        strategy,
        runs,
        bestRun,
        latestRun,
      };
    })
    .sort((left, right) => compareBacktestRuns(left.bestRun, right.bestRun));
}

function renderBacktestComparisonState({ title, hint, className = "" }) {
  backtestComparisonEl.className = `backtest-comparison empty${className ? ` ${className}` : ""}`;
  const titleEl = document.createElement("strong");
  const hintEl = document.createElement("span");
  titleEl.textContent = title;
  hintEl.textContent = hint;
  backtestComparisonEl.append(titleEl, hintEl);
}

function visibleBacktestRunElement(runId, strategyId) {
  const historyCards = Array.from(backtestHistoryEl.querySelectorAll(".backtest-history-item"));
  if (runId !== null && runId !== undefined && runId !== "") {
    const runMatch = historyCards.find((item) => String(item.dataset.backtestRunId) === String(runId));
    if (runMatch) return runMatch;
  }
  if (strategyId === null || strategyId === undefined || strategyId === "") return null;
  return historyCards.find((item) => String(item.dataset.strategyId) === String(strategyId)) ?? null;
}

function viewLatestBacktestRun(runId, strategyId) {
  const target = visibleBacktestRunElement(runId, strategyId);
  if (!target) {
    backtestComparisonHelp.textContent = t("latest_run_not_visible");
    window.setTimeout(() => {
      backtestComparisonHelp.textContent = t("strategy_performance_comparison_help");
    }, 2200);
    return;
  }

  if (highlightedBacktestRunTimeout) window.clearTimeout(highlightedBacktestRunTimeout);
  backtestHistoryEl.querySelectorAll(".backtest-history-item.highlight").forEach((item) => {
    item.classList.remove("highlight");
  });
  target.classList.add("highlight");
  target.tabIndex = -1;
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.focus({ preventScroll: true });
  highlightedBacktestRunTimeout = window.setTimeout(() => {
    target.classList.remove("highlight");
    highlightedBacktestRunTimeout = null;
  }, 1800);
}

function selectedBotStrategyId() {
  return strategyIdForSelectedBot();
}

function hasSelectedBacktestHistoryStrategy() {
  return Boolean(selectedBotStrategyId());
}

function effectiveBacktestHistoryScope() {
  return backtestHistoryScope === "selected" && hasSelectedBacktestHistoryStrategy() ? "selected" : "all";
}

function visibleBacktestHistory() {
  const strategyId = effectiveBacktestHistoryScope() === "selected" ? selectedBotStrategyId() : null;
  if (!strategyId) return backtestHistory;
  return backtestHistory.filter((item) => botIdsEqual(item.strategyId, strategyId));
}

function renderBacktestHistoryScopeControl() {
  const canUseSelectedScope = hasSelectedBacktestHistoryStrategy();
  const activeScope = effectiveBacktestHistoryScope();
  backtestHistoryScopeSelected.disabled = !canUseSelectedScope;
  backtestHistoryScopeAll.disabled = false;
  backtestHistoryScopeSelected.classList.toggle("active", activeScope === "selected");
  backtestHistoryScopeAll.classList.toggle("active", activeScope === "all");
  backtestHistoryScopeSelected.setAttribute("aria-pressed", String(activeScope === "selected"));
  backtestHistoryScopeAll.setAttribute("aria-pressed", String(activeScope === "all"));
  backtestHistoryScopeSelected.title = canUseSelectedScope
    ? t("backtest_history_scope_selected_help")
    : t("select_strategy_for_backtest");
  backtestHistoryScopeAll.title = t("backtest_history_scope_all_help");
}

function backtestHistoryItemKey(item) {
  return String(firstAvailable(item?.id, `${item?.strategyId ?? "strategy"}-${item?.createdAt ?? "run"}`));
}

function hasBacktestDetailValue(value) {
  return value !== null && value !== undefined && value !== "";
}

function backtestDetailRows(item) {
  const rows = [
    { label: t("strategy"), value: strategyLabelForHistory(item.strategyId), always: true },
    { label: t("strategy_type_label"), value: humanizeMessage(item.strategyType, "—"), always: true },
    { label: t("initial_balance_label"), value: item.initialBalance, formatter: formatDecimal },
    {
      label: t("final_balance_label"),
      value: item.finalBalance,
      formatter: formatDecimal,
      className: pnlClass(item.finalBalance, item.initialBalance),
    },
    { label: t("cash_balance_label"), value: item.cashBalance, formatter: formatDecimal },
    { label: t("total_return_label"), value: item.totalReturn, formatter: formatDecimal, className: pnlClass(item.totalReturn) },
    {
      label: t("return_percent_label"),
      value: item.totalReturnPercent,
      formatter: formatPercent,
      className: pnlClass(item.totalReturnPercent),
    },
    { label: t("realized_pnl_label"), value: item.realizedPnl, formatter: formatDecimal, className: pnlClass(item.realizedPnl) },
    {
      label: t("unrealized_pnl_label"),
      value: item.unrealizedPnl,
      formatter: formatDecimal,
      className: pnlClass(item.unrealizedPnl),
    },
    { label: t("number_of_trades_label"), value: item.numberOfTrades, formatter: formatDecimal },
    { label: t("closed_trades_label"), value: item.closedTrades, formatter: formatDecimal },
    {
      label: t("winning_losing_trades_label"),
      value: `${formatDecimal(item.winningTrades, "0")} / ${formatDecimal(item.losingTrades, "0")}`,
      hasValue: hasBacktestDetailValue(item.winningTrades) || hasBacktestDetailValue(item.losingTrades),
    },
    { label: t("win_rate_label"), value: item.winRate, formatter: formatPercent },
    { label: t("profit_factor_label"), value: item.profitFactor, formatter: formatRatio },
    { label: t("average_trade_pnl_label"), value: item.averageTradePnl, formatter: formatDecimal, className: pnlClass(item.averageTradePnl) },
    { label: t("best_trade_pnl_label"), value: item.bestTradePnl, formatter: formatDecimal, className: pnlClass(item.bestTradePnl) },
    { label: t("worst_trade_pnl_label"), value: item.worstTradePnl, formatter: formatDecimal, className: pnlClass(item.worstTradePnl) },
    { label: t("open_position_label"), value: item.openPosition, formatter: formatBoolean },
    { label: t("open_position_qty_label"), value: item.positionQuantity, formatter: formatDecimal },
    { label: t("source_label"), value: item.candleSource || item.source, formatter: formatValue },
    { label: t("candles_processed_label"), value: item.candlesProcessed, formatter: formatDecimal },
    { label: t("updated_time_label"), value: item.createdAt, formatter: formatDateTime },
  ];

  return rows.filter(
    (row) =>
      row.always ||
      row.hasValue ||
      hasBacktestDetailValue(row.value),
  );
}

function renderBacktestHistoryDetails(item) {
  const section = document.createElement("section");
  section.className = "backtest-history-details";
  section.setAttribute("aria-label", t("backtest_details"));

  const grid = document.createElement("dl");
  grid.className = "backtest-history-details-grid";
  backtestDetailRows(item).forEach((detail) => {
    const group = document.createElement("div");
    const label = document.createElement("dt");
    const value = document.createElement("dd");
    label.textContent = detail.label;
    value.textContent = detail.formatter ? detail.formatter(detail.value) : formatValue(detail.value);
    if (detail.className) value.classList.add(detail.className);
    group.append(label, value);
    grid.append(group);
  });

  section.append(grid);
  return section;
}

function visibleBacktestSummary(items) {
  const returnValues = items
    .map((item) => comparableNumber(item.totalReturnPercent))
    .filter((value) => value !== null);
  const bestReturn = returnValues.length > 0 ? Math.max(...returnValues) : null;
  const averageReturn =
    returnValues.length > 0
      ? returnValues.reduce((total, value) => total + value, 0) / returnValues.length
      : null;
  return {
    visibleRuns: items.length,
    bestReturn,
    averageReturn,
    profitableRuns: returnValues.filter((value) => value > 0).length,
    runsWithClosedTrades: items.filter((item) => {
      const closedTrades = comparableNumber(item.closedTrades);
      return closedTrades !== null && closedTrades > 0;
    }).length,
  };
}

function renderBacktestVisibleSummary(items) {
  const summary = visibleBacktestSummary(items);
  const grid = document.createElement("dl");
  grid.className = "backtest-visible-summary";
  [
    { label: t("visible_runs_label"), value: formatDecimal(summary.visibleRuns, "0") },
    { label: t("best_visible_return_label"), value: formatPercent(summary.bestReturn) },
    { label: t("average_return_label"), value: formatPercent(summary.averageReturn) },
    { label: t("profitable_runs_label"), value: formatDecimal(summary.profitableRuns, "0") },
    { label: t("with_closed_trades_label"), value: formatDecimal(summary.runsWithClosedTrades, "0") },
  ].forEach((item) => {
    const group = document.createElement("div");
    const label = document.createElement("dt");
    const value = document.createElement("dd");
    label.textContent = item.label;
    value.textContent = item.value;
    group.append(label, value);
    grid.append(group);
  });
  return grid;
}

function isBacktestRunVisibleInHistory(runId, strategyId) {
  const visibleItems = visibleBacktestHistory();
  if (runId !== null && runId !== undefined && runId !== "") {
    return visibleItems.some((item) => String(item.id) === String(runId));
  }
  if (strategyId === null || strategyId === undefined || strategyId === "") return false;
  return visibleItems.some((item) => botIdsEqual(item.strategyId, strategyId));
}

function hasValidComparisonReturn(row) {
  return [
    row?.bestRun?.totalReturnPercent,
    row?.latestRun?.totalReturnPercent,
    row?.bestRun?.totalReturn,
    row?.latestRun?.totalReturn,
  ].some((value) => comparableNumber(value) !== null);
}

function comparisonClosedTrades(row) {
  const bestClosedTrades = comparableNumber(row?.bestRun?.closedTrades);
  if (bestClosedTrades !== null) return bestClosedTrades;
  return comparableNumber(row?.latestRun?.closedTrades);
}

function comparisonBadge(text, variant) {
  const badge = document.createElement("span");
  badge.className = `backtest-comparison-badge ${variant}`;
  badge.textContent = text;
  return badge;
}

function isStrategyAvailableForBacktest(strategyId) {
  if (strategyId === null || strategyId === undefined || strategyId === "") return false;
  return strategies.some((strategy) => botIdsEqual(strategy.id, strategyId));
}

function useStrategyForNewBacktest(strategyId) {
  if (!isStrategyAvailableForBacktest(strategyId)) return;
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
  backtestStrategyId.value = String(strategyId);
  render();
  backtestForm.scrollIntoView({ behavior: "smooth", block: "center" });
  backtestStrategyId.focus({ preventScroll: true });
}

function renderBacktestComparison() {
  backtestComparisonEl.innerHTML = "";

  if (isLoadingBacktestHistory) {
    renderBacktestComparisonState({
      title: t("loading_strategy_comparison"),
      hint: t("loading_strategy_comparison_hint"),
      className: "loading",
    });
    return;
  }

  if (backtestHistoryError) {
    renderBacktestComparisonState({
      title: t("strategy_comparison_error"),
      hint: isBacktestDataIssueMessage(backtestHistoryError)
        ? t("backtest_not_enough_candle_data")
        : backtestHistoryError || t("strategy_comparison_error_hint"),
      className: "error",
    });
    return;
  }

  const rows = backtestComparisonRows();
  if (rows.length === 0) {
    renderBacktestComparisonState({
      title: backtestHistory.length === 0 ? t("no_strategy_comparison") : t("no_comparable_strategy_runs"),
      hint: backtestHistory.length === 0 ? t("no_strategy_comparison_hint") : t("no_comparable_strategy_runs_hint"),
    });
    return;
  }

  const list = document.createElement("div");
  list.className = "backtest-comparison-list";
  const selectedStrategyId = selectedBotStrategyId();
  const hasRankedReturn = rows.some(hasValidComparisonReturn);

  rows.forEach((row, index) => {
    const item = document.createElement("article");
    item.className = "backtest-comparison-item";

    const header = document.createElement("div");
    header.className = "backtest-comparison-item-header";
    const titleGroup = document.createElement("div");
    const title = document.createElement("strong");
    const type = document.createElement("span");
    title.textContent = row.strategy?.name || strategyLabelForHistory(row.strategyId);
    type.textContent = humanizeMessage(strategyTypeForComparison(row.latestRun || row.bestRun, row.strategy), "—");
    titleGroup.append(title, type);
    header.append(titleGroup);

    const latestRun = row.latestRun;
    const bestRun = row.bestRun;
    const closedTradesSource = bestRun?.closedTrades !== null && bestRun?.closedTrades !== undefined ? bestRun : latestRun;
    const qualitySource = latestRun ?? bestRun;
    const badges = document.createElement("div");
    badges.className = "backtest-comparison-badges";
    if (index === 0 && hasRankedReturn && hasValidComparisonReturn(row)) {
      badges.append(comparisonBadge(t("best_performer_badge"), "positive"));
    }
    if (Number(row.runs?.length ?? 0) < 3) {
      badges.append(comparisonBadge(t("needs_more_runs_badge"), "neutral"));
    }
    if (comparisonClosedTrades(row) === 0) {
      badges.append(comparisonBadge(t("no_closed_trades_badge"), "warning"));
    }
    if (botIdsEqual(row.strategyId, selectedStrategyId)) {
      badges.append(comparisonBadge(t("selected_bot_strategy_label"), "selected"));
    }

    const metrics = document.createElement("dl");
    metrics.className = "backtest-history-metrics backtest-comparison-metrics";
    [
      { label: t("recent_runs_label"), value: formatDecimal(row.runs.length, "0") },
      {
        label: t("best_return_label"),
        value: formatPercent(bestRun?.totalReturnPercent),
        className: pnlClass(bestRun?.totalReturnPercent),
      },
      {
        label: t("latest_return_label"),
        value: formatPercent(latestRun?.totalReturnPercent),
        className: pnlClass(latestRun?.totalReturnPercent),
      },
      { label: t("closed_trades_label"), value: formatDecimal(closedTradesSource?.closedTrades) },
      { label: t("win_rate_label"), value: formatPercent(qualitySource?.winRate) },
      { label: t("profit_factor_label"), value: formatRatio(qualitySource?.profitFactor) },
      { label: t("last_backtest_label"), value: formatDateTime(latestRun?.createdAt) },
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

    const actions = document.createElement("div");
    actions.className = "backtest-comparison-actions";
    const latestRunIsVisible = isBacktestRunVisibleInHistory(latestRun?.id, row.strategyId);
    const latestRunButton = document.createElement("button");
    latestRunButton.type = "button";
    latestRunButton.className = "secondary-button backtest-comparison-action";
    latestRunButton.textContent = latestRunIsVisible ? t("view_latest_run") : t("latest_run_not_visible");
    latestRunButton.title = latestRunIsVisible ? t("view_latest_run") : t("latest_run_not_visible_hint");
    latestRunButton.disabled = !latestRunIsVisible;
    if (latestRunIsVisible) {
      latestRunButton.addEventListener("click", () => viewLatestBacktestRun(latestRun?.id, row.strategyId));
    }
    actions.append(latestRunButton);
    const strategyAvailableForBacktest = isStrategyAvailableForBacktest(row.strategyId);
    const useButton = document.createElement("button");
    useButton.type = "button";
    useButton.className = "secondary-button backtest-comparison-action";
    useButton.textContent = t("use_for_new_backtest");
    useButton.title = strategyAvailableForBacktest
      ? t("use_for_new_backtest")
      : t("strategy_not_available_for_backtest");
    useButton.disabled = !strategyAvailableForBacktest;
    if (strategyAvailableForBacktest) {
      useButton.addEventListener("click", () => useStrategyForNewBacktest(row.strategyId));
    }
    actions.append(useButton);

    item.append(header);
    if (badges.childElementCount > 0) item.append(badges);
    item.append(metrics, actions);
    list.append(item);
  });

  backtestComparisonEl.className = "backtest-comparison";
  backtestComparisonEl.append(list);
}

function renderBacktestHistory() {
  renderBacktestHistoryScopeControl();
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

  const historyItems = visibleBacktestHistory();
  if (historyItems.length === 0) {
    backtestHistoryEl.className = "backtest-history empty";
    const title = document.createElement("strong");
    const hint = document.createElement("span");
    title.textContent = t("no_backtests_yet");
    hint.textContent = t("no_backtests_yet_hint");
    backtestHistoryEl.append(title, hint);
    return;
  }

  const fragments = [];
  fragments.push(renderBacktestVisibleSummary(historyItems));
  if (historyItems.length >= 2) {
    const bestRun = selectBestRecentBacktest(historyItems);
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
  historyItems.forEach((item) => {
    const row = document.createElement("li");
    row.className = "backtest-history-item";
    row.dataset.backtestRunId = item.id ?? "";
    row.dataset.strategyId = item.strategyId ?? "";
    const itemKey = backtestHistoryItemKey(item);
    const detailsId = `backtest-details-${itemKey.replace(/[^a-z0-9_-]/gi, "-")}`;
    const detailsExpanded = expandedBacktestDetails.has(itemKey);

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

    const actions = document.createElement("div");
    actions.className = "backtest-history-actions";
    const detailsButton = document.createElement("button");
    detailsButton.type = "button";
    detailsButton.className = "secondary-button backtest-history-detail-toggle";
    detailsButton.textContent = detailsExpanded ? t("hide_details") : t("view_details");
    detailsButton.setAttribute("aria-expanded", String(detailsExpanded));
    detailsButton.setAttribute("aria-controls", detailsId);
    detailsButton.addEventListener("click", () => {
      if (expandedBacktestDetails.has(itemKey)) {
        expandedBacktestDetails.delete(itemKey);
      } else {
        expandedBacktestDetails.add(itemKey);
      }
      render();
    });
    actions.append(detailsButton);

    row.append(header, meta, metrics, actions);
    if (detailsExpanded) {
      const details = renderBacktestHistoryDetails(item);
      details.id = detailsId;
      row.append(details);
    }
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
    strategy_type: "strategy type",
    symbol: "symbol",
    timeframe: "timeframe",
    parameters: "parameters",
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

function parseOptimizationIntegersAtLeast(value, minimum) {
  const values = commaValues(value);
  if (values.length === 0) return null;
  return values.every((item) => parseIntegerAtLeast(item, minimum) !== null) ? values : null;
}

function parseRsiOptimizationValues(value) {
  const values = commaValues(value);
  if (values.length === 0) return null;
  return values.every((item) => parseRsiThresholdParameter(item) !== null) ? values : null;
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

function formatOptimizationPresetValue(value) {
  return Number(value).toFixed(8).replace(/\.?0+$/, "");
}

function optimizationPresetQuantity(parameters) {
  const quantity = parsePositiveParameter(String(parameters?.quantity ?? ""));
  return quantity === null ? null : formatValue(parameters.quantity);
}

function setOptimizationPresetValues({ firstValues, secondValues, thirdValues = [], quantity }) {
  optimizationFirstValues.value = firstValues.join(", ");
  optimizationSecondValues.value = secondValues.join(", ");
  optimizationThirdValues.value = thirdValues.join(", ");
  if (quantity) optimizationQuantity.value = quantity;
  backtestOptimizationTouched = true;
}

function priceThresholdPresetBases() {
  const parameters = selectedBacktestStrategy()?.parameters ?? {};
  const parsedBuyBelow = Number(parameters.buy_below);
  const buyBelow = Number.isFinite(parsedBuyBelow) && parsedBuyBelow > 0 ? parsedBuyBelow : 100;
  const parsedSellAbove = Number(parameters.sell_above);
  const sellAbove =
    Number.isFinite(parsedSellAbove) && parsedSellAbove > buyBelow ? parsedSellAbove : buyBelow * 1.1;
  return { buyBelow, sellAbove, quantity: optimizationPresetQuantity(parameters) };
}

function safePriceThresholdPreset(buyMultipliers, sellMultipliers) {
  const { buyBelow, sellAbove, quantity } = priceThresholdPresetBases();
  const buyValues = buyMultipliers.map((multiplier) => buyBelow * multiplier);
  const maxBuy = Math.max(...buyValues);
  const sellFloor = Math.max(sellAbove, maxBuy * 1.02);
  const sellValues = sellMultipliers.map((multiplier) => Math.max(sellAbove * multiplier, sellFloor));
  return {
    firstValues: buyValues.map(formatOptimizationPresetValue),
    secondValues: sellValues.map(formatOptimizationPresetValue),
    quantity,
  };
}

function applyPriceThresholdPreset(kind) {
  const presets = {
    conservative: safePriceThresholdPreset([0.99, 1], [1, 1.01]),
    balanced: safePriceThresholdPreset([0.98, 1, 1.02], [0.99, 1, 1.02]),
    wide: safePriceThresholdPreset([0.94, 0.98, 1.02], [0.98, 1.03, 1.08]),
  };
  setOptimizationPresetValues(presets[kind] ?? presets.balanced);
}

function applyMovingAveragePreset(kind) {
  const parameters = selectedBacktestStrategy()?.parameters ?? {};
  const quantity = optimizationPresetQuantity(parameters);
  const presets = {
    fast: { firstValues: ["3", "5", "8"], secondValues: ["12", "20", "26"] },
    balanced: { firstValues: ["5", "10", "13"], secondValues: ["20", "30", "50"] },
    slow: { firstValues: ["10", "20", "30"], secondValues: ["50", "100", "150"] },
  };
  setOptimizationPresetValues({ ...(presets[kind] ?? presets.balanced), quantity });
}

function applyRsiPreset(kind) {
  const parameters = selectedBacktestStrategy()?.parameters ?? {};
  const quantity = optimizationPresetQuantity(parameters);
  const presets = {
    standard: {
      firstValues: ["14", "21"],
      secondValues: ["30", "35"],
      thirdValues: ["65", "70"],
    },
    sensitive: {
      firstValues: ["7", "10", "14"],
      secondValues: ["35", "40"],
      thirdValues: ["60", "65"],
    },
    conservative: {
      firstValues: ["14", "21", "28"],
      secondValues: ["20", "25", "30"],
      thirdValues: ["70", "75", "80"],
    },
  };
  const preset = presets[kind] ?? presets.standard;
  setOptimizationPresetValues({
    firstValues: preset.firstValues,
    secondValues: preset.secondValues,
    thirdValues: preset.thirdValues,
    quantity,
  });
}

function applyBollingerPreset(kind) {
  const parameters = selectedBacktestStrategy()?.parameters ?? {};
  const quantity = optimizationPresetQuantity(parameters);
  const presets = {
    standard: { firstValues: ["20", "30"], secondValues: ["2", "2.2"] },
    tight: { firstValues: ["10", "15", "20"], secondValues: ["1.5", "1.8"] },
    wide: { firstValues: ["20", "30", "40"], secondValues: ["2.5", "3"] },
  };
  setOptimizationPresetValues({ ...(presets[kind] ?? presets.standard), quantity });
}

function applyMacdPreset(kind) {
  const parameters = selectedBacktestStrategy()?.parameters ?? {};
  const quantity = optimizationPresetQuantity(parameters);
  const presets = {
    standard: {
      firstValues: ["12", "16"],
      secondValues: ["26", "32"],
      thirdValues: ["9"],
    },
    fast: {
      firstValues: ["5", "8", "10"],
      secondValues: ["13", "21"],
      thirdValues: ["5", "7"],
    },
    slow: {
      firstValues: ["16", "20"],
      secondValues: ["35", "50"],
      thirdValues: ["9", "12"],
    },
  };
  setOptimizationPresetValues({ ...(presets[kind] ?? presets.standard), quantity });
}

function populateOptimizationDefaults() {
  if (backtestOptimizationTouched) return;
  const strategy = selectedBacktestStrategy();
  const parameters = strategy?.parameters ?? {};
  const strategyType = optimizationStrategyType();

  if (strategyType === "moving_average_cross") {
    optimizationFirstValues.value = "5, 10";
    optimizationSecondValues.value = "20, 30";
    optimizationThirdValues.value = "";
    optimizationQuantity.value = formatValue(parameters.quantity, "1");
    return;
  }

  if (strategyType === "rsi_threshold") {
    optimizationFirstValues.value = formatValue(parameters.period, "14, 21");
    optimizationSecondValues.value = formatValue(parameters.oversold, "30, 35");
    optimizationThirdValues.value = formatValue(parameters.overbought, "65, 70");
    optimizationQuantity.value = formatValue(parameters.quantity, "1");
    return;
  }

  if (strategyType === "bollinger_bands") {
    optimizationFirstValues.value = formatValue(parameters.period, "20, 30");
    optimizationSecondValues.value = formatValue(parameters.stddev_multiplier, "2, 2.5");
    optimizationThirdValues.value = "";
    optimizationQuantity.value = formatValue(parameters.quantity, "1");
    return;
  }

  if (strategyType === "macd_crossover") {
    optimizationFirstValues.value = formatValue(parameters.fast_period, "12, 16");
    optimizationSecondValues.value = formatValue(parameters.slow_period, "26, 32");
    optimizationThirdValues.value = formatValue(parameters.signal_period, "9");
    optimizationQuantity.value = formatValue(parameters.quantity, "1");
    return;
  }

  optimizationFirstValues.value = nearbyOptimizationValues(parameters.buy_below, 100);
  optimizationSecondValues.value = nearbyOptimizationValues(parameters.sell_above, 110);
  optimizationThirdValues.value = "";
  optimizationQuantity.value = formatValue(parameters.quantity, "1");
}

function optimizationParameterSets() {
  const strategyType = optimizationStrategyType();
  const quantity = optimizationQuantity.value.trim();

  if (strategyType === "price_threshold") {
    if (parsePositiveParameter(quantity) === null) return { error: t("optimization_positive_numbers") };
    const buyBelowValues = parsePositiveOptimizationValues(optimizationFirstValues.value);
    const sellAboveValues = parsePositiveOptimizationValues(optimizationSecondValues.value);
    if (!buyBelowValues || !sellAboveValues) return { error: t("optimization_positive_numbers") };
    const parameterSets = buyBelowValues.flatMap((buyBelow) =>
      sellAboveValues.map((sellAbove) => ({ buy_below: buyBelow, sell_above: sellAbove, quantity })),
    );
    return parameterSets.length > 50 ? { error: t("optimization_max_sets") } : { parameterSets };
  }

  if (strategyType === "moving_average_cross") {
    if (parsePositiveParameter(quantity) === null) return { error: t("optimization_positive_numbers") };
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

  if (strategyType === "rsi_threshold") {
    const periodValues = parsePositiveOptimizationIntegers(optimizationFirstValues.value);
    const oversoldValues = parseRsiOptimizationValues(optimizationSecondValues.value);
    const overboughtValues = parseRsiOptimizationValues(optimizationThirdValues.value);
    const quantityValues = parsePositiveOptimizationValues(optimizationQuantity.value);
    if (!periodValues || !oversoldValues || !overboughtValues || !quantityValues) {
      return { error: t("optimization_rsi_thresholds_invalid") };
    }
    const parameterSets = periodValues.flatMap((period) =>
      oversoldValues.flatMap((oversold) =>
        overboughtValues.flatMap((overbought) =>
          quantityValues.map((candidateQuantity) => ({
            period,
            oversold,
            overbought,
            quantity: candidateQuantity,
          })),
        ),
      ),
    );
    if (parameterSets.some((parameters) => Number(parameters.oversold) >= Number(parameters.overbought))) {
      return { error: t("optimization_rsi_thresholds_invalid") };
    }
    return parameterSets.length > 50 ? { error: t("optimization_max_sets") } : { parameterSets };
  }

  if (strategyType === "bollinger_bands") {
    const periodValues = parseOptimizationIntegersAtLeast(optimizationFirstValues.value, 2);
    const stddevMultiplierValues = parsePositiveOptimizationValues(optimizationSecondValues.value);
    const quantityValues = parsePositiveOptimizationValues(optimizationQuantity.value);
    if (!periodValues || !stddevMultiplierValues || !quantityValues) {
      return { error: t("optimization_bollinger_invalid") };
    }
    const parameterSets = periodValues.flatMap((period) =>
      stddevMultiplierValues.flatMap((stddevMultiplier) =>
        quantityValues.map((candidateQuantity) => ({
          period,
          stddev_multiplier: stddevMultiplier,
          quantity: candidateQuantity,
        })),
      ),
    );
    return parameterSets.length > 50 ? { error: t("optimization_max_sets") } : { parameterSets };
  }

  if (strategyType === "macd_crossover") {
    const fastPeriodValues = parsePositiveOptimizationIntegers(optimizationFirstValues.value);
    const slowPeriodValues = parsePositiveOptimizationIntegers(optimizationSecondValues.value);
    const signalPeriodValues = parsePositiveOptimizationIntegers(optimizationThirdValues.value);
    const quantityValues = parsePositiveOptimizationValues(optimizationQuantity.value);
    if (!fastPeriodValues || !slowPeriodValues || !signalPeriodValues || !quantityValues) {
      return { error: t("optimization_macd_invalid") };
    }
    const parameterSets = fastPeriodValues.flatMap((fastPeriod) =>
      slowPeriodValues.flatMap((slowPeriod) =>
        signalPeriodValues.flatMap((signalPeriod) =>
          quantityValues.map((candidateQuantity) => ({
            fast_period: fastPeriod,
            slow_period: slowPeriod,
            signal_period: signalPeriod,
            quantity: candidateQuantity,
          })),
        ),
      ),
    );
    if (parameterSets.some((parameters) => Number(parameters.fast_period) >= Number(parameters.slow_period))) {
      return { error: t("optimization_macd_invalid") };
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

  const params = new URLSearchParams({ limit: "20" });

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

async function loadPaperPortfolio({ silent = false } = {}) {
  isLoadingPaperPortfolio = true;
  if (!silent) {
    paperPortfolioError = "";
  }
  render();

  try {
    paperPortfolio = normalizePaperPortfolio(await fetchJson("/api/v1/paper-portfolio"));
    paperPortfolioError = "";
  } catch (error) {
    paperPortfolio = null;
    paperPortfolioError = requestErrorMessage(error, t("paper_portfolio_unavailable"));
  } finally {
    isLoadingPaperPortfolio = false;
    render();
  }
}

function applyPaperPortfolioResult(result) {
  if (result.status === "fulfilled") {
    paperPortfolio = normalizePaperPortfolio(result.value);
    paperPortfolioError = "";
  } else {
    paperPortfolio = null;
    paperPortfolioError = requestErrorMessage(result.reason, t("paper_portfolio_unavailable"));
  }
  isLoadingPaperPortfolio = false;
}

function applyRecentPaperOrdersResult(result) {
  if (result.status === "fulfilled") {
    recentPaperOrders = normalizePaperOrders(result.value);
    recentPaperOrdersError = "";
  } else {
    recentPaperOrders = [];
    recentPaperOrdersError = requestErrorMessage(result.reason, t("recent_paper_orders_unavailable"));
  }
  isLoadingRecentPaperOrders = false;
}

function applyExecutionSafetyResult(result) {
  if (result.status === "fulfilled") {
    executionSafetyStatus = normalizeExecutionSafety(result.value);
    executionSafetyError = "";
  } else {
    executionSafetyStatus = null;
    executionSafetyError = requestErrorMessage(result.reason, t("execution_safety_unavailable"));
  }
  isLoadingExecutionSafety = false;
}

function applyReconciliationWorkerResult(result) {
  if (result.status === "fulfilled") {
    reconciliationWorkerStatus = normalizeReconciliationWorkerStatus(result.value);
    reconciliationWorkerError = "";
  } else {
    reconciliationWorkerStatus = null;
    reconciliationWorkerError = requestErrorMessage(result.reason, t("reconciliation_worker_unavailable"));
  }
  isLoadingReconciliationWorker = false;
}

function applyRecentReconciliationJobsResult(result) {
  if (result.status === "fulfilled") {
    recentReconciliationJobs = normalizeReconciliationJobs(result.value);
    recentReconciliationJobsError = "";
  } else {
    recentReconciliationJobs = [];
    recentReconciliationJobsError = t("recent_reconciliation_jobs_unavailable");
  }
  isLoadingRecentReconciliationJobs = false;
}

function clearRecentPaperOrders() {
  recentPaperOrders = [];
  recentPaperOrdersError = "";
  isLoadingRecentPaperOrders = false;
}

function clearExecutionSafety() {
  executionSafetyStatus = null;
  executionSafetyError = "";
  isLoadingExecutionSafety = false;
}

async function loadReconciliationWorkerStatus({ silent = false } = {}) {
  if (!silent) {
    reconciliationWorkerError = "";
    isLoadingReconciliationWorker = true;
    renderReconciliationWorker();
  }

  const result = await Promise.allSettled([
    fetchJson("/api/v1/execution-reconciliation-worker/status"),
  ]);
  applyReconciliationWorkerResult(result[0]);
  renderReconciliationWorker();
}

async function loadRecentReconciliationJobs({ silent = false } = {}) {
  if (!silent) {
    recentReconciliationJobsError = "";
    isLoadingRecentReconciliationJobs = true;
    renderRecentReconciliationJobs();
  }

  const result = await Promise.allSettled([
    fetchJson("/api/v1/execution-reconciliation-jobs?limit=10"),
  ]);
  applyRecentReconciliationJobsResult(result[0]);
  renderRecentReconciliationJobs();
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

function formatPerformanceReason(reason, decision) {
  if (!reason) return "—";
  return (
    firstRiskMessage(reason) ||
    getDecisionReasonMessage(reason) ||
    formatActivityMessageText(reason, decision ? formatDecisionLabel(decision) : humanizeMessage(reason))
  );
}

function performanceHealthLabel(health) {
  const labels = {
    healthy: "health_healthy",
    inactive: "health_inactive",
    no_activity: "health_no_activity",
    unknown: "health_unknown",
  };
  return t(labels[health] || "health_unknown");
}

function performanceHealthClass(health) {
  if (health === "healthy") return "status-active";
  if (health === "inactive") return "status-paused";
  if (health === "no_activity") return "status-idle";
  return "status-draft";
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
  clearExecutionSafety();
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
  selectedPerformance = null;
  performanceError = "";
  isLoadingPerformance = false;
  clearRecentPaperOrders();
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
    isCreatingStrategy ||
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
    await loadPaperPortfolio({ silent: true });
    if (selectedBotId) {
      await loadSelectedSummary(selectedBotId);
    } else {
      selectedPerformance = null;
      performanceError = "";
      isLoadingPerformance = false;
      clearRecentPaperOrders();
      clearExecutionSafety();
      await loadReconciliationWorkerStatus({ silent: true });
      await loadRecentReconciliationJobs({ silent: true });
      await loadBacktestHistory();
    }
  } catch (error) {
    bots = [];
    selectedBotId = null;
    selectedSummary = null;
    selectedPerformance = null;
    selectedExecutionProfile = null;
    performanceError = "";
    isLoadingPerformance = false;
    clearRecentPaperOrders();
    clearExecutionSafety();
    isLoadingBots = false;
    botListError = requestErrorMessage(error, t("could_not_load_bots"));
    await loadPaperPortfolio({ silent: true });
    await loadReconciliationWorkerStatus({ silent: true });
    await loadRecentReconciliationJobs({ silent: true });
    render();
  }
}

async function refreshSelectedData() {
  const currentBotId = selectedBotId;
  performanceError = "";
  const data = await fetchJson("/api/v1/bots");
  bots = normalizeBotsResponse(data);
  const sortedBotList = sortedBots(bots);

  selectedBotId = chooseSelectedBotId(sortedBotList);

  if (!botIdsEqual(selectedBotId, currentBotId)) {
    clearSelectedBotMessages();
  }

  if (selectedBotId) {
    isLoadingPerformance = true;
    isLoadingPaperPortfolio = true;
    isLoadingRecentPaperOrders = true;
    isLoadingExecutionSafety = true;
    isLoadingReconciliationWorker = true;
    isLoadingRecentReconciliationJobs = true;
    const [
      summaryResult,
      configResult,
      performanceResult,
      portfolioResult,
      ordersResult,
      executionSafetyResult,
      reconciliationWorkerResult,
      recentReconciliationJobsResult,
    ] = await Promise.allSettled([
      fetchJson(`/api/v1/bots/${selectedBotId}/summary`),
      fetchJson(`/api/v1/bots/${selectedBotId}`),
      fetchJson(`/api/v1/bots/${selectedBotId}/performance`),
      fetchJson("/api/v1/paper-portfolio"),
      fetchJson(`/api/v1/bots/${selectedBotId}/orders?limit=10`),
      fetchJson(`/api/v1/bots/${selectedBotId}/execution-safety/status`),
      fetchJson("/api/v1/execution-reconciliation-worker/status"),
      fetchJson("/api/v1/execution-reconciliation-jobs?limit=10"),
    ]);

    applyPaperPortfolioResult(portfolioResult);
    applyRecentPaperOrdersResult(ordersResult);
    applyExecutionSafetyResult(executionSafetyResult);
    applyReconciliationWorkerResult(reconciliationWorkerResult);
    applyRecentReconciliationJobsResult(recentReconciliationJobsResult);

    if (summaryResult.status !== "fulfilled") {
      isLoadingPerformance = false;
      throw summaryResult.reason;
    }
    if (configResult.status !== "fulfilled") {
      isLoadingPerformance = false;
      throw configResult.reason;
    }

    selectedSummary = normalizeSummary(summaryResult.value);
    selectedBotConfig = normalizeBotConfig(configResult.value);
    if (performanceResult.status === "fulfilled") {
      selectedPerformance = normalizePerformance(performanceResult.value);
      performanceError = "";
    } else {
      selectedPerformance = null;
      performanceError = requestErrorMessage(performanceResult.reason, t("bot_performance_unavailable"));
    }
    isLoadingPerformance = false;
    selectedExecutionProfile = await loadExecutionProfile(selectedBotId);
  } else {
    selectedSummary = null;
    isEditBotOpen = false;
    selectedBotConfig = null;
    selectedExecutionProfile = null;
    selectedPerformance = null;
    await loadPaperPortfolio({ silent: true });
    performanceError = "";
    isLoadingPerformance = false;
    clearRecentPaperOrders();
    clearExecutionSafety();
    await loadReconciliationWorkerStatus({ silent: true });
    await loadRecentReconciliationJobs({ silent: true });
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
      isLoadingPerformance = true;
      isLoadingPaperPortfolio = true;
      isLoadingRecentPaperOrders = true;
      isLoadingExecutionSafety = true;
      isLoadingReconciliationWorker = true;
      isLoadingRecentReconciliationJobs = true;
      const [
        summaryResult,
        configResult,
        performanceResult,
        portfolioResult,
        ordersResult,
        executionSafetyResult,
        reconciliationWorkerResult,
        recentReconciliationJobsResult,
      ] = await Promise.allSettled([
        fetchJson(`/api/v1/bots/${selectedBotId}/summary`),
        fetchJson(`/api/v1/bots/${selectedBotId}`),
        fetchJson(`/api/v1/bots/${selectedBotId}/performance`),
        fetchJson("/api/v1/paper-portfolio"),
        fetchJson(`/api/v1/bots/${selectedBotId}/orders?limit=10`),
        fetchJson(`/api/v1/bots/${selectedBotId}/execution-safety/status`),
        fetchJson("/api/v1/execution-reconciliation-worker/status"),
        fetchJson("/api/v1/execution-reconciliation-jobs?limit=10"),
      ]);

      applyPaperPortfolioResult(portfolioResult);
      applyRecentPaperOrdersResult(ordersResult);
      applyExecutionSafetyResult(executionSafetyResult);
      applyReconciliationWorkerResult(reconciliationWorkerResult);
      applyRecentReconciliationJobsResult(recentReconciliationJobsResult);

      if (summaryResult.status !== "fulfilled") {
        isLoadingPerformance = false;
        throw summaryResult.reason;
      }
      if (configResult.status !== "fulfilled") {
        isLoadingPerformance = false;
        throw configResult.reason;
      }

      selectedSummary = normalizeSummary(summaryResult.value);
      selectedBotConfig = normalizeBotConfig(configResult.value);
      if (performanceResult.status === "fulfilled") {
        selectedPerformance = normalizePerformance(performanceResult.value);
        performanceError = "";
      } else {
        selectedPerformance = null;
        performanceError = requestErrorMessage(performanceResult.reason, t("bot_performance_unavailable"));
      }
      isLoadingPerformance = false;
      selectedExecutionProfile = await loadExecutionProfile(selectedBotId);
      summaryError = "";
    } else {
      selectedSummary = null;
      selectedBotConfig = null;
      selectedExecutionProfile = null;
      selectedPerformance = null;
      await loadPaperPortfolio({ silent: true });
      performanceError = "";
      isLoadingPerformance = false;
      clearRecentPaperOrders();
      clearExecutionSafety();
      await loadReconciliationWorkerStatus({ silent: true });
      await loadRecentReconciliationJobs({ silent: true });
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
    isLoadingPerformance = false;
    isLoadingPaperPortfolio = false;
    isLoadingRecentPaperOrders = false;
    isLoadingExecutionSafety = false;
    isLoadingReconciliationWorker = false;
    isLoadingRecentReconciliationJobs = false;
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
    selectedPerformance = null;
    selectedBotConfig = null;
    selectedExecutionProfile = null;
    performanceError = "";
    isLoadingPerformance = false;
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

function createStrategyValidationMessage(error) {
  if (error?.status === 422) {
    return validationErrorsMessage(error?.data?.errors, t("check_strategy_fields"));
  }
  return requestErrorMessage(error, t("create_strategy_failed"));
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

function liveMarketPriceErrorMessage(error) {
  const message = binancePriceErrorMessage(error);
  return message === t("could_not_fetch_binance_price") ? t("live_market_price_error") : message;
}

function liveMarketDirection(item) {
  const price = comparableNumber(item.price);
  const previousPrice = comparableNumber(item.previousPrice);
  if (price === null || previousPrice === null || price === previousPrice) return "flat";
  return price > previousPrice ? "up" : "down";
}

function formatSignedDecimal(value) {
  const parsed = comparableNumber(value);
  if (parsed === null) return "—";
  const prefix = parsed > 0 ? "+" : "";
  return `${prefix}${formatDecimal(parsed)}`;
}

function liveMarketChange(item) {
  const price = comparableNumber(item.price);
  const previousPrice = comparableNumber(item.previousPrice);
  if (price === null || previousPrice === null) return null;
  return price - previousPrice;
}

function liveMarketPercentChange(item) {
  const change = liveMarketChange(item);
  const previousPrice = comparableNumber(item.previousPrice);
  if (change === null || previousPrice === null || previousPrice === 0) return null;
  return (change / previousPrice) * 100;
}

function formatSignedPercent(value) {
  const parsed = comparableNumber(value);
  if (parsed === null) return "—";
  const prefix = parsed > 0 ? "+" : "";
  return `${prefix}${formatPercent(parsed)}`;
}

function liveMarketDirectionLabel(direction) {
  if (direction === "up") return t("live_market_direction_up");
  if (direction === "down") return t("live_market_direction_down");
  return t("live_market_direction_flat");
}

async function fetchLiveMarketPrice(symbol) {
  return fetchJson("/api/v1/market/binance/price", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
}

function updateLiveMarketAutoRefresh() {
  if (liveMarketTimer) {
    clearInterval(liveMarketTimer);
    liveMarketTimer = null;
  }

  if (!liveMarketAutoRefreshEnabled || document.hidden) return;
  liveMarketTimer = setInterval(() => {
    if (!document.hidden) {
      refreshLiveMarket();
    }
  }, LIVE_MARKET_REFRESH_MS);
}

async function refreshLiveMarket() {
  if (isRefreshingLiveMarket || liveMarketSymbols.length === 0) return;
  isRefreshingLiveMarket = true;
  liveMarketSymbols = liveMarketSymbols.map((item) => ({ ...item, isLoading: true, error: "" }));
  render();

  await Promise.all(
    liveMarketSymbols.map(async (item) => {
      try {
        const result = await fetchLiveMarketPrice(item.symbol);
        const symbol = normalizeMarketSymbol(result.symbol || item.symbol);
        const price = result.price ?? null;
        liveMarketSymbols = liveMarketSymbols.map((candidate) =>
          candidate.symbol === item.symbol
            ? {
                ...candidate,
                symbol,
                previousPrice: candidate.price,
                price,
                updatedAt: new Date(),
                isLoading: false,
                error: "",
              }
            : candidate,
        );
      } catch (error) {
        liveMarketSymbols = liveMarketSymbols.map((candidate) =>
          candidate.symbol === item.symbol
            ? {
                ...candidate,
                isLoading: false,
                error: liveMarketPriceErrorMessage(error),
              }
            : candidate,
        );
      }
    }),
  );

  isRefreshingLiveMarket = false;
  render();
}

function addLiveMarketSymbol(event) {
  event.preventDefault();
  const symbol = normalizeMarketSymbol(liveMarketSymbol.value);
  if (!symbol) {
    liveMarketMessage = t("live_market_symbol_required");
    liveMarketMessageType = "error";
    render();
    return;
  }
  if (liveMarketSymbols.some((item) => item.symbol === symbol)) {
    liveMarketMessage = t("live_market_duplicate_symbol", { symbol });
    liveMarketMessageType = "error";
    render();
    return;
  }

  liveMarketSymbols = [...liveMarketSymbols, liveMarketSymbolItem(symbol)];
  persistLiveMarketSymbols();
  liveMarketSymbol.value = "";
  liveMarketMessage = t("live_market_added_symbol", { symbol });
  liveMarketMessageType = "success";
  render();
  refreshLiveMarket();
}

function removeLiveMarketSymbol(symbol) {
  liveMarketSymbols = liveMarketSymbols.filter((item) => item.symbol !== symbol);
  persistLiveMarketSymbols();
  liveMarketMessage = t("live_market_removed_symbol", { symbol });
  liveMarketMessageType = "note";
  render();
}

function candleNumber(...values) {
  for (const value of values) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function normalizeCandle(rawCandle) {
  const source = Array.isArray(rawCandle)
    ? {
        openTime: rawCandle[0],
        open: rawCandle[1],
        high: rawCandle[2],
        low: rawCandle[3],
        close: rawCandle[4],
        volume: rawCandle[5],
        closeTime: rawCandle[6],
      }
    : rawCandle && typeof rawCandle === "object"
      ? rawCandle
      : {};
  const open = candleNumber(source.open, source.open_price, source.o);
  const high = candleNumber(source.high, source.high_price, source.h);
  const low = candleNumber(source.low, source.low_price, source.l);
  const close = candleNumber(source.close, source.close_price, source.c);
  if ([open, high, low, close].some((value) => value === null)) return null;

  return {
    open,
    high: Math.max(high, open, close, low),
    low: Math.min(low, open, close, high),
    close,
    volume: candleNumber(source.volume, source.v),
    time: firstAvailable(
      source.open_time,
      source.openTime,
      source.opened_at,
      source.timestamp,
      source.time,
      source.close_time,
      source.closeTime,
      null,
    ),
  };
}

function normalizeCandleResponse(data) {
  const rawCandles = Array.isArray(data)
    ? data
    : Array.isArray(data?.candles)
      ? data.candles
      : Array.isArray(data?.items)
        ? data.items
        : [];
  return rawCandles.map(normalizeCandle).filter(Boolean);
}

function candleDateRange(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]) - 1;
  const day = Number(match[3]);
  const start = new Date(Date.UTC(year, month, day));
  const end = new Date(Date.UTC(year, month, day + 1));
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
  return {
    start_time: start.toISOString(),
    end_time: end.toISOString(),
  };
}

function candleRequestPayload() {
  const payload = {
    symbol: candleModal.symbol,
    timeframe: candleModal.timeframe,
    limit: candleModal.limit,
  };
  const range = candleDateRange(candleModal.candleDate);
  return range ? { ...payload, ...range } : payload;
}

async function fetchLiveMarketCandles(payload = candleRequestPayload()) {
  return fetchJson("/api/v1/market/binance/candles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function candleTimestamp(candle) {
  const parsed = new Date(candle?.time);
  return Number.isNaN(parsed.getTime()) ? null : parsed.getTime();
}

function candleIdentity(candle) {
  const timestamp = candleTimestamp(candle);
  return timestamp === null ? "" : String(timestamp);
}

function sortCandlesOldestFirst(candles) {
  return [...candles].sort((left, right) => (candleTimestamp(left) ?? 0) - (candleTimestamp(right) ?? 0));
}

function mergeCandleSets(existingCandles, incomingCandles) {
  const byTime = new Map();
  [...existingCandles, ...incomingCandles].forEach((candle) => {
    const key = candleIdentity(candle);
    if (!key) return;
    byTime.set(key, candle);
  });
  return sortCandlesOldestFirst([...byTime.values()]);
}

function oldestLoadedCandle() {
  return candleModal.candles[0] ?? null;
}

function olderCandlesPayload() {
  const oldest = oldestLoadedCandle();
  const timestamp = candleTimestamp(oldest);
  if (timestamp === null) return null;
  return {
    symbol: candleModal.symbol,
    timeframe: candleModal.timeframe,
    limit: Math.min(Math.max(Number(candleModal.limit) || 100, 100), 500),
    end_time: new Date(Math.max(timestamp - 1, 0)).toISOString(),
  };
}

function candleErrorMessage(error) {
  const message = friendlyCandleImportErrorMessage(error);
  return message === t("candle_import_failed") ? t("candle_error") : message;
}

async function refreshCandleModal() {
  if (!candleModal.isOpen || candleModal.isLoading || !candleModal.symbol) return;
  const requestId = candleModal.requestId + 1;
  candleModal = {
    ...candleModal,
    isLoading: true,
    isLoadingOlder: false,
    error: "",
    olderMessage: "",
    requestId,
  };
  renderCandleModal();

  try {
    const result = await fetchLiveMarketCandles();
    if (candleModal.requestId !== requestId) return;
    const candles = normalizeCandleResponse(result);
    const defaultWindow = defaultCandleWindow(candles.length);
    candleModal = {
      ...candleModal,
      candles,
      visibleStart: defaultWindow.start,
      visibleCount: defaultWindow.count || null,
      isLoading: false,
      error: "",
    };
    candleWheelPanRemainder = 0;
  } catch (error) {
    if (candleModal.requestId !== requestId) return;
    candleModal = {
      ...candleModal,
      candles: [],
      visibleStart: 0,
      visibleCount: null,
      isLoading: false,
      error: candleErrorMessage(error),
    };
    candleWheelPanRemainder = 0;
  }
  renderCandleModal();
}

async function loadOlderCandles() {
  if (
    !candleModal.isOpen ||
    candleModal.isLoading ||
    candleModal.isLoadingOlder ||
    candleModal.candles.length === 0 ||
    !candleModal.symbol
  ) {
    return;
  }

  const payload = olderCandlesPayload();
  if (!payload) return;
  const visibleWindow = candleVisibleWindow();
  const visibleFirstKey = candleIdentity(candleModal.candles[visibleWindow.start]);
  candleModal = {
    ...candleModal,
    isLoadingOlder: true,
    olderMessage: t("candle_loading_older"),
  };
  renderCandleModal();

  try {
    const result = await fetchLiveMarketCandles(payload);
    const incomingCandles = normalizeCandleResponse(result);
    const previousCount = candleModal.candles.length;
    const mergedCandles = mergeCandleSets(candleModal.candles, incomingCandles);
    const loadedCount = Math.max(mergedCandles.length - previousCount, 0);
    const anchoredStart = Math.max(
      mergedCandles.findIndex((candle) => candleIdentity(candle) === visibleFirstKey),
      0,
    );
    candleModal = {
      ...candleModal,
      candles: mergedCandles,
      visibleStart: anchoredStart,
      visibleCount: visibleWindow.count,
      isLoadingOlder: false,
      olderMessage: loadedCount > 0
        ? t("candle_older_loaded", { count: loadedCount })
        : t("candle_no_older_loaded"),
    };
    candleWheelPanRemainder = 0;
  } catch (error) {
    candleModal = {
      ...candleModal,
      isLoadingOlder: false,
      olderMessage: candleErrorMessage(error) || t("candle_older_error"),
    };
  }

  renderCandleModal();
}

function openCandleModal(symbol) {
  candleModalPreviousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  candleModal = {
    ...candleModal,
    isOpen: true,
    symbol,
    candles: [],
    visibleStart: 0,
    visibleCount: null,
    error: "",
    olderMessage: "",
    isLoading: false,
    isLoadingOlder: false,
  };
  renderCandleModal();
  candleModalClose.focus();
  refreshCandleModal();
}

function closeCandleModal() {
  if (!candleModal.isOpen) return;
  candleModal = {
    ...candleModal,
    isOpen: false,
    isLoading: false,
    error: "",
    requestId: candleModal.requestId + 1,
  };
  renderCandleModal();
  if (candleModalPreviousFocus?.focus) {
    candleModalPreviousFocus.focus();
  }
  candleModalPreviousFocus = null;
}

function candlePriceRange(candles) {
  const highs = candles.map((item) => item.high);
  const lows = candles.map((item) => item.low);
  const rawMaximum = Math.max(...highs);
  const rawMinimum = Math.min(...lows);
  const rawRange = Math.max(rawMaximum - rawMinimum, Math.abs(rawMaximum) * 0.0001, 1);
  const padding = rawRange * 0.04;
  return {
    maximum: rawMaximum + padding,
    minimum: rawMinimum - padding,
    rangeHigh: rawMaximum,
    rangeLow: rawMinimum,
  };
}

function candleYScale(value, minimum, maximum, plot) {
  const range = Math.max(maximum - minimum, Math.abs(maximum) * 0.0001, 1);
  return plot.top + ((maximum - value) / range) * plot.height;
}

function candleTicks(minimum, maximum, count = 6) {
  const range = Math.max(maximum - minimum, Math.abs(maximum) * 0.0001, 1);
  return Array.from({ length: count }, (_, index) => maximum - (range * index) / (count - 1));
}

function candleTimeLabel(value, timeframe) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  if (timeframe === "1h") {
    const parts = new Intl.DateTimeFormat([], {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      hour12: false,
    }).formatToParts(parsed);
    const byType = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${byType.month}-${byType.day} ${byType.hour}:00`;
  }
  return formatTime(value);
}

function candleTimeTickIndexes(candles, count = 5) {
  if (candles.length <= 1) return [0];
  const tickCount = Math.min(count, candles.length);
  const indexes = new Set();
  for (let index = 0; index < tickCount; index += 1) {
    indexes.add(Math.round((index * (candles.length - 1)) / (tickCount - 1)));
  }
  return [...indexes].sort((left, right) => left - right);
}

function candleNetChangeClass(value) {
  if (value > 0) return "pnl-positive";
  if (value < 0) return "pnl-negative";
  return "pnl-neutral";
}

function renderCandleRangeSummary(candles, range) {
  const first = candles[0];
  const latest = candles[candles.length - 1];
  const netChange = latest.close - first.open;
  const netChangePercent = first.open ? (netChange / first.open) * 100 : null;
  const summary = document.createElement("dl");
  summary.className = "candle-range-summary";
  [
    { label: t("candle_range_high_label"), value: formatDecimal(range.rangeHigh) },
    { label: t("candle_range_low_label"), value: formatDecimal(range.rangeLow) },
    { label: t("candle_first_open_label"), value: formatDecimal(first.open) },
    { label: t("candle_last_close_label"), value: formatDecimal(latest.close) },
    {
      label: t("candle_net_change_label"),
      value: formatSignedDecimal(netChange),
      className: candleNetChangeClass(netChange),
    },
    {
      label: t("candle_net_change_percent_label"),
      value: formatSignedPercent(netChangePercent),
      className: candleNetChangeClass(netChange),
    },
  ].forEach((item) => {
    const group = document.createElement("div");
    const label = document.createElement("dt");
    const value = document.createElement("dd");
    label.textContent = item.label;
    value.textContent = item.value;
    if (item.className) value.classList.add(item.className);
    group.append(label, value);
    summary.append(group);
  });
  candleChart.append(summary);
}

function candleMinimumVisibleCount(total) {
  return Math.min(10, total);
}

function defaultCandleVisibleCount(total) {
  if (total <= 0) return 0;
  if (total <= 35) return total;
  if (total <= 60) return Math.min(total, 34);
  return Math.min(total, Math.max(candleMinimumVisibleCount(total), Math.round(total * 0.58)));
}

function defaultCandleWindow(total) {
  const count = defaultCandleVisibleCount(total);
  return {
    start: Math.max(total - count, 0),
    count,
  };
}

function normalizedCandleWindow(total, start = candleModal.visibleStart, count = candleModal.visibleCount) {
  if (total <= 0) return { start: 0, count: 0 };
  const safeCount = Math.min(total, Math.max(candleMinimumVisibleCount(total), Number(count) || total));
  const safeStart = Math.min(Math.max(Number(start) || 0, 0), Math.max(total - safeCount, 0));
  return { start: safeStart, count: safeCount };
}

function candleVisibleWindow() {
  const total = candleModal.candles.length;
  return normalizedCandleWindow(total);
}

function visibleCandleSet() {
  const window = candleVisibleWindow();
  return candleModal.candles.slice(window.start, window.start + window.count);
}

function setCandleWindow(start, count) {
  const window = normalizedCandleWindow(candleModal.candles.length, start, count);
  candleModal = {
    ...candleModal,
    visibleStart: window.start,
    visibleCount: window.count || null,
  };
}

function resetCandleWindow() {
  const window = defaultCandleWindow(candleModal.candles.length);
  candleWheelPanRemainder = 0;
  setCandleWindow(window.start, window.count);
}

function panCandleWindowByCandles(deltaCandles) {
  const window = candleVisibleWindow();
  if (!canPanCandleWindow()) return false;
  const nextStart = window.start + deltaCandles;
  if (nextStart < 0 && window.start === 0) {
    loadOlderCandles();
    return false;
  }
  setCandleWindow(nextStart, window.count);
  return candleModal.visibleStart !== window.start;
}

function panCandleWindow(direction) {
  const total = candleModal.candles.length;
  const window = candleVisibleWindow();
  if (!total || window.count >= total) return;
  const shift = Math.max(1, Math.round(window.count * 0.5));
  if (panCandleWindowByCandles(direction * shift)) {
    renderCandleModal();
  }
}

function canPanCandleWindow() {
  const window = candleVisibleWindow();
  return candleModal.candles.length > 0 && window.count < candleModal.candles.length;
}

function zoomCandleWindow(delta) {
  const total = candleModal.candles.length;
  if (!total) return;
  const window = candleVisibleWindow();
  const nextCount = delta < 0
    ? Math.max(candleMinimumVisibleCount(total), Math.round(window.count * 0.78))
    : Math.min(total, Math.round(window.count / 0.78));
  if (nextCount === window.count) return;
  const center = window.start + window.count / 2;
  candleWheelPanRemainder = 0;
  setCandleWindow(Math.round(center - nextCount / 2), nextCount);
  renderCandleModal();
}

function candleChartInteractionWidth() {
  return Math.max(candleChart.getBoundingClientRect().width, 240);
}

function candlePanDistanceToShift(pixelDelta, visibleCount = candleVisibleWindow().count) {
  const width = candleChartInteractionWidth();
  const candleWidth = width / Math.max(visibleCount, 1);
  const rawShift = pixelDelta / Math.max(candleWidth, 10);
  if (Math.abs(rawShift) < 0.5) return 0;
  return Math.trunc(rawShift);
}

function panCandleWindowByWheel(delta) {
  const window = candleVisibleWindow();
  const width = candleChartInteractionWidth();
  const candleWidth = width / Math.max(window.count, 1);
  candleWheelPanRemainder += delta / Math.max(candleWidth, 10);
  const shift = Math.trunc(candleWheelPanRemainder);
  if (!shift) return false;
  candleWheelPanRemainder -= shift;
  return panCandleWindowByCandles(shift);
}

function finishCandleDrag(pointerId = null) {
  if (!candleDragState) return;
  if (pointerId !== null && candleDragState.pointerId !== pointerId) return;
  candleDragState = null;
  candleChart.classList.remove("is-panning");
  hideCandleHover();
}

function hideCandleHover() {
  candleChart.querySelector(".candle-hover-tooltip")?.remove();
  candleChart.querySelector(".candle-hover-guide")?.remove();
}

function candleTooltipRows(candle) {
  return [
    { label: t("candle_time_label"), value: formatDateTime(candle.time) },
    { label: t("candle_open_label"), value: formatDecimal(candle.open) },
    { label: t("candle_high_label"), value: formatDecimal(candle.high) },
    { label: t("candle_low_label"), value: formatDecimal(candle.low) },
    { label: t("candle_close_label"), value: formatDecimal(candle.close) },
    { label: t("candle_volume_label"), value: formatDecimal(candle.volume) },
  ];
}

function showCandleHover(event) {
  if (candleDragState || candleModal.isLoading || candleModal.isLoadingOlder) {
    hideCandleHover();
    return;
  }

  const svg = candleChart.querySelector(".candle-chart-svg");
  const candles = visibleCandleSet();
  if (!svg || candles.length === 0) {
    hideCandleHover();
    return;
  }

  const svgRect = svg.getBoundingClientRect();
  const chartRect = candleChart.getBoundingClientRect();
  const scaleX = CANDLE_CHART_WIDTH / Math.max(svgRect.width, 1);
  const svgX = (event.clientX - svgRect.left) * scaleX;
  if (
    svgX < CANDLE_CHART_PLOT.left ||
    svgX > CANDLE_CHART_WIDTH - CANDLE_CHART_PLOT.right ||
    event.clientY < svgRect.top ||
    event.clientY > svgRect.bottom
  ) {
    hideCandleHover();
    return;
  }

  const step = CANDLE_CHART_PLOT.width / Math.max(candles.length, 1);
  const index = Math.min(
    Math.max(Math.floor((svgX - CANDLE_CHART_PLOT.left) / step), 0),
    candles.length - 1,
  );
  const candle = candles[index];
  const candleX = CANDLE_CHART_PLOT.left + step * index + step / 2;
  const guideLeft = svgRect.left - chartRect.left + (candleX / CANDLE_CHART_WIDTH) * svgRect.width;
  const guideTop = svgRect.top - chartRect.top + (CANDLE_CHART_PLOT.top / CANDLE_CHART_HEIGHT) * svgRect.height;
  const guideHeight = (CANDLE_CHART_PLOT.height / CANDLE_CHART_HEIGHT) * svgRect.height;

  let guide = candleChart.querySelector(".candle-hover-guide");
  if (!guide) {
    guide = document.createElement("span");
    guide.className = "candle-hover-guide";
    candleChart.append(guide);
  }
  guide.style.left = `${guideLeft}px`;
  guide.style.top = `${guideTop}px`;
  guide.style.height = `${guideHeight}px`;

  let tooltip = candleChart.querySelector(".candle-hover-tooltip");
  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.className = "candle-hover-tooltip";
    candleChart.append(tooltip);
  }
  tooltip.innerHTML = candleTooltipRows(candle)
    .map((row) => `<span>${row.label}</span><strong>${row.value}</strong>`)
    .join("");

  const preferredLeft = event.clientX - chartRect.left + 12;
  const preferredTop = event.clientY - chartRect.top + 12;
  const tooltipWidth = tooltip.offsetWidth || 180;
  const tooltipHeight = tooltip.offsetHeight || 150;
  const left = Math.min(Math.max(preferredLeft, 8), Math.max(chartRect.width - tooltipWidth - 8, 8));
  const top = Math.min(Math.max(preferredTop, 8), Math.max(chartRect.height - tooltipHeight - 8, 8));
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function renderCandleChart(candles) {
  hideCandleHover();
  candleChart.innerHTML = "";
  if (candles.length === 0) return;

  const width = CANDLE_CHART_WIDTH;
  const height = CANDLE_CHART_HEIGHT;
  const plot = CANDLE_CHART_PLOT;
  const range = candlePriceRange(candles);
  const { minimum, maximum } = range;
  const step = plot.width / Math.max(candles.length, 1);
  const bodyWidth = Math.max(3, Math.min(10, step * 0.58));
  const namespace = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(namespace, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", t("candle_chart_label"));
  svg.classList.add("candle-chart-svg");

  renderCandleRangeSummary(candles, range);

  candleTicks(range.rangeLow, range.rangeHigh).forEach((tick) => {
    const y = candleYScale(tick, minimum, maximum, plot);
    const line = document.createElementNS(namespace, "line");
    line.setAttribute("x1", String(plot.left));
    line.setAttribute("x2", String(width - plot.right));
    line.setAttribute("y1", String(y));
    line.setAttribute("y2", String(y));
    line.classList.add("candle-grid-line");
    svg.append(line);

    const label = document.createElementNS(namespace, "text");
    label.setAttribute("x", String(width - plot.right + 9));
    label.setAttribute("y", String(y));
    label.setAttribute("dominant-baseline", "middle");
    label.classList.add("candle-axis-label", "candle-y-axis-label");
    label.textContent = formatDecimal(tick);
    svg.append(label);
  });

  const yAxis = document.createElementNS(namespace, "line");
  yAxis.setAttribute("x1", String(width - plot.right));
  yAxis.setAttribute("x2", String(width - plot.right));
  yAxis.setAttribute("y1", String(plot.top));
  yAxis.setAttribute("y2", String(plot.top + plot.height));
  yAxis.classList.add("candle-axis-line");
  svg.append(yAxis);

  const xAxis = document.createElementNS(namespace, "line");
  xAxis.setAttribute("x1", String(plot.left));
  xAxis.setAttribute("x2", String(width - plot.right));
  xAxis.setAttribute("y1", String(plot.top + plot.height));
  xAxis.setAttribute("y2", String(plot.top + plot.height));
  xAxis.classList.add("candle-axis-line");
  svg.append(xAxis);

  candleTimeTickIndexes(candles).forEach((index) => {
    const candle = candles[index];
    const labelText = candleTimeLabel(candle.time, candleModal.timeframe);
    if (!labelText) return;
    const x = plot.left + step * index + step / 2;
    const tick = document.createElementNS(namespace, "line");
    tick.setAttribute("x1", String(x));
    tick.setAttribute("x2", String(x));
    tick.setAttribute("y1", String(plot.top + plot.height));
    tick.setAttribute("y2", String(plot.top + plot.height + 5));
    tick.classList.add("candle-axis-line");
    svg.append(tick);

    const label = document.createElementNS(namespace, "text");
    label.setAttribute("x", String(x));
    label.setAttribute("y", String(plot.top + plot.height + 22));
    label.setAttribute("text-anchor", "middle");
    label.classList.add("candle-axis-label", "candle-x-axis-label");
    label.textContent = labelText;
    svg.append(label);
  });

  candles.forEach((candle, index) => {
    const x = plot.left + step * index + step / 2;
    const highY = candleYScale(candle.high, minimum, maximum, plot);
    const lowY = candleYScale(candle.low, minimum, maximum, plot);
    const openY = candleYScale(candle.open, minimum, maximum, plot);
    const closeY = candleYScale(candle.close, minimum, maximum, plot);
    const isUp = candle.close >= candle.open;

    const wick = document.createElementNS(namespace, "line");
    wick.setAttribute("x1", String(x));
    wick.setAttribute("x2", String(x));
    wick.setAttribute("y1", String(highY));
    wick.setAttribute("y2", String(lowY));
    wick.classList.add("candle-wick", isUp ? "up" : "down");
    svg.append(wick);

    const body = document.createElementNS(namespace, "rect");
    body.setAttribute("x", String(x - bodyWidth / 2));
    body.setAttribute("y", String(Math.min(openY, closeY)));
    body.setAttribute("width", String(bodyWidth));
    body.setAttribute("height", String(Math.max(Math.abs(closeY - openY), 2)));
    body.classList.add("candle-body", isUp ? "up" : "down");
    svg.append(body);
  });

  candleChart.append(svg);
}

function renderCandleSummary(candles) {
  candleSummary.innerHTML = "";
  if (candles.length === 0) return;
  const latest = candles[candles.length - 1];
  [
    { label: t("candle_open_label"), value: formatDecimal(latest.open) },
    { label: t("candle_high_label"), value: formatDecimal(latest.high) },
    { label: t("candle_low_label"), value: formatDecimal(latest.low) },
    { label: t("candle_close_label"), value: formatDecimal(latest.close) },
    { label: t("candle_volume_label"), value: formatDecimal(latest.volume) },
    { label: t("candle_time_label"), value: formatDateTime(latest.time) },
  ].forEach((item) => {
    const group = document.createElement("div");
    const label = document.createElement("dt");
    const value = document.createElement("dd");
    label.textContent = item.label;
    value.textContent = item.value;
    group.append(label, value);
    candleSummary.append(group);
  });
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

function resetCreateStrategyForm() {
  createStrategyName.value = "";
  createStrategySymbol.value = "BTCUSDT";
  createStrategyTimeframe.value = "1m";
  createStrategyType.value = "price_threshold";
  populateCreateStrategyParameters("price_threshold");
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

async function submitCreateStrategy(event) {
  event.preventDefault();
  if (isCreatingStrategy) return;

  const validationError = validateCreateStrategyForm();
  if (validationError) {
    createStrategyMessage = validationError;
    createStrategyMessageType = "error";
    isCreateStrategyOpen = true;
    render();
    return;
  }

  isCreatingStrategy = true;
  createStrategyMessage = "";
  createStrategyMessageType = "";
  render();

  try {
    const createdStrategy = await fetchJson("/api/v1/strategies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(createStrategyPayload()),
    });
    await loadStrategies();
    await refreshDashboardData();
    createStrategyMessage = t("create_strategy_success", {
      name: createdStrategy?.name || t("unnamed_strategy"),
    });
    createStrategyMessageType = "success";
    isCreateStrategyOpen = true;
    resetCreateStrategyForm();
  } catch (error) {
    createStrategyMessage = createStrategyValidationMessage(error);
    createStrategyMessageType = "error";
    isCreateStrategyOpen = true;
  } finally {
    isCreatingStrategy = false;
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
    } else {
      await loadPaperPortfolio({ silent: true });
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
  performanceError = "";
  actionMessage = "";
  actionMessageType = "";
  isLoadingSummary = true;
  isLoadingPerformance = true;
  isLoadingPaperPortfolio = true;
  isLoadingRecentPaperOrders = true;
  isLoadingExecutionSafety = true;
  isLoadingReconciliationWorker = true;
  isLoadingRecentReconciliationJobs = true;
  selectedSummary = null;
  selectedPerformance = null;
  selectedBotConfig = null;
  selectedExecutionProfile = null;
  render();

  try {
    const [
      summaryResult,
      configResult,
      profileResult,
      performanceResult,
      portfolioResult,
      ordersResult,
      executionSafetyResult,
      reconciliationWorkerResult,
      recentReconciliationJobsResult,
    ] = await Promise.allSettled([
      fetchJson(`/api/v1/bots/${botId}/summary`),
      fetchJson(`/api/v1/bots/${botId}`),
      fetchJson(`/api/v1/bots/${botId}/execution-profile`),
      fetchJson(`/api/v1/bots/${botId}/performance`),
      fetchJson("/api/v1/paper-portfolio"),
      fetchJson(`/api/v1/bots/${botId}/orders?limit=10`),
      fetchJson(`/api/v1/bots/${botId}/execution-safety/status`),
      fetchJson("/api/v1/execution-reconciliation-worker/status"),
      fetchJson("/api/v1/execution-reconciliation-jobs?limit=10"),
    ]);

    applyPaperPortfolioResult(portfolioResult);
    applyRecentPaperOrdersResult(ordersResult);
    applyExecutionSafetyResult(executionSafetyResult);
    applyReconciliationWorkerResult(reconciliationWorkerResult);
    applyRecentReconciliationJobsResult(recentReconciliationJobsResult);

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
    if (performanceResult.status === "fulfilled") {
      selectedPerformance = normalizePerformance(performanceResult.value);
    } else {
      performanceError = requestErrorMessage(performanceResult.reason, t("bot_performance_unavailable"));
    }
  } catch (error) {
    selectedSummary = null;
    selectedPerformance = null;
    selectedBotConfig = null;
    selectedExecutionProfile = null;
    clearRecentPaperOrders();
    clearExecutionSafety();
    summaryError = requestErrorMessage(error, t("could_not_load_bot_details"));
  } finally {
    isLoadingSummary = false;
    isLoadingPerformance = false;
    isLoadingPaperPortfolio = false;
    isLoadingRecentPaperOrders = false;
    isLoadingExecutionSafety = false;
    isLoadingReconciliationWorker = false;
    isLoadingRecentReconciliationJobs = false;
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

function renderCreateStrategyTypeOptions() {
  const selectedType = normalizeStrategyType(createStrategyType.value || "price_threshold");
  createStrategyType.innerHTML = CREATE_STRATEGY_TYPES.map(
    (strategyType) =>
      `<option value="${strategyType}"${strategyType === selectedType ? " selected" : ""}>${humanizeMessage(
        strategyType,
      )}</option>`,
  ).join("");
  createStrategyType.value = CREATE_STRATEGY_TYPES.includes(selectedType) ? selectedType : "price_threshold";
}

function renderCreateStrategyForm() {
  createStrategyForm.setAttribute("data-open", String(isCreateStrategyOpen));
  toggleCreateStrategy.textContent = isCreateStrategyOpen ? t("close") : t("create_strategy");
  toggleCreateStrategy.disabled = isCreatingStrategy;
  createStrategySubmit.textContent = isCreatingStrategy ? t("creating_strategy") : t("save_strategy");
  createStrategySubmit.disabled = isCreatingStrategy;
  createStrategyCancel.textContent = t("cancel");
  createStrategyCancel.disabled = isCreatingStrategy;
  renderCreateStrategyTypeOptions();

  const fields = createStrategyParameterFields();
  [createStrategyParamOne, createStrategyParamTwo, createStrategyParamThree, createStrategyParamFour].forEach(
    (input) => {
      input.disabled = isCreatingStrategy;
      input.inputMode = "decimal";
    },
  );
  fields.forEach((field) => {
    field.labelEl.textContent = field.label;
    field.input.name = field.key;
    field.input.inputMode = field.key.includes("window") || field.key === "period" ? "numeric" : "decimal";
  });
  createStrategyParamFourField.hidden = fields.length < 4;
  createStrategyName.disabled = isCreatingStrategy;
  createStrategySymbol.disabled = isCreatingStrategy;
  createStrategyTimeframe.disabled = isCreatingStrategy;
  createStrategyType.disabled = isCreatingStrategy;
  createStrategyMessageEl.textContent = createStrategyMessage;
  createStrategyMessageEl.className = createStrategyMessageType
    ? `form-message ${createStrategyMessageType}`
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

function renderBotPerformance() {
  botPerformanceContent.innerHTML = "";

  if (!selectedBotId) {
    botPerformanceContent.textContent = t("bot_performance_select_bot");
    botPerformanceContent.className = "bot-performance-content empty";
    return;
  }

  if (isLoadingPerformance && !selectedPerformance) {
    botPerformanceContent.textContent = t("bot_performance_loading");
    botPerformanceContent.className = "bot-performance-content empty loading";
    return;
  }

  if (performanceError && !selectedPerformance) {
    botPerformanceContent.textContent = performanceError;
    botPerformanceContent.className = "bot-performance-content empty error";
    return;
  }

  if (!selectedPerformance) {
    botPerformanceContent.textContent = t("bot_performance_unavailable");
    botPerformanceContent.className = "bot-performance-content empty";
    return;
  }

  const performance = selectedPerformance;
  const decisionLabel = performance.lastDecision
    ? formatDecisionLabel(performance.lastDecision)
    : "—";
  const rows = [
    {
      label: t("health_label"),
      value: performanceHealthLabel(performance.health),
      valueClass: `status-pill performance-health ${performanceHealthClass(performance.health)}`,
    },
    { label: t("latest_price_label"), value: formatDecimal(performance.latestMarketPrice) },
    { label: t("current_position_qty_label"), value: formatDecimal(performance.currentPositionQuantity) },
    { label: t("last_decision_label"), value: decisionLabel },
    {
      label: t("decision_reason_label"),
      value: formatPerformanceReason(performance.lastDecisionReason, performance.lastDecision),
      className: "performance-wide",
    },
    { label: t("last_event_time_label"), value: formatDateTime(performance.lastRunEventAt) },
    { label: t("total_event_count_label"), value: formatDecimal(performance.recentRunEventCount) },
    { label: t("buy_signal_count_label"), value: formatDecimal(performance.buyDecisionCount) },
    { label: t("sell_signal_count_label"), value: formatDecimal(performance.sellDecisionCount) },
    { label: t("hold_signal_count_label"), value: formatDecimal(performance.holdDecisionCount) },
    { label: t("risk_blocked_count_label"), value: formatDecimal(performance.riskBlockedEventCount) },
    { label: t("order_filled_count_label"), value: formatDecimal(performance.filledOrderEventCount) },
    {
      label: t("realized_pnl_label"),
      value: formatPnlDecimal(performance.realizedPnl),
      valueClass: pnlClass(performance.realizedPnl),
    },
    {
      label: t("unrealized_pnl_label"),
      value: formatPnlDecimal(performance.unrealizedPnl),
      valueClass: pnlClass(performance.unrealizedPnl),
    },
  ];

  const grid = document.createElement("dl");
  grid.className = "bot-performance-grid";
  rows.forEach((item) => {
    const row = document.createElement("div");
    const label = document.createElement("dt");
    const value = document.createElement("dd");
    if (item.className) row.className = item.className;
    label.textContent = item.label;
    value.textContent = item.value;
    if (item.valueClass) value.className = item.valueClass;
    row.append(label, value);
    grid.append(row);
  });

  botPerformanceContent.className = "bot-performance-content";
  botPerformanceContent.append(grid);

  if (Number(performance.recentRunEventCount) === 0) {
    const empty = document.createElement("p");
    empty.className = "bot-performance-note";
    empty.textContent = t("bot_performance_no_activity");
    botPerformanceContent.append(empty);
  }

  if (performanceError) {
    const error = document.createElement("p");
    error.className = "bot-performance-note error";
    error.textContent = performanceError;
    botPerformanceContent.append(error);
  }
}

function appendMetric(grid, item) {
  const row = document.createElement("div");
  const label = document.createElement("dt");
  const value = document.createElement("dd");
  if (item.className) row.className = item.className;
  label.textContent = item.label;
  value.textContent = item.value;
  if (item.valueClass) value.className = item.valueClass;
  row.append(label, value);
  grid.append(row);
}

function renderPaperPortfolio() {
  paperPortfolioContent.innerHTML = "";

  if (isLoadingPaperPortfolio && !paperPortfolio) {
    paperPortfolioContent.textContent = t("paper_portfolio_loading");
    paperPortfolioContent.className = "paper-portfolio-content empty loading";
    return;
  }

  if (paperPortfolioError && !paperPortfolio) {
    paperPortfolioContent.textContent = paperPortfolioError;
    paperPortfolioContent.className = "paper-portfolio-content empty error";
    return;
  }

  if (!paperPortfolio) {
    paperPortfolioContent.textContent = t("paper_portfolio_unavailable");
    paperPortfolioContent.className = "paper-portfolio-content empty";
    return;
  }

  const currency = paperPortfolio.accountCurrency || "USDT";
  const summaryRows = [
    { label: t("starting_balance_label"), value: formatCompactMoney(paperPortfolio.startingBalance, currency) },
    { label: t("cash_balance_label"), value: formatCompactMoney(paperPortfolio.cashBalance, currency) },
    { label: t("positions_value_label"), value: formatCompactMoney(paperPortfolio.positionsMarketValue, currency) },
    { label: t("total_equity_label"), value: formatCompactMoney(paperPortfolio.totalEquity, currency) },
    {
      label: t("realized_pnl_label"),
      value: formatCompactPnlMoney(paperPortfolio.totalRealizedPnl, currency),
      valueClass: pnlClass(paperPortfolio.totalRealizedPnl),
    },
    {
      label: t("unrealized_pnl_label"),
      value: formatCompactPnlMoney(paperPortfolio.totalUnrealizedPnl, currency),
      valueClass: pnlClass(paperPortfolio.totalUnrealizedPnl),
    },
    { label: t("open_positions_label"), value: formatDecimal(paperPortfolio.openPositionCount, "0") },
  ];

  const summaryGrid = document.createElement("dl");
  summaryGrid.className = "paper-portfolio-summary";
  summaryRows.forEach((item) => appendMetric(summaryGrid, item));

  paperPortfolioContent.className = "paper-portfolio-content";
  paperPortfolioContent.append(summaryGrid);

  if (!paperPortfolio.updatedAt && Number(paperPortfolio.openPositionCount || 0) === 0) {
    const emptyNote = document.createElement("p");
    emptyNote.className = "paper-portfolio-note";
    emptyNote.textContent = t("paper_portfolio_empty");
    paperPortfolioContent.append(emptyNote);
  }

  const positionsSection = document.createElement("div");
  positionsSection.className = "paper-portfolio-positions";

  const positionsHeading = document.createElement("h3");
  positionsHeading.textContent = t("open_positions_label");
  positionsSection.append(positionsHeading);

  if (!paperPortfolio.positions.length) {
    const empty = document.createElement("p");
    empty.className = "paper-portfolio-note";
    empty.textContent = t("paper_portfolio_no_open_positions");
    positionsSection.append(empty);
    paperPortfolioContent.append(positionsSection);
    return;
  }

  const list = document.createElement("div");
  list.className = "paper-portfolio-position-list";

  paperPortfolio.positions.forEach((position) => {
    const item = document.createElement("article");
    item.className = "paper-portfolio-position";

    const header = document.createElement("div");
    header.className = "paper-portfolio-position-header";
    const symbol = document.createElement("strong");
    symbol.textContent = formatValue(position.symbol);
    header.append(symbol);
    if (!position.priceAvailable) {
      const badge = document.createElement("span");
      badge.className = "paper-portfolio-price-status";
      badge.textContent = t("price_unavailable");
      header.append(badge);
    }

    const metrics = document.createElement("dl");
    metrics.className = "paper-portfolio-position-grid";
    const marketPrice = position.priceAvailable
      ? formatMoney(position.latestMarketPrice, currency)
      : t("price_unavailable");
    const valuation = (value) => (position.priceAvailable ? formatMoney(value, currency) : "—");
    const pnlValue = (value) => (position.priceAvailable ? formatPnlMoney(value, currency) : "—");
    const percentValue = position.priceAvailable ? formatPercent(position.unrealizedPnlPercent) : "—";

    [
      { label: t("quantity"), value: formatDecimal(position.quantity) },
      { label: t("average_entry_label"), value: formatMoney(position.averageEntryPrice, currency) },
      { label: t("latest_price_label"), value: marketPrice },
      { label: t("market_value_label"), value: valuation(position.marketValue) },
      {
        label: t("realized_pnl_label"),
        value: formatPnlMoney(position.realizedPnl, currency),
        valueClass: pnlClass(position.realizedPnl),
      },
      {
        label: t("unrealized_pnl_label"),
        value: pnlValue(position.unrealizedPnl),
        valueClass: position.priceAvailable ? pnlClass(position.unrealizedPnl) : "pnl-neutral",
      },
      {
        label: t("unrealized_pnl_percent_label"),
        value: percentValue,
        valueClass: position.priceAvailable ? pnlClass(position.unrealizedPnlPercent) : "pnl-neutral",
      },
    ].forEach((metric) => appendMetric(metrics, metric));

    item.append(header, metrics);
    list.append(item);
  });

  positionsSection.append(list);
  paperPortfolioContent.append(positionsSection);

  if (paperPortfolioError) {
    const error = document.createElement("p");
    error.className = "paper-portfolio-note error";
    error.textContent = paperPortfolioError;
    paperPortfolioContent.append(error);
  }
}

function orderSideLabel(side) {
  const normalized = normalizeStrategyType(side);
  if (normalized === "buy") return t("order_side_buy");
  if (normalized === "sell") return t("order_side_sell");
  return formatValue(side);
}

function orderSideClass(side) {
  const normalized = normalizeStrategyType(side);
  if (normalized === "buy") return "recent-order-side buy";
  if (normalized === "sell") return "recent-order-side sell";
  return "recent-order-side";
}

function orderStatusLabel(status, reason = "") {
  const normalized = normalizeStrategyType(status);
  const normalizedReason = normalizeStrategyType(reason);
  if (normalizedReason.includes("blocked")) return t("order_status_blocked");
  const labels = {
    created: "order_status_created",
    submitted: "order_status_submitted",
    filled: "order_status_filled",
    rejected: "order_status_rejected",
    cancelled: "order_status_cancelled",
    pending: "order_status_pending",
  };
  return t(labels[normalized] || "order_status_unknown");
}

function orderStatusClass(status, reason = "") {
  const normalized = normalizeStrategyType(status);
  const normalizedReason = normalizeStrategyType(reason);
  if (normalizedReason.includes("blocked")) return "recent-order-status blocked";
  if (normalized === "filled") return "recent-order-status filled";
  if (normalized === "rejected" || normalized === "cancelled") return "recent-order-status rejected";
  if (normalized === "created" || normalized === "submitted" || normalized === "pending") {
    return "recent-order-status pending";
  }
  return "recent-order-status";
}

function orderReason(order) {
  return firstAvailable(order.rejectionReason, order.decisionReason, "");
}

function orderFilledQuantity(order) {
  if (!Array.isArray(order.fills) || order.fills.length === 0) return null;
  let hasQuantity = false;
  const total = order.fills.reduce((sum, fill) => {
    const quantity = Number(fill.fillQuantity);
    if (!Number.isFinite(quantity)) return sum;
    hasQuantity = true;
    return sum + quantity;
  }, 0);
  return hasQuantity ? total : null;
}

function orderAverageFillPrice(order) {
  if (!Array.isArray(order.fills) || order.fills.length === 0) return null;
  let totalQuantity = 0;
  let totalNotional = 0;
  order.fills.forEach((fill) => {
    const quantity = Number(fill.fillQuantity);
    const price = Number(fill.fillPrice);
    if (Number.isFinite(quantity) && Number.isFinite(price) && quantity > 0) {
      totalQuantity += quantity;
      totalNotional += quantity * price;
    }
  });
  if (totalQuantity <= 0) return null;
  return totalNotional / totalQuantity;
}

function renderRecentPaperOrders() {
  recentPaperOrdersContent.innerHTML = "";

  if (!selectedBotId) {
    recentPaperOrdersContent.textContent = t("recent_paper_orders_select_bot");
    recentPaperOrdersContent.className = "recent-paper-orders-content empty";
    return;
  }

  if (isLoadingRecentPaperOrders && recentPaperOrders.length === 0) {
    recentPaperOrdersContent.textContent = t("recent_paper_orders_loading");
    recentPaperOrdersContent.className = "recent-paper-orders-content empty loading";
    return;
  }

  if (recentPaperOrdersError && recentPaperOrders.length === 0) {
    recentPaperOrdersContent.textContent = recentPaperOrdersError;
    recentPaperOrdersContent.className = "recent-paper-orders-content empty error";
    return;
  }

  if (recentPaperOrders.length === 0) {
    recentPaperOrdersContent.textContent = t("recent_paper_orders_empty");
    recentPaperOrdersContent.className = "recent-paper-orders-content empty";
    return;
  }

  recentPaperOrdersContent.className = "recent-paper-orders-content";
  const list = document.createElement("div");
  list.className = "recent-paper-orders-list";

  recentPaperOrders.forEach((order) => {
    const reason = orderReason(order);
    const card = document.createElement("article");
    card.className = "recent-paper-order";

    const header = document.createElement("div");
    header.className = "recent-paper-order-header";
    const identity = document.createElement("div");
    const symbol = document.createElement("strong");
    const timestamp = document.createElement("span");
    symbol.textContent = formatValue(order.symbol);
    timestamp.textContent = formatDateTime(order.createdAt);
    identity.append(symbol, timestamp);

    const badges = document.createElement("div");
    badges.className = "recent-paper-order-badges";
    const sideBadge = document.createElement("span");
    sideBadge.className = orderSideClass(order.side);
    sideBadge.textContent = orderSideLabel(order.side);
    const statusBadge = document.createElement("span");
    statusBadge.className = orderStatusClass(order.status, reason);
    statusBadge.textContent = orderStatusLabel(order.status, reason);
    badges.append(sideBadge, statusBadge);
    header.append(identity, badges);

    const averageFillPrice = orderAverageFillPrice(order);
    const executionPrice = firstAvailable(averageFillPrice, order.requestedPrice);
    const filledQuantity = orderFilledQuantity(order);
    const rows = [
      { label: t("order_created_time_label"), value: formatDateTime(order.createdAt) },
      { label: t("order_mode_label"), value: humanizeMessage(order.mode, "—") },
      { label: t("order_type_label"), value: humanizeMessage(order.orderType, "—") },
      { label: t("order_quantity_label"), value: formatDecimal(order.quantity) },
      { label: t("order_filled_quantity_label"), value: formatDecimal(filledQuantity) },
      { label: t("order_price_label"), value: formatDecimal(executionPrice) },
      { label: t("order_fill_count_label"), value: formatDecimal(order.fillCount, "0") },
    ];
    if (order.strategyId) {
      rows.push({ label: t("order_strategy_label"), value: `#${formatValue(order.strategyId)}` });
    }

    const grid = document.createElement("dl");
    grid.className = "recent-paper-order-grid";
    rows.forEach((row) => appendMetric(grid, row));

    card.append(header, grid);
    if (reason) {
      const reasonEl = document.createElement("p");
      reasonEl.className = "recent-paper-order-reason";
      reasonEl.textContent = `${t("order_reason_label")}: ${humanizeMessage(reason, reason)}`;
      card.append(reasonEl);
    }
    list.append(card);
  });

  recentPaperOrdersContent.append(list);
  if (recentPaperOrdersError) {
    const error = document.createElement("p");
    error.className = "recent-paper-orders-note error";
    error.textContent = recentPaperOrdersError;
    recentPaperOrdersContent.append(error);
  }
}

function executionSafetyStateLabel(value) {
  if (value === true) return t("execution_safety_allowed");
  if (value === false) return t("execution_safety_blocked");
  return "—";
}

function executionSafetyStateClass(value) {
  if (value === true) return "execution-safety-state-badge allowed";
  if (value === false) return "execution-safety-state-badge blocked";
  return "execution-safety-state-badge";
}

function executionSafetyEnabledLabel(value) {
  if (value === true) return t("execution_safety_enabled");
  if (value === false) return t("execution_safety_disabled");
  return "—";
}

function executionSafetyConfiguredLabel(value) {
  if (value === true) return t("execution_safety_configured");
  if (value === false) return t("execution_safety_not_configured");
  return "—";
}

function executionSafetyLimitValue(value, formatter) {
  if (value === null || value === undefined || value === "") return t("execution_safety_disabled");
  return formatter(value);
}

function executionSafetyLossClass(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed === 0) return "pnl-neutral";
  return parsed > 0 ? "pnl-negative" : "pnl-positive";
}

function isSafeExecutionSafetyMetadataKey(key) {
  const normalized = normalizeStrategyType(key);
  if (
    normalized.includes("key") ||
    normalized.includes("secret") ||
    normalized.includes("token") ||
    normalized.includes("credential") ||
    normalized.includes("password") ||
    normalized.includes("signature") ||
    normalized.includes("api")
  ) {
    return false;
  }
  return new Set([
    "broker",
    "mode",
    "symbol",
    "side",
    "bot_id",
    "strategy_id",
    "order_id",
    "order_type",
    "notional",
    "max_order_notional",
    "daily_order_count",
    "accepted_order_count",
    "max_daily_order_count",
    "remaining_daily_order_capacity",
    "day_start",
    "utc_day_start",
    "current_daily_realized_loss",
    "max_daily_loss",
    "remaining_daily_loss_capacity",
    "paper_execution_allowed",
    "live_execution_enabled",
    "risk_reducing_exits_allowed",
  ]).has(normalized);
}

function executionSafetyMetadataValue(value) {
  if (typeof value === "boolean") return value ? t("yes") : t("no");
  if (typeof value === "number" || typeof value === "bigint") return formatDecimal(value);
  if (typeof value === "string") return humanizeMessage(value, value);
  return "";
}

function safeExecutionSafetyMetadata(metadata) {
  if (!metadata || typeof metadata !== "object") return [];
  return Object.entries(metadata)
    .filter(([key, value]) => {
      if (!isSafeExecutionSafetyMetadataKey(key)) return false;
      return ["string", "number", "boolean", "bigint"].includes(typeof value);
    })
    .slice(0, 6)
    .map(([key, value]) => ({
      label: humanizeMessage(key, key),
      value: executionSafetyMetadataValue(value),
    }))
    .filter((item) => item.value);
}

function reconciliationJobStatusLabel(status) {
  const normalized = normalizeStrategyType(status);
  const labels = {
    pending: "reconciliation_job_status_pending",
    claimed: "reconciliation_job_status_claimed",
    resolved: "reconciliation_job_status_resolved",
    exhausted: "reconciliation_job_status_exhausted",
  };
  return t(labels[normalized] || "reconciliation_job_status_unknown");
}

function reconciliationJobStatusClass(status) {
  const normalized = normalizeStrategyType(status);
  if (normalized === "resolved") return "reconciliation-job-status resolved";
  if (normalized === "exhausted") return "reconciliation-job-status exhausted";
  if (normalized === "claimed") return "reconciliation-job-status claimed";
  if (normalized === "pending") return "reconciliation-job-status pending";
  return "reconciliation-job-status";
}

function reconciliationJobIdValue(value) {
  const formatted = formatValue(value);
  return formatted === "—" ? formatted : `#${formatted}`;
}

function renderRecentReconciliationJobs() {
  recentReconciliationJobsContent.innerHTML = "";

  if (isLoadingRecentReconciliationJobs && recentReconciliationJobs.length === 0) {
    recentReconciliationJobsContent.textContent = t("recent_reconciliation_jobs_loading");
    recentReconciliationJobsContent.className = "recent-reconciliation-jobs-content empty loading";
    return;
  }

  if (recentReconciliationJobsError && recentReconciliationJobs.length === 0) {
    recentReconciliationJobsContent.textContent = recentReconciliationJobsError;
    recentReconciliationJobsContent.className = "recent-reconciliation-jobs-content empty error";
    return;
  }

  if (recentReconciliationJobs.length === 0) {
    recentReconciliationJobsContent.textContent = t("recent_reconciliation_jobs_empty");
    recentReconciliationJobsContent.className = "recent-reconciliation-jobs-content empty";
    return;
  }

  recentReconciliationJobsContent.className = "recent-reconciliation-jobs-content";
  const list = document.createElement("div");
  list.className = "recent-reconciliation-jobs-list";

  recentReconciliationJobs.forEach((job) => {
    const item = document.createElement("article");
    item.className = "recent-reconciliation-job";

    const header = document.createElement("div");
    header.className = "recent-reconciliation-job-header";
    const identity = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = `${t("reconciliation_job_id_label")} ${reconciliationJobIdValue(job.id)}`;
    const meta = document.createElement("p");
    meta.className = "recent-reconciliation-job-meta";
    meta.textContent = [
      `${t("reconciliation_job_execution_attempt_label")} ${reconciliationJobIdValue(job.executionAttemptId)}`,
      `${t("reconciliation_job_bot_label")} ${reconciliationJobIdValue(job.botId)}`,
    ].join(" · ");
    identity.append(title, meta);

    const statusBadge = document.createElement("span");
    statusBadge.className = reconciliationJobStatusClass(job.status);
    statusBadge.textContent = reconciliationJobStatusLabel(job.status);
    header.append(identity, statusBadge);

    const metrics = document.createElement("dl");
    metrics.className = "recent-reconciliation-job-grid";
    [
      {
        label: t("reconciliation_job_attempt_count_label"),
        value: formatDecimal(job.automaticAttemptCount),
      },
      {
        label: t("reconciliation_job_max_attempts_label"),
        value: formatDecimal(job.maxAutomaticAttempts),
      },
      {
        label: t("reconciliation_job_next_attempt_label"),
        value: formatUtcDateTime(job.nextAttemptAt),
      },
      {
        label: t("reconciliation_job_claimed_label"),
        value: formatUtcDateTime(job.claimedAt),
      },
      {
        label: t("reconciliation_job_resolved_label"),
        value: formatUtcDateTime(job.resolvedAt),
      },
      {
        label: t("reconciliation_job_exhausted_label"),
        value: formatUtcDateTime(job.exhaustedAt),
      },
      {
        label: t("reconciliation_job_result_label"),
        value: formatValue(job.lastResult),
        className: "recent-reconciliation-job-wide",
      },
      {
        label: t("reconciliation_job_failure_label"),
        value: formatValue(job.lastFailure),
        className: "recent-reconciliation-job-wide",
      },
      {
        label: t("reconciliation_job_created_label"),
        value: formatUtcDateTime(job.createdAt),
      },
      {
        label: t("reconciliation_job_updated_label"),
        value: formatUtcDateTime(job.updatedAt),
      },
    ].forEach((metric) => appendMetric(metrics, metric));

    item.append(header, metrics);
    list.append(item);
  });

  recentReconciliationJobsContent.append(list);

  if (recentReconciliationJobsError) {
    const error = document.createElement("p");
    error.className = "recent-reconciliation-jobs-note error";
    error.textContent = recentReconciliationJobsError;
    recentReconciliationJobsContent.append(error);
  }
}

function reconciliationWorkerEnabledLabel(value) {
  if (value === true) return t("execution_safety_enabled");
  if (value === false) return t("execution_safety_disabled");
  return "—";
}

function reconciliationWorkerInitializedLabel(value) {
  return value === true ? t("reconciliation_worker_initialized") : t("reconciliation_worker_never_started");
}

function reconciliationWorkerHeartbeatLabel(status) {
  if (!status?.lastHeartbeatAt) return t("reconciliation_worker_not_available");
  return status.isStale === true
    ? t("reconciliation_worker_stale_heartbeat")
    : t("reconciliation_worker_recent_heartbeat");
}

function reconciliationWorkerThresholdLabel(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return "—";
  return t("reconciliation_worker_seconds", { seconds: formatDecimal(seconds, "0") });
}

function reconciliationWorkerSummary(status) {
  if (!status?.initialized) {
    return {
      label: t("reconciliation_worker_not_started"),
      summary: t("reconciliation_worker_not_started"),
      className: "reconciliation-worker-state-badge neutral",
    };
  }
  if (status.configuredEnabled === false) {
    return {
      label: t("execution_safety_disabled"),
      summary: t("reconciliation_worker_disabled_summary"),
      className: "reconciliation-worker-state-badge neutral",
    };
  }
  if (status.state === "running" && status.isStale === true) {
    return {
      label: t("reconciliation_worker_stale_heartbeat"),
      summary: t("reconciliation_worker_stale_summary"),
      className: "reconciliation-worker-state-badge warning",
    };
  }
  if (status.state === "running") {
    return {
      label: t("reconciliation_worker_recent_heartbeat"),
      summary: t("reconciliation_worker_recent_summary"),
      className: "reconciliation-worker-state-badge healthy",
    };
  }
  if (status.state === "stopped") {
    return {
      label: t("reconciliation_worker_stopped_summary"),
      summary: t("reconciliation_worker_stopped_summary"),
      className: "reconciliation-worker-state-badge neutral",
    };
  }
  return {
    label: t("health_unknown"),
    summary: t("reconciliation_worker_unknown_summary"),
    className: "reconciliation-worker-state-badge neutral",
  };
}

function renderReconciliationWorker() {
  reconciliationWorkerContent.innerHTML = "";

  if (isLoadingReconciliationWorker && !reconciliationWorkerStatus) {
    reconciliationWorkerContent.textContent = t("reconciliation_worker_loading");
    reconciliationWorkerContent.className = "reconciliation-worker-content empty loading";
    return;
  }

  if (reconciliationWorkerError && !reconciliationWorkerStatus) {
    reconciliationWorkerContent.textContent = reconciliationWorkerError;
    reconciliationWorkerContent.className = "reconciliation-worker-content empty error";
    return;
  }

  if (!reconciliationWorkerStatus) {
    reconciliationWorkerContent.textContent = t("reconciliation_worker_unavailable");
    reconciliationWorkerContent.className = "reconciliation-worker-content empty";
    return;
  }

  const status = reconciliationWorkerStatus;
  const summary = reconciliationWorkerSummary(status);
  const metrics = [
    {
      label: t("reconciliation_worker_configured_label"),
      value: reconciliationWorkerEnabledLabel(status.configuredEnabled),
    },
    {
      label: t("reconciliation_worker_initialized_label"),
      value: reconciliationWorkerInitializedLabel(status.initialized),
    },
    { label: t("reconciliation_worker_state_label"), value: status.state ? formatStatus(status.state) : "—" },
    {
      label: t("reconciliation_worker_heartbeat_label"),
      value: reconciliationWorkerHeartbeatLabel(status),
      valueClass: status.isStale === true ? "negative" : "",
    },
    {
      label: t("reconciliation_worker_stale_threshold_label"),
      value: reconciliationWorkerThresholdLabel(status.heartbeatStaleAfterSeconds),
    },
    { label: t("reconciliation_worker_last_started_label"), value: formatUtcDateTime(status.lastStartedAt) },
    { label: t("reconciliation_worker_last_heartbeat_label"), value: formatUtcDateTime(status.lastHeartbeatAt) },
    { label: t("reconciliation_worker_last_stopped_label"), value: formatUtcDateTime(status.lastStoppedAt) },
    {
      label: t("reconciliation_worker_last_cycle_finished_label"),
      value: formatUtcDateTime(status.lastCycleFinishedAt),
    },
    { label: t("reconciliation_worker_last_result_label"), value: formatValue(status.lastCycleResultCode) },
    {
      label: t("reconciliation_worker_last_job_label"),
      value: formatValue(status.lastProcessedReconciliationJobId),
    },
    { label: t("reconciliation_worker_updated_label"), value: formatUtcDateTime(status.updatedAt) },
  ];

  const state = document.createElement("div");
  state.className = "reconciliation-worker-state";
  const badge = document.createElement("span");
  badge.className = summary.className;
  badge.textContent = summary.label;
  const summaryEl = document.createElement("p");
  summaryEl.className = "reconciliation-worker-summary";
  summaryEl.textContent = summary.summary;
  state.append(badge, summaryEl);

  const grid = document.createElement("dl");
  grid.className = "reconciliation-worker-grid";
  metrics.forEach((item) => appendMetric(grid, item));

  reconciliationWorkerContent.className = "reconciliation-worker-content";
  reconciliationWorkerContent.append(state, grid);

  if (reconciliationWorkerError) {
    const error = document.createElement("p");
    error.className = "reconciliation-worker-note error";
    error.textContent = reconciliationWorkerError;
    reconciliationWorkerContent.append(error);
  }
}

function renderExecutionSafety() {
  executionSafetyContent.innerHTML = "";

  if (!selectedBotId) {
    executionSafetyContent.textContent = t("execution_safety_select_bot");
    executionSafetyContent.className = "execution-safety-content empty";
    return;
  }

  if (isLoadingExecutionSafety && !executionSafetyStatus) {
    executionSafetyContent.textContent = t("execution_safety_loading");
    executionSafetyContent.className = "execution-safety-content empty loading";
    return;
  }

  if (executionSafetyError && !executionSafetyStatus) {
    executionSafetyContent.textContent = executionSafetyError;
    executionSafetyContent.className = "execution-safety-content empty error";
    return;
  }

  if (!executionSafetyStatus) {
    executionSafetyContent.textContent = t("execution_safety_unavailable");
    executionSafetyContent.className = "execution-safety-content empty";
    return;
  }

  const status = executionSafetyStatus;
  const allowed = status.isExecutionCurrentlyAllowed;
  const reason = status.blockingReason
    ? humanizeMessage(status.blockingReason, status.blockingReason)
    : executionSafetyStateLabel(allowed);
  const metrics = [
    { label: t("global_execution_enabled_label"), value: executionSafetyEnabledLabel(status.globalExecutionEnabled) },
    { label: t("paper_execution_enabled_label"), value: executionSafetyEnabledLabel(status.paperExecutionAllowed) },
    { label: t("live_execution_enabled_label"), value: executionSafetyEnabledLabel(status.liveExecutionEnabled) },
    {
      label: t("binance_testnet_enabled_label"),
      value: executionSafetyEnabledLabel(status.binanceTestnetBrokerEnabled),
    },
    {
      label: t("binance_order_submission_enabled_label"),
      value: executionSafetyEnabledLabel(status.binanceTestnetOrderSubmissionEnabled),
    },
    {
      label: t("binance_credentials_configured_label"),
      value: executionSafetyConfiguredLabel(status.binanceTestnetCredentialsConfigured),
    },
    {
      label: t("max_order_notional_label"),
      value: executionSafetyLimitValue(status.maxOrderNotional, (value) => formatCompactMoney(value, "USD")),
    },
    {
      label: t("max_daily_order_count_label"),
      value: executionSafetyLimitValue(status.maxDailyOrderCount, (value) => formatDecimal(value, "0")),
    },
    {
      label: t("current_daily_accepted_order_count_label"),
      value: formatDecimal(status.currentDailyAcceptedOrderCount),
    },
    {
      label: t("remaining_daily_capacity_label"),
      value: formatDecimal(status.remainingDailyOrderCapacity),
    },
    {
      label: t("max_daily_loss_label"),
      value: executionSafetyLimitValue(status.maxDailyLoss, (value) => formatCompactMoney(value, "USD")),
    },
    {
      label: t("current_daily_realized_loss_label"),
      value: formatCompactMoney(status.currentDailyRealizedLoss, "USD"),
      valueClass: executionSafetyLossClass(status.currentDailyRealizedLoss),
    },
    { label: t("execution_safety_utc_day_start_label"), value: formatUtcDateTime(status.utcDayStart) },
  ];
  const safeMetadata = safeExecutionSafetyMetadata(status.metadata);

  const state = document.createElement("div");
  state.className = "execution-safety-state";
  const badge = document.createElement("span");
  badge.className = executionSafetyStateClass(allowed);
  badge.textContent = executionSafetyStateLabel(allowed);
  const reasonEl = document.createElement("p");
  reasonEl.className = "execution-safety-reason";
  reasonEl.textContent = `${t("execution_safety_reason_label")}: ${reason}`;
  state.append(badge, reasonEl);

  const grid = document.createElement("dl");
  grid.className = "execution-safety-grid";
  metrics.forEach((item) => appendMetric(grid, item));

  executionSafetyContent.className = "execution-safety-content";
  executionSafetyContent.append(state, grid);

  if (safeMetadata.length > 0) {
    const metadata = document.createElement("p");
    metadata.className = "execution-safety-metadata";
    const details = safeMetadata.map((item) => `${item.label}: ${item.value}`).join(" · ");
    metadata.textContent = `${t("execution_safety_metadata_label")}: ${details}`;
    executionSafetyContent.append(metadata);
  }

  if (executionSafetyError) {
    const error = document.createElement("p");
    error.className = "execution-safety-note error";
    error.textContent = executionSafetyError;
    executionSafetyContent.append(error);
  }
}

function renderLiveMarket() {
  liveMarketAutoRefresh.checked = liveMarketAutoRefreshEnabled;
  liveMarketRefresh.textContent = isRefreshingLiveMarket
    ? t("live_market_refreshing")
    : t("live_market_refresh");
  liveMarketRefresh.disabled = isRefreshingLiveMarket || liveMarketSymbols.length === 0;
  liveMarketAdd.textContent = t("live_market_add_symbol");
  liveMarketMessageEl.textContent = liveMarketMessage;
  liveMarketMessageEl.className = liveMarketMessageType
    ? `form-message ${liveMarketMessageType}`
    : "form-message";
  liveMarketWatchlist.innerHTML = "";

  if (liveMarketSymbols.length === 0) {
    liveMarketWatchlist.className = "live-market-watchlist empty";
    const title = document.createElement("strong");
    const hint = document.createElement("span");
    title.textContent = t("live_market_empty");
    hint.textContent = t("live_market_empty_hint");
    liveMarketWatchlist.append(title, hint);
    return;
  }

  liveMarketWatchlist.className = "live-market-watchlist";
  liveMarketSymbols.forEach((item) => {
    const direction = liveMarketDirection(item);
    const change = liveMarketChange(item);
    const percentChange = liveMarketPercentChange(item);
    const card = document.createElement("article");
    card.className = `live-market-card ${direction}`;

    const header = document.createElement("div");
    header.className = "live-market-card-header";
    const titleGroup = document.createElement("div");
    const symbol = document.createElement("strong");
    const state = document.createElement("span");
    symbol.textContent = item.symbol;
    state.className = `live-market-direction ${direction}`;
    state.textContent = item.isLoading ? t("live_market_loading") : liveMarketDirectionLabel(direction);
    titleGroup.append(symbol, state);

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "secondary-button live-market-remove";
    removeButton.textContent = "×";
    removeButton.title = t("live_market_remove_symbol", { symbol: item.symbol });
    removeButton.setAttribute("aria-label", t("live_market_remove_symbol", { symbol: item.symbol }));
    removeButton.addEventListener("click", () => removeLiveMarketSymbol(item.symbol));
    const actions = document.createElement("div");
    actions.className = "live-market-card-actions";
    const chartButton = document.createElement("button");
    chartButton.type = "button";
    chartButton.className = "secondary-button live-market-chart-action";
    chartButton.textContent = t("live_market_chart");
    chartButton.setAttribute("aria-label", t("live_market_chart_aria", { symbol: item.symbol }));
    chartButton.addEventListener("click", () => openCandleModal(item.symbol));
    actions.append(chartButton, removeButton);
    header.append(titleGroup, actions);

    const metrics = document.createElement("dl");
    metrics.className = "live-market-metrics";
    [
      { label: t("live_market_latest_price"), value: formatDecimal(item.price) },
      { label: t("live_market_previous_price"), value: formatDecimal(item.previousPrice) },
      { label: t("live_market_absolute_change"), value: formatSignedDecimal(change), className: `pnl-${direction === "up" ? "positive" : direction === "down" ? "negative" : "neutral"}` },
      { label: t("live_market_percent_change"), value: formatSignedPercent(percentChange), className: `pnl-${direction === "up" ? "positive" : direction === "down" ? "negative" : "neutral"}` },
      { label: t("live_market_last_updated"), value: formatDateTime(item.updatedAt) },
    ].forEach((metric) => {
      const group = document.createElement("div");
      const label = document.createElement("dt");
      const value = document.createElement("dd");
      label.textContent = metric.label;
      value.textContent = metric.value;
      if (metric.className) value.className = metric.className;
      group.append(label, value);
      metrics.append(group);
    });

    card.append(header, metrics);
    if (item.error) {
      const error = document.createElement("p");
      error.className = "live-market-error";
      error.textContent = item.error;
      card.append(error);
    }
    liveMarketWatchlist.append(card);
  });
}

function renderCandleModal() {
  candleModalEl.hidden = !candleModal.isOpen;
  if (!candleModal.isOpen) return;

  candleModalTitle.textContent = t("candle_modal_title", { symbol: candleModal.symbol });
  candleTimeframe.value = candleModal.timeframe;
  candleLimit.value = String(candleModal.limit);
  candleDate.value = candleModal.candleDate;
  const isCandleBusy = candleModal.isLoading || candleModal.isLoadingOlder;
  candleRefresh.textContent = candleModal.isLoading ? t("candle_refreshing") : t("candle_refresh");
  candleLoadOlder.textContent = candleModal.isLoadingOlder ? t("candle_loading_older") : t("candle_load_older");
  candleRefresh.disabled = isCandleBusy;
  candleTimeframe.disabled = isCandleBusy;
  candleLimit.disabled = isCandleBusy;
  candleDate.disabled = isCandleBusy;
  candleDateClear.disabled = isCandleBusy || !candleModal.candleDate;
  const window = candleVisibleWindow();
  const defaultWindow = defaultCandleWindow(candleModal.candles.length);
  const canPan = candleModal.candles.length > 0 && window.count < candleModal.candles.length;
  candleLoadOlder.disabled = isCandleBusy || candleModal.candles.length === 0;
  candleOlderMessage.textContent = candleModal.olderMessage;
  candleWindowPrev.disabled = isCandleBusy || !canPan || window.start <= 0;
  candleWindowNext.disabled = (
    isCandleBusy ||
    !canPan ||
    window.start + window.count >= candleModal.candles.length
  );
  candleWindowReset.disabled = (
    isCandleBusy ||
    candleModal.candles.length === 0 ||
    (window.start === defaultWindow.start && window.count === defaultWindow.count)
  );
  candleModalMessage.className = candleModal.error
    ? "candle-modal-message error"
    : candleModal.isLoading
      ? "candle-modal-message loading"
      : "candle-modal-message";
  candleModalMessage.textContent = candleModal.error
    ? candleModal.error
    : candleModal.isLoading
      ? t("candle_loading")
      : candleModal.candles.length === 0
        ? t("candle_empty")
        : "";

  const visibleCandles = visibleCandleSet();
  renderCandleChart(visibleCandles);
  renderCandleSummary(candleModal.candles);
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
  renderCreateStrategyForm();
  renderBotList();
  renderSummary();
  renderBotPerformance();
  renderPaperPortfolio();
  renderRecentPaperOrders();
  renderExecutionSafety();
  renderReconciliationWorker();
  renderRecentReconciliationJobs();
  renderLiveMarket();
  renderDecisionExplanation();
  renderStrategyParametersForm();
  renderBacktestPanel();
  renderBacktestComparison();
  renderBacktestHistory();
  renderEditBotForm();
  renderActivity();
  renderCandleModal();
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
toggleCreateStrategy.addEventListener("click", () => {
  isCreateStrategyOpen = !isCreateStrategyOpen;
  if (isCreateStrategyOpen) {
    populateCreateStrategyParameters(normalizeStrategyType(createStrategyType.value || "price_threshold"));
  }
  if (!isCreateStrategyOpen && !isCreatingStrategy) {
    createStrategyMessage = "";
    createStrategyMessageType = "";
  }
  render();
});
createStrategyType.addEventListener("change", () => {
  populateCreateStrategyParameters(normalizeStrategyType(createStrategyType.value));
  createStrategyMessage = "";
  createStrategyMessageType = "";
  renderCreateStrategyForm();
});
createStrategyCancel.addEventListener("click", () => {
  if (isCreatingStrategy) return;
  isCreateStrategyOpen = false;
  createStrategyMessage = "";
  createStrategyMessageType = "";
  resetCreateStrategyForm();
  render();
});
botSearch.addEventListener("input", () => {
  botSearchQuery = botSearch.value;
  renderBotList();
});
document.addEventListener("visibilitychange", updateAutoRefresh);
document.addEventListener("visibilitychange", updateLiveMarketAutoRefresh);
window.addEventListener("beforeunload", () => {
  stopAutoRefresh();
  if (liveMarketTimer) clearInterval(liveMarketTimer);
});
pauseResume.addEventListener("click", togglePauseResume);
runNow.addEventListener("click", runSelectedBotNow);
editBot.addEventListener("click", openEditBotForm);
deleteBot.addEventListener("click", deleteSelectedBot);
editBotCancel.addEventListener("click", closeEditBotForm);
editStrategyParameters.addEventListener("click", openStrategyParametersForm);
strategyParametersCancel.addEventListener("click", closeStrategyParametersForm);
createBotForm.addEventListener("submit", submitCreateBot);
createStrategyForm.addEventListener("submit", submitCreateStrategy);
editBotForm.addEventListener("submit", submitEditBot);
executionSettingsForm.addEventListener("submit", submitExecutionSettings);
strategyParametersForm.addEventListener("submit", submitStrategyParameters);
riskSettingsForm.addEventListener("submit", submitRiskSettings);
backtestForm.addEventListener("submit", submitBacktest);
backtestSubmit.addEventListener("click", submitBacktest);
backtestImportBinance.addEventListener("click", importBacktestBinanceCandles);
backtestOptimizationForm.addEventListener("submit", submitBacktestOptimization);
optimizationPriceConservative.addEventListener("click", () => applyPriceThresholdPreset("conservative"));
optimizationPriceBalanced.addEventListener("click", () => applyPriceThresholdPreset("balanced"));
optimizationPriceWide.addEventListener("click", () => applyPriceThresholdPreset("wide"));
optimizationMaFast.addEventListener("click", () => applyMovingAveragePreset("fast"));
optimizationMaBalanced.addEventListener("click", () => applyMovingAveragePreset("balanced"));
optimizationMaSlow.addEventListener("click", () => applyMovingAveragePreset("slow"));
optimizationRsiStandard.addEventListener("click", () => applyRsiPreset("standard"));
optimizationRsiSensitive.addEventListener("click", () => applyRsiPreset("sensitive"));
optimizationRsiConservative.addEventListener("click", () => applyRsiPreset("conservative"));
optimizationBollingerStandard.addEventListener("click", () => applyBollingerPreset("standard"));
optimizationBollingerTight.addEventListener("click", () => applyBollingerPreset("tight"));
optimizationBollingerWide.addEventListener("click", () => applyBollingerPreset("wide"));
optimizationMacdStandard.addEventListener("click", () => applyMacdPreset("standard"));
optimizationMacdFast.addEventListener("click", () => applyMacdPreset("fast"));
optimizationMacdSlow.addEventListener("click", () => applyMacdPreset("slow"));
refreshBacktestHistory.addEventListener("click", loadBacktestHistory);
backtestHistoryScopeSelected.addEventListener("click", () => {
  if (!hasSelectedBacktestHistoryStrategy()) return;
  backtestHistoryScope = "selected";
  render();
});
backtestHistoryScopeAll.addEventListener("click", () => {
  backtestHistoryScope = "all";
  render();
});
priceForm.addEventListener("submit", updateMarketPrice);
binancePriceFetch.addEventListener("click", fetchBinancePriceForSelectedBot);
liveMarketForm.addEventListener("submit", addLiveMarketSymbol);
liveMarketRefresh.addEventListener("click", refreshLiveMarket);
liveMarketAutoRefresh.addEventListener("change", () => {
  liveMarketAutoRefreshEnabled = liveMarketAutoRefresh.checked;
  persistLiveMarketAutoRefresh();
  updateLiveMarketAutoRefresh();
  renderLiveMarket();
});
candleModalClose.addEventListener("click", closeCandleModal);
candleModalEl.addEventListener("click", (event) => {
  if (event.target === candleModalEl) closeCandleModal();
});
candleRefresh.addEventListener("click", refreshCandleModal);
candleTimeframe.addEventListener("change", () => {
  candleModal = {
    ...candleModal,
    timeframe: candleTimeframe.value,
    candles: [],
    visibleStart: 0,
    visibleCount: null,
    error: "",
    olderMessage: "",
  };
  renderCandleModal();
  refreshCandleModal();
});
candleLimit.addEventListener("change", () => {
  candleModal = {
    ...candleModal,
    limit: Number(candleLimit.value) || 50,
    candles: [],
    visibleStart: 0,
    visibleCount: null,
    error: "",
    olderMessage: "",
  };
  renderCandleModal();
  refreshCandleModal();
});
candleDate.addEventListener("change", () => {
  candleModal = {
    ...candleModal,
    candleDate: candleDate.value,
    candles: [],
    visibleStart: 0,
    visibleCount: null,
    error: "",
    olderMessage: "",
  };
  renderCandleModal();
  refreshCandleModal();
});
candleDateClear.addEventListener("click", () => {
  candleModal = {
    ...candleModal,
    candleDate: "",
    candles: [],
    visibleStart: 0,
    visibleCount: null,
    error: "",
    olderMessage: "",
  };
  renderCandleModal();
  refreshCandleModal();
});
candleChart.addEventListener("wheel", (event) => {
  if (!candleModal.isOpen || candleModal.isLoading || candleModal.isLoadingOlder || candleModal.candles.length === 0) return;
  const horizontalDelta = Math.abs(event.deltaX) > 0 ? event.deltaX : null;
  const shiftWheelDelta = event.shiftKey && Math.abs(event.deltaY) > 0 ? event.deltaY : null;
  const panDelta = horizontalDelta ?? shiftWheelDelta;
  if (panDelta !== null) {
    event.preventDefault();
    if (panCandleWindowByWheel(panDelta)) {
      renderCandleModal();
    }
    return;
  }
  event.preventDefault();
  zoomCandleWindow(event.deltaY);
}, { passive: false });
candleChart.addEventListener("pointerdown", (event) => {
  if (!candleModal.isOpen || candleModal.isLoading || candleModal.isLoadingOlder || !canPanCandleWindow()) return;
  event.preventDefault();
  hideCandleHover();
  const window = candleVisibleWindow();
  candleDragState = {
    pointerId: event.pointerId,
    startX: event.clientX,
    initialStart: window.start,
    visibleCount: window.count,
  };
  candleChart.classList.add("is-panning");
  candleChart.setPointerCapture?.(event.pointerId);
});
candleChart.addEventListener("pointermove", (event) => {
  if (!candleDragState) {
    showCandleHover(event);
    return;
  }
  if (candleDragState.pointerId !== event.pointerId || candleModal.isLoadingOlder || !canPanCandleWindow()) {
    return;
  }
  event.preventDefault();
  const dragDelta = event.clientX - candleDragState.startX;
  const shift = candlePanDistanceToShift(-dragDelta, candleDragState.visibleCount);
  const nextStart = candleDragState.initialStart + shift;
  const previousStart = candleModal.visibleStart;
  setCandleWindow(nextStart, candleDragState.visibleCount);
  if (candleModal.visibleStart !== previousStart) {
    renderCandleModal();
  }
});
candleChart.addEventListener("pointerup", (event) => finishCandleDrag(event.pointerId));
candleChart.addEventListener("pointercancel", (event) => finishCandleDrag(event.pointerId));
candleChart.addEventListener("lostpointercapture", () => finishCandleDrag());
candleChart.addEventListener("pointerleave", hideCandleHover);
candleLoadOlder.addEventListener("click", loadOlderCandles);
candleWindowPrev.addEventListener("click", () => panCandleWindow(-1));
candleWindowNext.addEventListener("click", () => panCandleWindow(1));
candleWindowReset.addEventListener("click", () => {
  resetCandleWindow();
  renderCandleModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && candleModal.isOpen) {
    closeCandleModal();
  }
});
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
  render();
});
[optimizationFirstValues, optimizationSecondValues, optimizationThirdValues, optimizationQuantity, optimizationMinClosedTrades].forEach(
  (input) => {
    input.addEventListener("input", () => {
      backtestOptimizationTouched = true;
    });
  },
);
optimizationRequireClosedPosition.addEventListener("change", () => {
  backtestOptimizationTouched = true;
});

document.documentElement.lang = currentLanguage === "am" ? "hy" : "en";
renderLanguageSwitcher();
applyStaticTranslations();
updateLiveMarketAutoRefresh();
refreshLiveMarket();
loadBots();
loadStrategies();
