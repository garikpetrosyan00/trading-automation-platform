const API_BASE_URL = "";
const AUTO_REFRESH_MS = 10000;

let bots = [];
let selectedBotId = null;
let selectedSummary = null;
let isLoadingBots = true;
let isLoadingSummary = false;
let isTogglingPause = false;
let isRunningNow = false;
let isUpdatingPrice = false;
let isRefreshing = false;
let symbolTouched = false;
let botListError = "";
let summaryError = "";
let actionMessage = "";
let actionMessageType = "";
let priceMessage = "";
let priceMessageType = "";
let refreshMessage = "";
let botSearchQuery = "";
let lastRefreshedAt = null;
let autoRefreshTimer = null;

const headerMeta = document.querySelector("#header-meta");
const botList = document.querySelector("#bot-list");
const botCount = document.querySelector("#bot-count");
const botSearch = document.querySelector("#bot-search");
const selectedSymbol = document.querySelector("#selected-symbol");
const selectedName = document.querySelector("#selected-name");
const selectedStatus = document.querySelector("#selected-status");
const selectedStrategy = document.querySelector("#selected-strategy");
const selectedCooldown = document.querySelector("#selected-cooldown");
const selectedPrice = document.querySelector("#selected-price");
const selectedLastRun = document.querySelector("#selected-last-run");
const pauseResume = document.querySelector("#pause-resume");
const runNow = document.querySelector("#run-now");
const actionMessageEl = document.querySelector("#action-message");
const refreshDashboard = document.querySelector("#refresh-dashboard");
const autoRefresh = document.querySelector("#auto-refresh");
const refreshMessageEl = document.querySelector("#refresh-message");
const activityList = document.querySelector("#activity-list");
const priceForm = document.querySelector("#price-form");
const priceSymbol = document.querySelector("#price-symbol");
const priceValue = document.querySelector("#price-value");
const priceSubmit = document.querySelector("#price-submit");
const priceMessageEl = document.querySelector("#price-message");

function normalizeBot(rawBot) {
  return {
    id: rawBot.bot_id ?? rawBot.id,
    name: rawBot.name ?? "Unnamed bot",
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
  return shouldPause(status) ? "Pause" : "Resume";
}

function formatValue(value, fallback = "—") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
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
  return `${count} ${count === 1 ? "bot" : "bots"}`;
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
      ? `Active until ${formatDateTime(bot.cooldownUntil)}`
      : "Active";
  }
  if (bot.cooldownSeconds) return `${formatDecimal(bot.cooldownSeconds)}s configured`;
  return "Not active";
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`);
  }
  return response.json();
}

async function loadBots() {
  isLoadingBots = true;
  botListError = "";
  render();

  try {
    const data = await fetchJson("/api/v1/bots");
    bots = normalizeBotsResponse(data);
    if (selectedBotId && !bots.some((bot) => bot.id === selectedBotId)) {
      selectedBotId = null;
    }
    if (!selectedBotId && bots.length > 0) {
      selectedBotId = bots[0].id;
    }
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
    botListError = "Could not load bots.";
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

  if (selectedBotId) {
    const summary = await fetchJson(`/api/v1/bots/${selectedBotId}/summary`);
    selectedSummary = normalizeSummary(summary);
  } else {
    selectedSummary = null;
  }
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

    if (selectedBotId) {
      const summary = await fetchJson(`/api/v1/bots/${selectedBotId}/summary`);
      selectedSummary = normalizeSummary(summary);
      summaryError = "";
    } else {
      selectedSummary = null;
      summaryError = "";
    }
    lastRefreshedAt = new Date();
  } catch (error) {
    refreshMessage = silent ? "Auto-refresh failed." : "Could not refresh.";
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
    actionMessage = `Could not ${action} bot.`;
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
    await fetchJson(`/api/v1/bots/${bot.id}/run`, { method: "POST" });
    actionMessage = "Manual run created";
    actionMessageType = "success";
    await refreshSelectedData();
  } catch (error) {
    actionMessage = "Could not run bot.";
    actionMessageType = "error";
  } finally {
    isRunningNow = false;
    render();
  }
}

function validationMessage(error) {
  return error?.message?.startsWith("Request failed with 422")
    ? "Check symbol and positive price."
    : "Could not update price.";
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
    priceMessage = "Price updated";
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
  render();

  try {
    const data = await fetchJson(`/api/v1/bots/${botId}/summary`);
    selectedSummary = normalizeSummary(data);
  } catch (error) {
    selectedSummary = null;
    summaryError = "Could not load bot details.";
  } finally {
    isLoadingSummary = false;
  }

  render();
}

function renderBotList() {
  botList.innerHTML = "";
  botSearch.value = botSearchQuery;

  if (isLoadingBots) {
    botCount.textContent = "Loading";
    botList.innerHTML = `<div class="state-message loading">Loading bots...</div>`;
    return;
  }

  if (botListError) {
    botCount.textContent = "Error";
    botList.innerHTML = `<div class="state-message error">${botListError}</div>`;
    return;
  }

  const visibleBots = filteredBots();
  botCount.textContent = botSearchQuery
    ? `${visibleBots.length}/${bots.length} bots`
    : `${bots.length} bots`;

  if (bots.length === 0) {
    botList.innerHTML = `<div class="state-message">No bots yet.</div>`;
    return;
  }

  if (visibleBots.length === 0) {
    botList.innerHTML = `<div class="state-message">No bots match your search.</div>`;
    return;
  }

  visibleBots.forEach((bot) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "bot-row";
    row.setAttribute("aria-selected", String(bot.id === selectedBotId));
    row.addEventListener("click", async () => {
      selectedBotId = bot.id;
      await loadSelectedSummary(bot.id);
    });

    row.innerHTML = `
      <span class="bot-row-main">
        <strong class="bot-row-name">${formatValue(bot.name, "Unnamed bot")}</strong>
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

