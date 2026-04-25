const API_BASE_URL = "";
const AUTO_REFRESH_MS = 10000;
const LANGUAGE_STORAGE_KEY = "dashboard.language";
const DEFAULT_LANGUAGE = "en";
const SUPPORTED_LANGUAGES = new Set(["en", "am"]);

let bots = [];
let strategies = [];
let selectedBotId = null;
let selectedSummary = null;
let isLoadingBots = true;
let isLoadingSummary = false;
let isLoadingStrategies = false;
let isTogglingPause = false;
let isRunningNow = false;
let isUpdatingPrice = false;
let isRefreshing = false;
let isCreatingBot = false;
let isCreateBotOpen = false;
let isEditBotOpen = false;
let isLoadingEditBot = false;
let isSavingEditBot = false;
let symbolTouched = false;
let botListError = "";
let summaryError = "";
let actionMessage = "";
let actionMessageType = "";
let createBotMessage = "";
let createBotMessageType = "";
let editBotMessage = "";
let editBotMessageType = "";
let strategyLoadError = "";
let priceMessage = "";
let priceMessageType = "";
let refreshMessage = "";
let botSearchQuery = "";
let lastRefreshedAt = null;
let autoRefreshTimer = null;
let selectedBotConfig = null;
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
      "This form updates only basic bot details. Status and mode are shown here for context and are not editable in this form.",
    selected_strategy_label: "Strategy",
    selected_cooldown_label: "Cooldown",
    selected_price_label: "Last price",
    selected_last_run_label: "Last run",
    recent_activity: "Recent Activity",
    set_price: "Set price",
    updating: "Updating…",
    price: "Price",
    quantity: "Quantity",
    loading_recent_activity: "Loading recent activity...",
    loading_generic: "Loading…",
    no_recent_activity_yet: "No recent activity yet.",
    failed_to_load_recent_activity: "Failed to load recent activity.",
    ready_to_run: "Ready to run",
    paused_state: "Paused",
    not_runnable: "Not runnable",
    loading_actions: "Loading bot actions...",
    activate_draft_before_running: "Activate this draft Bot before running it.",
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
    request_failed_404: "The requested Bot could not be found.",
    request_failed_422: "Check the submitted values and try again.",
    could_not_update_price: "Could not update price.",
    could_not_create_bot: "Could not create Bot.",
    could_not_update_bot: "Could not update Bot.",
    could_not_load_bot_settings: "Could not load Bot settings.",
    could_not_load_bot_details: "Could not load Bot details.",
    could_not_load_bots: "Could not load Bots.",
    could_not_refresh: "Could not refresh.",
    auto_refresh_failed: "Auto-refresh failed. {detail}",
    please_try_again: "Please try again.",
    could_not_run_bot: "Could not run Bot.",
    could_not_pause_bot: "Could not pause Bot.",
    could_not_resume_bot: "Could not resume Bot.",
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
      "Այս ձևը թարմացնում է միայն Bot-ի հիմնական դաշտերը։ Status-ը և mode-ը այստեղ ցուցադրվում են միայն տեղեկության համար և չեն խմբագրվում։",
    selected_strategy_label: "Strategy",
    selected_cooldown_label: "Cooldown",
    selected_price_label: "Վերջին գին",
    selected_last_run_label: "Վերջին գործարկում",
    recent_activity: "Վերջին ակտիվություն",
    set_price: "Սահմանել գինը",
    updating: "Թարմացվում է…",
    price: "Գին",
    quantity: "Քանակ",
    loading_recent_activity: "Բեռնվում է վերջին ակտիվությունը...",
    loading_generic: "Բեռնվում է…",
    no_recent_activity_yet: "Վերջին ակտիվություն դեռ չկա։",
    failed_to_load_recent_activity: "Չհաջողվեց բեռնել վերջին ակտիվությունը։",
    ready_to_run: "Պատրաստ է գործարկման",
    paused_state: "Դադարեցված է",
    not_runnable: "Չի կարող գործարկվել",
    loading_actions: "Բեռնվում են Bot-ի գործողությունները...",
    activate_draft_before_running: "Ակտիվացրու այս draft Bot-ը՝ նախքան գործարկելը։",
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
    request_failed_404: "Պահանջված Bot-ը չգտնվեց։",
    request_failed_422: "Ստուգիր ուղարկված արժեքները և նորից փորձիր։",
    could_not_update_price: "Չհաջողվեց թարմացնել գինը։",
    could_not_create_bot: "Չհաջողվեց ստեղծել Bot։",
    could_not_update_bot: "Չհաջողվեց թարմացնել Bot-ը։",
    could_not_load_bot_settings: "Չհաջողվեց բեռնել Bot-ի կարգավորումները։",
    could_not_load_bot_details: "Չհաջողվեց բեռնել Bot-ի մանրամասները։",
    could_not_load_bots: "Չհաջողվեց բեռնել Bots։",
    could_not_refresh: "Չհաջողվեց թարմացնել։",
    auto_refresh_failed: "Auto-refresh-ը ձախողվեց։ {detail}",
    please_try_again: "Խնդրում ենք նորից փորձել։",
    could_not_run_bot: "Չհաջողվեց գործարկել Bot-ը։",
    could_not_pause_bot: "Չհաջողվեց դադարեցնել Bot-ը։",
    could_not_resume_bot: "Չհաջողվեց վերսկսել Bot-ը։",
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
    order_filled: "Order filled",
    run_event: "Run event",
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
const actionHelp = document.querySelector("#action-help");
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
const recentActivityHeading = document.querySelector("#recent-activity-heading");
const activityList = document.querySelector("#activity-list");
const priceForm = document.querySelector("#price-form");
const priceSymbol = document.querySelector("#price-symbol");
const priceValue = document.querySelector("#price-value");
const priceSubmit = document.querySelector("#price-submit");
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
  recentActivityHeading.textContent = t("recent_activity");
  toggleCreateBot.textContent = isCreateBotOpen ? t("close") : t("create_bot");
  createBotSubmit.textContent = isCreatingBot ? t("creating") : t("create_draft_bot");
  editBot.textContent = isLoadingEditBot ? t("loading_generic") : t("edit");
  editBotSubmit.textContent = isSavingEditBot ? t("saving") : t("save_changes");
  editBotCancel.textContent = t("cancel");
  priceSubmit.textContent = isUpdatingPrice ? t("updating") : t("set_price");
}

