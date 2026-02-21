const futuresSearchForm = document.getElementById("futures-search-form");
const futuresQueryInput = document.getElementById("futures-query");
const futuresSearchStatus = document.getElementById("futures-search-status");
const futuresSearchResults = document.getElementById("futures-search-results");

const candlesForm = document.getElementById("candles-form");
const candlesTickerInput = document.getElementById("candles-ticker");
const candlesStatus = document.getElementById("candles-status");
const candlesMeta = document.getElementById("candles-meta");
const candlesCanvas = document.getElementById("candles-canvas");

const bondsForm = document.getElementById("bonds-form");
const bondsStatus = document.getElementById("bonds-status");
const bondsTbody = document.querySelector("#bonds-table tbody");
const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
const tabPanels = Array.from(document.querySelectorAll(".tab-panel"));
let lastDailyRows = [];

function setViewportSizeVars() {
  const vh = window.innerHeight * 0.01;
  const vw = document.documentElement.clientWidth * 0.01;
  document.documentElement.style.setProperty("--vh", `${vh}px`);
  document.documentElement.style.setProperty("--vw", `${vw}px`);
}

function initTelegramWebApp() {
  const tg = window.Telegram?.WebApp;
  if (!tg) return;
  try {
    tg.ready();
    tg.expand();
    if (typeof tg.disableVerticalSwipes === "function") {
      tg.disableVerticalSwipes();
    }
  } catch (error) {
    console.warn("Telegram WebApp init failed:", error);
  }
}

function resizeCandlesCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const rect = candlesCanvas.getBoundingClientRect();
  const cssWidth = Math.max(280, Math.floor(rect.width || 320));
  const cssHeight = Math.max(180, Math.floor(rect.height || 240));
  candlesCanvas.width = Math.floor(cssWidth * ratio);
  candlesCanvas.height = Math.floor(cssHeight * ratio);
  const ctx = candlesCanvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
}

function setStatus(target, text, isError = false) {
  target.textContent = text || "";
  target.classList.toggle("error", isError);
}