function renderSummary() {
  const listBot = bots.find((bot) => bot.id === selectedBotId);
  const bot = selectedSummary || listBot;

  if (!bot) {
    selectedSymbol.textContent = "";
    selectedName.textContent = botListError
      ? "Details unavailable"
      : "Select a bot to view details.";
    selectedStatus.textContent = "idle";
    selectedStatus.className = "status-pill status-idle";
    selectedStrategy.textContent = "—";
    selectedCooldown.textContent = "—";
    selectedPrice.textContent = "—";
    selectedLastRun.textContent = "—";
    pauseResume.textContent = "Pause";
    pauseResume.disabled = true;
    runNow.textContent = "Run now";
    runNow.disabled = true;
    if (!symbolTouched) {
      priceSymbol.value = "";
    }
    priceSubmit.textContent = isUpdatingPrice ? "Updating…" : "Set price";
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
    ? "Loading details..."
    : formatValue(bot.name, "Unnamed bot");
  selectedStatus.textContent = formatStatus(bot.status);
  selectedStatus.className = `status-pill ${statusClass(bot.status)}`;
  selectedStrategy.textContent = formatValue(bot.strategyType);
  selectedCooldown.textContent = cooldownText(bot);
  selectedPrice.textContent = formatDecimal(bot.lastPrice);
  selectedLastRun.textContent = formatDateTime(bot.updatedAt);
  pauseResume.textContent = isTogglingPause
    ? `${pauseResumeLabel(bot.status)}…`
    : pauseResumeLabel(bot.status);
  pauseResume.disabled = !selectedBotId || isTogglingPause;
  runNow.textContent = isRunningNow ? "Running…" : "Run now";
  runNow.disabled = !selectedBotId || isRunningNow;
  if (!symbolTouched) {
    priceSymbol.value = formatValue(bot.symbol, "");
  }
  if (!priceValue.value) {
    priceValue.value = formatDecimal(bot.lastPrice, "");
  }
  priceSubmit.textContent = isUpdatingPrice ? "Updating…" : "Set price";
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
  refreshDashboard.textContent = isRefreshing ? "Refreshing…" : "Refresh";
  refreshDashboard.disabled = isRefreshing;
  refreshMessageEl.textContent = refreshMessage;
  refreshMessageEl.className = refreshMessage
    ? "refresh-message error"
    : "refresh-message";
}

function renderHeaderMeta() {
  headerMeta.textContent = `${botCountText(bots.length)} · Last refreshed: ${formatTime(lastRefreshedAt)}`;
}

function renderActivity() {
  activityList.innerHTML = "";

  if (summaryError) {
    activityList.innerHTML = `<li><span class="activity-empty error">${summaryError}</span></li>`;
    return;
  }

  const activity = selectedSummary?.recentActivity ?? [];

  if (selectedBotId && isLoadingSummary) {
    activityList.innerHTML = `<li><span class="activity-empty loading">Loading activity...</span></li>`;
    return;
  }

  if (selectedBotId && selectedSummary && activity.length === 0) {
    activityList.innerHTML = `<li><span class="activity-empty">No recent activity yet.</span></li>`;
    return;
  }

  if (!selectedBotId || !selectedSummary) {
    activityList.innerHTML = `<li><span class="activity-empty">Select a bot to view activity.</span></li>`;
    return;
  }

  activity.forEach((item) => {
    const row = document.createElement("li");
    row.innerHTML = `
      <span class="activity-message">${item.message ?? item.status ?? item.type ?? "activity"}</span>
      <span class="activity-time">${formatDateTime(item.timestamp ?? item.created_at)}</span>
    `;
    activityList.appendChild(row);
  });
}

function render() {
  renderHeaderMeta();
  renderRefreshControl();
  renderBotList();
  renderSummary();
  renderActivity();
}

refreshDashboard.addEventListener("click", () => refreshDashboardData());
autoRefresh.addEventListener("change", updateAutoRefresh);
botSearch.addEventListener("input", () => {
  botSearchQuery = botSearch.value;
  renderBotList();
});
document.addEventListener("visibilitychange", updateAutoRefresh);
window.addEventListener("beforeunload", stopAutoRefresh);
pauseResume.addEventListener("click", togglePauseResume);
runNow.addEventListener("click", runSelectedBotNow);
priceForm.addEventListener("submit", updateMarketPrice);
priceSymbol.addEventListener("input", () => {
  symbolTouched = true;
});

loadBots();