function normalizeBot(rawBot) {
  return {
    id: rawBot.bot_id ?? rawBot.id,
    name: rawBot.name ?? "",
    status: rawBot.status ?? "idle",
    isPaused: rawBot.is_paused ?? false,
    strategyType: rawBot.strategy_type ?? "",
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
    isActive: rawStrategy.is_active ?? true,
  };
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
  if (status === "draft") return t("pause_resume");
  return shouldPause(status) ? t("pause") : t("resume");
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

function formatDecimal(value, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value);
  return new Intl.NumberFormat([], {
    minimumFractionDigits: 0,
    maximumFractionDigits: 8,
  }).format(parsed);
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

function formatActivityMessage(item) {
  return humanizeMessage(item?.message || item?.status || item?.type, t("activity_update"));
}

function activityStatus(item) {
  const message = String(item?.message || "").toLowerCase();
  const type = String(item?.type || "").toLowerCase();

  if (message === "buy_filled" || message === "sell_filled" || type === "order_filled") {
    return { label: t("activity_success"), className: "activity-status-success" };
  }
  if (
    ["bot_not_active", "bot_skipped_paused", "evaluation_no_signal", "cooldown_active"].includes(
      message,
    )
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
  if (item?.type === "order_filled") return t("order_filled");
  if (item?.type === "run_event") return t("run_event");
  return humanizeMessage(item?.type, t("activity_event"));
}

function activityDetailParts(item) {
  const parts = [];

  if (item?.side) {
    parts.push(`${t("side_label")}: ${humanizeMessage(item.side)}`);
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

  return parts;
}

function activityBotName() {
  const bot = selectedSummary || bots.find((item) => item.id === selectedBotId);
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
  const details = [strategy.symbol, strategy.timeframe].filter(Boolean).join(" · ");
  return details ? `${strategy.name} (${details})` : strategy.name;
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

async function loadStrategies() {
  isLoadingStrategies = true;
  strategyLoadError = "";
  render();

  try {
    const data = await fetchJson("/api/v1/strategies");
    strategies = Array.isArray(data) ? data.map(normalizeStrategy) : [];
  } catch (error) {
    strategies = [];
    strategyLoadError = requestErrorMessage(error, t("could_not_load_strategies", { detail: "" }).trim());
  } finally {
    isLoadingStrategies = false;
    render();
  }
}

function describeManualRunResult(result) {
  const latestActivity = result?.recent_activity_preview?.[0]?.message;
  const activityLabel = humanizeMessage(latestActivity || result?.message, "Recent activity updated");

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

function clearSelectedBotMessages() {
  actionMessage = "";
  actionMessageType = "";
  editBotMessage = "";
  editBotMessageType = "";
}

function hasInFlightAction() {
  return (
    isLoadingSummary ||
    isTogglingPause ||
    isRunningNow ||
    isUpdatingPrice ||
    isCreatingBot ||
    isLoadingEditBot ||
    isSavingEditBot
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
    if (selectedBotId && !bots.some((bot) => bot.id === selectedBotId)) {
      selectedBotId = null;
      isEditBotOpen = false;
      selectedBotConfig = null;
    }
    if (!selectedBotId && bots.length > 0) {
      selectedBotId = bots[0].id;
    }
    if (selectedBotId !== previousSelectedBotId) {
      clearSelectedBotMessages();
    }
    refreshMessage = "";
    lastRefreshedAt = new Date();
    isLoadingBots = false;
    render();
    if (selectedBotId) {
      await loadSelectedSummary(selectedBotId);
    }
  } catch (error) {
    bots = [];
    selectedBotId = null;
    selectedSummary = null;
    isLoadingBots = false;
    botListError = requestErrorMessage(error, t("could_not_load_bots"));
    render();
  }
}

async function refreshSelectedData() {
  const currentBotId = selectedBotId;
  const data = await fetchJson("/api/v1/bots");
  bots = normalizeBotsResponse(data);

  selectedBotId = bots.some((bot) => bot.id === currentBotId)
    ? currentBotId
    : bots[0]?.id ?? null;

  if (selectedBotId !== currentBotId) {
    clearSelectedBotMessages();
  }

  if (selectedBotId) {
    const summary = await fetchJson(`/api/v1/bots/${selectedBotId}/summary`);
    selectedSummary = normalizeSummary(summary);
  } else {
    selectedSummary = null;
    isEditBotOpen = false;
    selectedBotConfig = null;
  }
  refreshMessage = "";
  lastRefreshedAt = new Date();
}

async function refreshDashboardData({ silent = false } = {}) {
  if (isRefreshing) return;

  const currentBotId = selectedBotId;
  isRefreshing = true;
  if (!silent) {
    refreshMessage = "";
  }
  render();

  try {
    const data = await fetchJson("/api/v1/bots");
    bots = normalizeBotsResponse(data);
    botListError = "";

    selectedBotId = bots.some((bot) => bot.id === currentBotId)
      ? currentBotId
      : null;

    if (selectedBotId !== currentBotId) {
      clearSelectedBotMessages();
    }

    if (selectedBotId) {
      const summary = await fetchJson(`/api/v1/bots/${selectedBotId}/summary`);
      selectedSummary = normalizeSummary(summary);
      summaryError = "";
    } else {
      selectedSummary = null;
      summaryError = "";
    }
    refreshMessage = "";
    lastRefreshedAt = new Date();
  } catch (error) {
    refreshMessage = silent
      ? t("auto_refresh_failed", { detail: requestErrorMessage(error, t("please_try_again")) })
      : requestErrorMessage(error, t("could_not_refresh"));
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
  const bot = selectedSummary || bots.find((item) => item.id === selectedBotId);
  if (!bot || isTogglingPause) return;

  const action = shouldPause(bot.status) ? "pause" : "resume";
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
      action === "pause" ? t("could_not_pause_bot") : t("could_not_resume_bot"),
    );
    actionMessageType = "error";
  } finally {
    isTogglingPause = false;
    render();
  }
}

async function runSelectedBotNow() {
  const bot = selectedSummary || bots.find((item) => item.id === selectedBotId);
  if (!bot || isRunningNow) return;

  isRunningNow = true;
  actionMessage = "";
  actionMessageType = "";
  render();

  try {
    const result = await fetchJson(`/api/v1/bots/${bot.id}/run`, { method: "POST" });
    const feedback = describeManualRunResult(result);
    actionMessage = feedback.text;
    actionMessageType = feedback.type;
    await refreshSelectedData();
  } catch (error) {
    actionMessage = requestErrorMessage(error, t("could_not_run_bot"));
    actionMessageType = "error";
  } finally {
    isRunningNow = false;
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
  selectedBotConfig = null;
  editBotMessage = "";
  editBotMessageType = "";
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

  isSavingEditBot = true;
  editBotMessage = "";
  editBotMessageType = "";
  render();

  const payload = {
    name: editBotName.value.trim(),
    strategy_id: Number(editBotStrategyId.value.trim()),
    exchange_name: editBotExchangeName.value.trim(),
    notes: editBotNotes.value.trim() || null,
  };

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

async function loadSelectedSummary(botId) {
  summaryError = "";
  actionMessage = "";
  actionMessageType = "";
  isLoadingSummary = true;
  selectedSummary = null;
  selectedBotConfig = null;
  render();

  try {
    const [summaryResult, configResult] = await Promise.allSettled([
      fetchJson(`/api/v1/bots/${botId}/summary`),
      fetchJson(`/api/v1/bots/${botId}`),
    ]);

    if (summaryResult.status !== "fulfilled") {
      throw summaryResult.reason;
    }

    selectedSummary = normalizeSummary(summaryResult.value);
    if (configResult.status === "fulfilled") {
      selectedBotConfig = normalizeBotConfig(configResult.value);
    }
  } catch (error) {
    selectedSummary = null;
    selectedBotConfig = null;
    summaryError = requestErrorMessage(error, t("could_not_load_bot_details"));
  } finally {
    isLoadingSummary = false;
  }

  render();
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
    row.setAttribute("aria-selected", String(bot.id === selectedBotId));
    row.addEventListener("click", async () => {
      if (bot.id === selectedBotId) return;
      clearSelectedBotMessages();
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
  editBot.disabled = !selectedBotId || isLoadingSummary || isLoadingEditBot || isSavingEditBot;
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

  renderStrategySelect(editBotStrategyId, selectedBotConfig?.strategyId ?? editBotStrategyId.value);

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

function renderSummary() {
  const listBot = bots.find((bot) => bot.id === selectedBotId);
  const bot = selectedSummary || listBot;
  const botMode = modeLabel(selectedBotConfig?.isPaper);
  const canRunNow = Boolean(selectedBotId && bot && isRunnableStatus(bot.status) && !bot.isPaused);
  const canPauseResume = Boolean(selectedBotId && bot && !["draft"].includes(bot.status));

  if (!bot) {
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
    pauseResume.textContent = t("pause");
    pauseResume.disabled = true;
    runNow.textContent = t("run_now");
    runNow.disabled = true;
    editBot.textContent = t("edit");
    editBot.disabled = true;
    actionHelp.textContent = actionHelpText(null);
    if (!symbolTouched) {
      priceSymbol.value = "";
    }
    priceSubmit.textContent = isUpdatingPrice ? t("updating") : t("set_price");
    priceSubmit.disabled = isUpdatingPrice;
    actionMessageEl.textContent = "";
    actionMessageEl.className = "action-message";
    priceMessageEl.textContent = priceMessage;
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
  selectedStrategy.textContent = formatValue(bot.strategyType);
  selectedCooldown.textContent = cooldownText(bot);
  selectedPrice.textContent = formatDecimal(bot.lastPrice);
  selectedLastRun.textContent = formatDateTime(bot.updatedAt);
  pauseResume.textContent = isTogglingPause
    ? `${pauseResumeLabel(bot.status)}…`
    : pauseResumeLabel(bot.status);
  pauseResume.disabled = !canPauseResume || isTogglingPause || isLoadingSummary || isRunningNow;
  runNow.textContent = isRunningNow ? t("running_now") : t("run_now");
  runNow.disabled = !canRunNow || isRunningNow || isLoadingSummary || isTogglingPause;
  editBot.textContent = isLoadingEditBot ? t("loading_generic") : t("edit");
  editBot.disabled =
    !selectedBotId || isLoadingSummary || isLoadingEditBot || isSavingEditBot || isRunningNow || isTogglingPause;
  actionHelp.textContent = actionHelpText(bot);
  if (!symbolTouched) {
    priceSymbol.value = formatValue(bot.symbol, "");
  }
  if (!priceValue.value) {
    priceValue.value = formatDecimal(bot.lastPrice, "");
  }
  priceSubmit.textContent = isUpdatingPrice ? t("updating") : t("set_price");
  priceSubmit.disabled = isUpdatingPrice;
  actionMessageEl.textContent = actionMessage;
  actionMessageEl.className = actionMessageType
    ? `action-message ${actionMessageType}`
    : "action-message";
  priceMessageEl.textContent = priceMessage;
  priceMessageEl.className = priceMessageType
    ? `form-message ${priceMessageType}`
    : "form-message";
}

function renderRefreshControl() {
  refreshDashboard.textContent = isRefreshing ? t("refreshing") : t("refresh");
  refreshDashboard.disabled = isRefreshing || hasInFlightAction();
  refreshMessageEl.textContent = refreshMessage;
  refreshMessageEl.className = refreshMessage
    ? "refresh-message error"
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
editBotCancel.addEventListener("click", closeEditBotForm);
createBotForm.addEventListener("submit", submitCreateBot);
editBotForm.addEventListener("submit", submitEditBot);
priceForm.addEventListener("submit", updateMarketPrice);
priceSymbol.addEventListener("input", () => {
  symbolTouched = true;
});

document.documentElement.lang = currentLanguage === "am" ? "hy" : "en";
renderLanguageSwitcher();
applyStaticTranslations();
loadBots();
loadStrategies();