async function fetchJson(url) {
  const res = await fetch(url);
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(payload.detail || `HTTP ${res.status}`);
  }
  return payload;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function toFloat(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") {
    const normalized = value.replace(",", ".");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function couponsPerYear(bond) {
  const couponPeriod = toFloat(bond.coupon_period);
  if (couponPeriod && couponPeriod > 0) return 365 / couponPeriod;
  const couponFrequency = toFloat(bond.coupon_frequency);
  if (couponFrequency && couponFrequency > 0) return couponFrequency;
  return null;
}

function priceMoney(bond) {
  const currentPrice = toFloat(bond.current_price);
  const faceValue = toFloat(bond.face_value);
  if (currentPrice === null || faceValue === null) return null;
  return (faceValue * currentPrice) / 100;
}

function annualCouponAmount(bond) {
  const nextCoupon = toFloat(bond.next_coupon);
  if (nextCoupon === null) return null;
  const perYear = couponsPerYear(bond);
  if (perYear === null) return null;
  return nextCoupon * perYear;
}

function calcCouponYield(bond) {
  const price = priceMoney(bond);
  const annualCoupon = annualCouponAmount(bond);
  if (price === null || annualCoupon === null || price <= 0) return null;
  return (annualCoupon / price) * 100;
}

function calcTotalYield(bond) {
  const price = priceMoney(bond);
  const annualCoupon = annualCouponAmount(bond);
  if (price === null || annualCoupon === null || price <= 0 || !bond.maturity_date) return null;
  const maturityDate = new Date(bond.maturity_date);
  if (Number.isNaN(maturityDate.getTime())) return null;
  const now = new Date();
  const daysToMaturity = Math.floor((maturityDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  if (daysToMaturity <= 0) return null;
  const yearsToMaturity = daysToMaturity / 365;
  if (yearsToMaturity <= 0) return null;
  const faceValue = toFloat(bond.face_value);
  if (faceValue === null) return null;
  const redemptionGainPerYear = (faceValue - price) / yearsToMaturity;
  return ((annualCoupon + redemptionGainPerYear) / price) * 100;
}

function fmtNum(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "н/д";
  return value.toFixed(2).replace(".", ",");
}

function formatCouponType(value) {
  const mapping = {
    fixed: "фиксированный",
    float: "плавающий",
    none: "без купона",
    unknown: "неизвестно",
  };
  if (!value) return "н/д";
  return mapping[value] || "неизвестно";
}

function formatCurrency(code) {
  if (!code) return "н/д";
  const mapping = {
    RUB: "руб",
    RUR: "руб",
    SUR: "руб",
    USD: "долл. США",
    EUR: "евро",
    CNY: "юань",
    GBP: "фунт стерл.",
    CHF: "швейц. франк",
    JPY: "иена",
  };
  return mapping[code] || `валюта ${code}`;
}

function formatNominal(bond) {
  const faceValue = toFloat(bond.face_value);
  const currency = formatCurrency(bond.currency);
  const amount =
    faceValue === null ? "н/д" : Number.isInteger(faceValue) ? String(faceValue) : faceValue.toFixed(2).replace(".", ",");
  if (amount === "н/д" && currency === "н/д") return "н/д";
  if (currency === "н/д") return amount;
  if (amount === "н/д") return currency;
  return `${amount} ${currency}`;
}

function formatMaturity(value) {
  if (!value) return "-";
  const maturityDate = new Date(value);
  if (Number.isNaN(maturityDate.getTime())) return String(value);
  const now = new Date();
  const daysLeft = Math.floor((maturityDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  if (daysLeft <= 0) return `${value} (погашена)`;
  const totalMonths = Math.max(0, Math.floor(daysLeft / 30));
  const years = Math.floor(totalMonths / 12);
  const months = totalMonths % 12;
  return `${value} (${years}г ${months}м)`;
}

function renderFuturesSearch(results) {
  futuresSearchResults.innerHTML = "";
  if (!results.length) {
    futuresSearchResults.innerHTML = "<div class='list-item'>Ничего не найдено</div>";
    return;
  }
  futuresSearchResults.innerHTML = results
    .map(
      (item) => `
      <article class="list-item">
        <div class="ticker">${escapeHtml(item.secid)}</div>
        <div class="contract">${escapeHtml(item.contract_name || item.shortname || "Без названия")}</div>
      </article>
    `,
    )
    .join("");
}

function drawCandles(dailyRows) {
  lastDailyRows = dailyRows;
  resizeCandlesCanvas();
  const ctx = candlesCanvas.getContext("2d");
  const width = Math.floor(candlesCanvas.width / (window.devicePixelRatio || 1));
  const height = Math.floor(candlesCanvas.height / (window.devicePixelRatio || 1));
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  const candles = dailyRows
    .map((row) => ({
      open: Number(row.open),
      high: Number(row.high),
      low: Number(row.low),
      close: Number(row.close),
    }))
    .filter((c) => [c.open, c.high, c.low, c.close].every((v) => Number.isFinite(v)));

  if (!candles.length) {
    ctx.fillStyle = "#7b8186";
    ctx.font = "16px Manrope";
    ctx.fillText("Нет данных для свечного графика", 20, 36);
    return;
  }

  const windowCandles = candles.slice(-120);
  const highs = windowCandles.map((c) => c.high);
  const lows = windowCandles.map((c) => c.low);
  const maxPrice = Math.max(...highs);
  const minPrice = Math.min(...lows);
  const span = maxPrice - minPrice || 1;
  const padTop = 20;
  const padBottom = 26;
  const padX = 12;
  const plotHeight = height - padTop - padBottom;
  const plotWidth = width - padX * 2;
  const step = plotWidth / windowCandles.length;
  const bodyWidth = Math.max(3, step * 0.65);

  const toY = (price) => padTop + ((maxPrice - price) / span) * plotHeight;

  ctx.strokeStyle = "#d7dfd4";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = padTop + (plotHeight / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padX, y);
    ctx.lineTo(width - padX, y);
    ctx.stroke();
  }

  windowCandles.forEach((c, idx) => {
    const x = padX + step * idx + step / 2;
    const up = c.close >= c.open;
    const color = up ? "#0d8a73" : "#cf3f2e";
    const highY = toY(c.high);
    const lowY = toY(c.low);
    const openY = toY(c.open);
    const closeY = toY(c.close);
    const topY = Math.min(openY, closeY);
    const bodyH = Math.max(1, Math.abs(openY - closeY));

    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, highY);
    ctx.lineTo(x, lowY);
    ctx.stroke();

    ctx.fillStyle = color;
    ctx.fillRect(x - bodyWidth / 2, topY, bodyWidth, bodyH);
  });

  ctx.fillStyle = "#616970";
  ctx.font = "12px Manrope";
  ctx.fillText(minPrice.toFixed(2), 12, height - 8);
  ctx.fillText(maxPrice.toFixed(2), 12, 14);
}

function renderBonds(bonds) {
  bondsTbody.innerHTML = "";
  if (!bonds.length) {
    bondsTbody.innerHTML = "<tr><td colspan='7'>Нет результатов</td></tr>";
    return;
  }
  bondsTbody.innerHTML = bonds
    .map(
      (bond) => {
        const couponYield = calcCouponYield(bond);
        const totalYield = calcTotalYield(bond);
        return `
      <tr>
        <td>${escapeHtml(bond.name)}</td>
        <td>${escapeHtml(formatMaturity(bond.maturity_date))}</td>
        <td>${escapeHtml(`${formatCouponType(bond.coupon_type)}, период ${bond.coupon_period ?? "н/д"} дн`)}</td>
        <td>${escapeHtml(`${fmtNum(couponYield)}%`)}</td>
        <td>${escapeHtml(`${fmtNum(totalYield)}%`)}</td>
        <td>${escapeHtml(formatNominal(bond))}</td>
        <td>${escapeHtml(`${fmtNum(toFloat(bond.current_price))}%`)}</td>
      </tr>
    `;
      },
    )
    .join("");
}

function activateTab(panelId, focusActiveButton = false) {
  const activeButton = tabButtons.find((button) => button.dataset.tabTarget === panelId);
  if (!activeButton) return;

  tabButtons.forEach((button) => {
    const isActive = button === activeButton;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
    button.tabIndex = isActive ? 0 : -1;
    if (isActive && focusActiveButton) {
      button.focus();
    }
  });

  tabPanels.forEach((panel) => {
    const isActive = panel.id === panelId;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });

  if (panelId === "panel-futures") {
    requestAnimationFrame(() => drawCandles(lastDailyRows));
  }
}

if (tabButtons.length && tabPanels.length) {
  tabButtons.forEach((button, index) => {
    button.addEventListener("click", () => {
      activateTab(button.dataset.tabTarget);
    });

    button.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const step = event.key === "ArrowRight" ? 1 : -1;
      const nextIndex = (index + step + tabButtons.length) % tabButtons.length;
      const nextButton = tabButtons[nextIndex];
      activateTab(nextButton.dataset.tabTarget, true);
    });
  });

  const selectedTab = tabButtons.find((button) => button.getAttribute("aria-selected") === "true") || tabButtons[0];
  activateTab(selectedTab.dataset.tabTarget);
}

futuresSearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const q = futuresQueryInput.value.trim();
  if (!q) return;
  setStatus(futuresSearchStatus, "Ищу контракты...");
  try {
    const payload = await fetchJson(`/api/futures/search?q=${encodeURIComponent(q)}&limit=12`);
    setStatus(futuresSearchStatus, `Найдено: ${payload.count}`);
    renderFuturesSearch(payload.results || []);
  } catch (error) {
    setStatus(futuresSearchStatus, error.message, true);
  }
});

candlesForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const ticker = candlesTickerInput.value.trim();
  if (!ticker) return;
  setStatus(candlesStatus, "Загружаю свечи...");
  candlesMeta.textContent = "";
  try {
    const payload = await fetchJson(`/api/futures/candles?ticker=${encodeURIComponent(ticker)}`);
    setStatus(candlesStatus, `Готово: ${payload.ticker}`);
    candlesMeta.textContent = `daily: ${payload.daily_count}, hourly: ${payload.hourly_count}`;
    drawCandles(payload.daily || []);
  } catch (error) {
    setStatus(candlesStatus, error.message, true);
    drawCandles([]);
  }
});

bondsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus(bondsStatus, "Подбираю облигации...");

  const params = new URLSearchParams();
  const fields = [
    ["currency", "bonds-currency"],
    ["coupon_type", "bonds-coupon-type"],
    ["bond_type", "bonds-type"],
    ["years_from", "bonds-years-from"],
    ["years_to", "bonds-years-to"],
    ["limit", "bonds-limit"],
  ];

  fields.forEach(([key, id]) => {
    const value = document.getElementById(id).value.trim();
    if (value !== "") params.set(key, value);
  });

  try {
    const payload = await fetchJson(`/api/bonds/search?${params.toString()}`);
    setStatus(bondsStatus, `Получено: ${payload.count}`);
    renderBonds(payload.results || []);
  } catch (error) {
    setStatus(bondsStatus, error.message, true);
    renderBonds([]);
  }
});

drawCandles([]);
window.addEventListener("resize", () => drawCandles(lastDailyRows));
window.addEventListener("resize", setViewportSizeVars);
window.addEventListener("orientationchange", () => {
  setTimeout(() => {
    setViewportSizeVars();
    drawCandles(lastDailyRows);
  }, 150);
});

setViewportSizeVars();
initTelegramWebApp();
