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
  const ctx = candlesCanvas.getContext("2d");
  const width = candlesCanvas.width;
  const height = candlesCanvas.height;
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
    bondsTbody.innerHTML = "<tr><td colspan='6'>Нет результатов</td></tr>";
    return;
  }
  bondsTbody.innerHTML = bonds
    .map(
      (bond) => `
      <tr>
        <td>${escapeHtml(bond.secid)}</td>
        <td>${escapeHtml(bond.name)}</td>
        <td>${escapeHtml(bond.maturity_date || "-")}</td>
        <td>${escapeHtml(bond.coupon_type || "-")}</td>
        <td>${escapeHtml(bond.currency || "-")}</td>
        <td>${bond.current_price ?? "-"}</td>
      </tr>
    `,
    )
    .join("");
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

