const HOMES = [
  { id: 1, name: "青羊 · 河畔家", area: "青羊区", size: 3, temp: 15.2, base: 9.4, color: "#087f70", quality: 99.8 },
  { id: 2, name: "高新 · 公寓", area: "高新区", size: 2, temp: 16.8, base: 7.1, color: "#2f65d9", quality: 99.5 },
  { id: 3, name: "温江 · 老宅", area: "温江区", size: 4, temp: 14.4, base: 11.8, color: "#d68818", quality: 99.9 },
  { id: 4, name: "天府 · 新居", area: "天府新区", size: 3, temp: 15.8, base: 8.9, color: "#c33974", quality: 99.6 },
  { id: 5, name: "龙泉 · 山居", area: "龙泉驿区", size: 2, temp: 13.9, base: 6.6, color: "#7458c8", quality: 99.4 }
];

const FILTER_FACTORS = {
  all: 1,
  exclude_ac: 0.79,
  exclude_heater: 0.87,
  exclude_fridge: 0.94
};

const MONTHS = [
  "1月", "2月", "3月", "4月", "5月", "6月",
  "7月", "8月", "9月", "10月", "11月", "12月"
];

const APPLIANCES = [
  { name: "空调", pct: 32, color: "#087f70" },
  { name: "热水器", pct: 24, color: "#d68818" },
  { name: "冰箱", pct: 18, color: "#2f65d9" },
  { name: "洗衣机", pct: 11, color: "#c33974" },
  { name: "照明与其他", pct: 15, color: "#829b91" }
];

const state = {
  selected: new Set([1, 2, 3]),
  range: 30,
  filter: "all",
  showAverage: true,
  predictMonth: 12
};

const chart = document.getElementById("chart");
const chartLegend = document.getElementById("chartLegend");
const chartTooltip = document.getElementById("chartTooltip");
const houseList = document.getElementById("houseList");
const toast = document.getElementById("toast");
const predictModal = document.getElementById("predictModal");

let chartData = [];
let averageData = [];
let chartGeometry = null;
let toastTimer = null;

function selectedHomes() {
  return HOMES.filter(function (home) {
    return state.selected.has(home.id);
  });
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function pointCount() {
  if (state.range === 7) return 7;
  if (state.range === 30) return 30;
  return 12;
}

function monthSeasonFactor(month) {
  return 1 + 0.14 * Math.cos(((month - 0.5) / 12) * Math.PI * 2 - 0.8);
}

function buildSeries(home, count, factor) {
  const values = [];
  const labels = [];
  const now = new Date(2023, 11, 31);

  for (let i = 0; i < count; i++) {
    let monthFactor = 1;
    let variation = 0;

    if (state.range === 12) {
      monthFactor = monthSeasonFactor(i + 1);
      variation = 0.07 * Math.sin((i + 1) * (home.id + 2) * 0.42);
      labels.push((i + 1) + "月");
    } else {
      const date = new Date(now);
      date.setDate(now.getDate() - (count - 1 - i));
      labels.push((date.getMonth() + 1) + "/" + date.getDate());
      variation =
        0.085 * Math.sin((i + home.id * 1.7) / 2.7) +
        0.045 * Math.cos((i + home.id) * 0.82);
    }

    values.push(home.base * monthFactor * (1 + variation) * factor);
  }

  return { home: home, labels: labels, values: values };
}

function buildChartData() {
  const count = pointCount();
  const factor = FILTER_FACTORS[state.filter];
  const selectedSeries = selectedHomes().map(function (home) {
    return buildSeries(home, count, factor);
  });
  const allSeries = HOMES.map(function (home) {
    return buildSeries(home, count, factor);
  });
  const averages = allSeries[0].values.map(function (_, index) {
    const total = allSeries.reduce(function (sum, series) {
      return sum + series.values[index];
    }, 0);
    return total / allSeries.length;
  });

  chartData = selectedSeries;
  averageData = averages;
}

function tickIndices(count) {
  if (count <= 7) {
    return Array.from({ length: count }, function (_, index) {
      return index;
    });
  }
  if (count === 12) return [0, 2, 4, 6, 8, 10, 11];
  return [0, 5, 10, 15, 20, 25, 29];
}

function renderChart() {
  const W = 960;
  const H = 470;
  const pad = { top: 22, right: 22, bottom: 40, left: 49 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;
  const allValues = chartData.flatMap(function (series) {
    return series.values;
  });

  if (state.showAverage) {
    allValues.push.apply(allValues, averageData);
  }
  if (!allValues.length) return;

  const rawMin = Math.min.apply(null, allValues);
  const rawMax = Math.max.apply(null, allValues);
  const boundsPad = Math.max((rawMax - rawMin) * 0.18, 1.1);
  const bounds = {
    min: Math.max(0, Math.floor(rawMin - boundsPad)),
    max: Math.ceil(rawMax + boundsPad)
  };

  const xFor = function (index) {
    return pad.left + (plotW * index) / Math.max(1, pointCount() - 1);
  };
  const yFor = function (value) {
    return pad.top + plotH - ((value - bounds.min) / Math.max(1, bounds.max - bounds.min)) * plotH;
  };

  chartGeometry = {
    W: W,
    H: H,
    pad: pad,
    plotW: plotW,
    plotH: plotH,
    bounds: bounds,
    xFor: xFor,
    yFor: yFor
  };

  let grid = "";
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (plotH / 4) * i;
    const value = bounds.max - ((bounds.max - bounds.min) / 4) * i;
    grid += '<line class="grid-line" x1="' + pad.left + '" y1="' + y +
      '" x2="' + (W - pad.right) + '" y2="' + y + '"></line>';
    grid += '<text class="axis-label" x="' + (pad.left - 10) + '" y="' + (y + 3) +
      '" text-anchor="end">' + value.toFixed(1) + "</text>";
  }

  grid += '<text class="axis-unit" x="' + pad.left + '" y="13">KWH / HOME / DAY</text>';

  const labels = chartData[0] ? chartData[0].labels : [];
  tickIndices(pointCount()).forEach(function (index) {
    grid += '<text class="axis-label" x="' + xFor(index) + '" y="' + (H - 12) +
      '" text-anchor="middle">' + labels[index] + "</text>";
  });

  const linePath = function (values) {
    return values.map(function (value, index) {
      return (index === 0 ? "M " : "L ") + xFor(index) + " " + yFor(value);
    }).join(" ");
  };

  let averageMarkup = "";
  if (state.showAverage) {
    averageMarkup = '<path class="average-line" d="' + linePath(averageData) + '"></path>';
  }

  let seriesMarkup = "";
  chartData.forEach(function (series) {
    const lastIndex = series.values.length - 1;
    const lastX = xFor(lastIndex);
    const lastY = yFor(series.values[lastIndex]);
    seriesMarkup += '<path class="series-line" stroke="' + series.home.color +
      '" d="' + linePath(series.values) + '"></path>';
    seriesMarkup += '<circle class="end-dot" cx="' + lastX + '" cy="' + lastY +
      '" r="3.6" fill="' + series.home.color + '"></circle>';
  });

  chart.innerHTML =
    grid +
    averageMarkup +
    seriesMarkup +
    '<line class="hover-line" x1="0" y1="' + pad.top + '" x2="0" y2="' +
      (pad.top + plotH) + '"></line>' +
    '<g class="hover-dots"></g>';

  renderLegend();
}

function renderLegend() {
  const items = chartData.map(function (series) {
    return '<span class="legend-item"><span class="legend-dot" style="--legend-color:' +
      series.home.color + '"></span>' + series.home.name + "</span>";
  });

  if (state.showAverage) {
    items.push('<span class="legend-item"><span class="legend-line dashed"></span>全部家庭平均</span>');
  }
  chartLegend.innerHTML = items.join("");
}

function updateTooltip(event) {
  if (!chartGeometry || !chartData.length) return;

  const rect = chart.getBoundingClientRect();
  const localX = (event.clientX - rect.left) / rect.width * chartGeometry.W;
  const ratio = clamp((localX - chartGeometry.pad.left) / chartGeometry.plotW, 0, 1);
  const index = Math.round(ratio * (pointCount() - 1));
  const x = chartGeometry.xFor(index);
  const line = chart.querySelector(".hover-line");
  const dots = chart.querySelector(".hover-dots");

  line.setAttribute("x1", x);
  line.setAttribute("x2", x);
  line.style.opacity = "0.72";

  dots.innerHTML = chartData.map(function (series) {
    return '<circle class="hover-dot" cx="' + x + '" cy="' +
      chartGeometry.yFor(series.values[index]) + '" r="4" fill="' + series.home.color +
      '" style="opacity:1"></circle>';
  }).join("");

  const rows = chartData.map(function (series) {
    return '<div class="tt-row"><span class="tt-name"><span class="tt-dot" style="background:' +
      series.home.color + '"></span>' + series.home.name +
      '</span><span class="tt-value">' + series.values[index].toFixed(1) + "</span></div>";
  }).join("");

  chartTooltip.innerHTML =
    '<div class="tt-date">' + chartData[0].labels[index] + " · kWh</div>" + rows;
  chartTooltip.style.left = clamp(x / chartGeometry.W * 100, 10, 90) + "%";
  chartTooltip.classList.add("show");
}

function hideTooltip() {
  chartTooltip.classList.remove("show");
  const line = chart.querySelector(".hover-line");
  const dots = chart.querySelector(".hover-dots");
  if (line) line.style.opacity = "0";
  if (dots) dots.innerHTML = "";
}

function renderHouseList() {
  houseList.innerHTML = HOMES.map(function (home) {
    const checked = state.selected.has(home.id);
    return '<label class="house-row' + (checked ? " selected" : "") + '">' +
      '<input type="checkbox" data-id="' + home.id + '"' + (checked ? " checked" : "") + ">" +
      '<span class="checkmark" aria-hidden="true">' +
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">' +
          '<path d="m3 8 3.2 3.2L13 4.8"></path>' +
        "</svg>" +
      "</span>" +
      '<span class="house-dot" style="--dot:' + home.color + '"></span>' +
      '<span><span class="house-name">' + home.name + "</span>" +
        '<span class="house-meta">' + home.area + " · " + home.size + " 人 · " +
        home.temp.toFixed(1) + "°C</span></span>" +
      '<span class="house-kwh">' + home.base.toFixed(1) + "<small> kWh</small></span>" +
    "</label>";
  }).join("");

  houseList.querySelectorAll("input").forEach(function (input) {
    input.addEventListener("change", function () {
      const id = Number(input.dataset.id);

      if (input.checked && state.selected.size >= 5) {
        input.checked = false;
        showToast("最多同时对比 5 户家庭");
        return;
      }

      if (!input.checked && state.selected.size === 1) {
        input.checked = true;
        showToast("至少保留 1 户家庭");
        return;
      }

      if (input.checked) state.selected.add(id);
      else state.selected.delete(id);
      refresh();
    });
  });
}

function updateSelectionUI() {
  const count = state.selected.size;
  document.getElementById("selectionCount").textContent = count + " / 5";
  document.getElementById("selectionProgress").style.width = (count / 5 * 100) + "%";
  document.getElementById("chartCompareBadge").textContent = "对比 " + count + " 户";
}

function renderMetrics() {
  const homes = selectedHomes();
  const factor = FILTER_FACTORS[state.filter];
  const selectedMean = homes.reduce(function (sum, home) {
    return sum + home.base * factor;
  }, 0) / homes.length;
  const allMean = HOMES.reduce(function (sum, home) {
    return sum + home.base * factor;
  }, 0) / HOMES.length;
  const compare = ((selectedMean - allMean) / allMean) * 100;
  const temp = homes.reduce(function (sum, home) {
    return sum + home.temp;
  }, 0) / homes.length;
  const quality = homes.reduce(function (sum, home) {
    return sum + home.quality;
  }, 0) / homes.length;
  const rangeLabel = state.range === 7 ? "近 7 天" : state.range === 30 ? "近 30 天" : "近 12 月";

  document.getElementById("metricDaily").innerHTML = selectedMean.toFixed(1) + " <small>kWh</small>";
  document.getElementById("metricDailyMeta").textContent = rangeLabel + " · " + homes.length + " 户家庭";
  document.getElementById("metricTemp").innerHTML = temp.toFixed(1) + " <small>°C</small>";
  document.getElementById("metricCompare").innerHTML =
    (compare >= 0 ? "+" : "") + compare.toFixed(1) + " <small>%</small>";
  document.getElementById("metricQuality").innerHTML = quality.toFixed(1) + " <small>%</small>";
  document.getElementById("qualityNumber").textContent = quality.toFixed(1) + "%";
  document.getElementById("qualityRing").style.setProperty("--pct", quality.toFixed(1));
}

function renderChartInsights() {
  const homes = selectedHomes();
  const factor = FILTER_FACTORS[state.filter];
  const peak = homes.slice().sort(function (a, b) {
    return b.base - a.base;
  })[0];
  const minTemp = Math.min.apply(null, homes.map(function (home) { return home.temp; }));
  const maxTemp = Math.max.apply(null, homes.map(function (home) { return home.temp; }));
  const latest = chartData[0] ? chartData[0].values[chartData[0].values.length - 1] : 0;
  const rangeLabel = state.range === 7 ? "近 7 天" : state.range === 30 ? "近 30 天" : "近 12 月";

  document.getElementById("chartInsights").innerHTML =
    '<div class="insight"><span class="insight-label">最高日均用电</span><span class="insight-value">' +
      peak.name + ' · ' + (peak.base * factor).toFixed(1) + ' kWh</span></div>' +
    '<div class="insight"><span class="insight-label">平均温度区间</span><span class="insight-value">' +
      minTemp.toFixed(1) + ' – ' + maxTemp.toFixed(1) + ' °C</span></div>' +
    '<div class="insight"><span class="insight-label">' + rangeLabel + ' 最新值</span><span class="insight-value">' +
      latest.toFixed(1) + ' kWh · ' + (state.showAverage ? '全部均值已叠加' : '仅所选家庭') + '</span></div>';
}

function renderCompareTable() {
  const homes = selectedHomes().slice().sort(function (a, b) {
    return b.base - a.base;
  });
  const factor = FILTER_FACTORS[state.filter];

  document.getElementById("compareBody").innerHTML = homes.map(function (home) {
    const daily = home.base * factor;
    return "<tr>" +
      '<td><span class="name-cell"><span class="table-dot" style="background:' +
        home.color + '"></span>' + home.name + "</span></td>" +
      "<td>" + home.size + "</td>" +
      '<td class="strong">' + daily.toFixed(1) + "</td>" +
      "<td>" + (daily / home.size).toFixed(1) + "</td>" +
      "<td>" + home.temp.toFixed(1) + "°C</td>" +
    "</tr>";
  }).join("");

  const temps = homes.map(function (home) {
    return home.temp;
  });
  const spread = Math.max.apply(null, temps) - Math.min.apply(null, temps);
  document.getElementById("compareSummary").textContent = homes.length + " 户家庭 · 按日均用电排序";
  document.getElementById("compareNote").textContent =
    "当前选中 " + homes.length + " 户，最大平均温差 " + spread.toFixed(1) + "°C。";
}

function renderApplianceBars() {
  document.getElementById("applianceBars").innerHTML = APPLIANCES.map(function (item) {
    return '<div class="bar-row">' +
      '<span class="bar-name">' + item.name + "</span>" +
      '<div class="bar-track"><div class="bar-fill" style="--w:' + item.pct +
        "%;--bar-color:" + item.color + '"></div></div>' +
      '<span class="bar-pct">' + item.pct + "%</span>" +
    "</div>";
  }).join("");
}

function findHome(homeId) {
  return HOMES.find(function (home) {
    return home.id === homeId;
  });
}

function renderPredictControls() {
  const monthSelect = document.getElementById("predictMonth");
  const houseSelect = document.getElementById("predictHouse");

  monthSelect.innerHTML = MONTHS.map(function (label, index) {
    const month = index + 1;
    return '<option value="' + month + '"' +
      (month === state.predictMonth ? " selected" : "") + ">" + label + "</option>";
  }).join("");

  houseSelect.innerHTML = HOMES.map(function (home) {
    return '<option value="' + home.id + '">' + home.name + " · " + home.area + "</option>";
  }).join("");

  const selectedHome = selectedHomes()[0] || HOMES[0];
  houseSelect.value = String(selectedHome.id);
  syncPopulationToHouse();
}

function syncPopulationToHouse() {
  const home = findHome(Number(document.getElementById("predictHouse").value)) || HOMES[0];
  document.getElementById("predictPopulation").value = String(home.size);
}

function calculateForecast(announce) {
  const monthSelect = document.getElementById("predictMonth");
  const houseSelect = document.getElementById("predictHouse");
  const populationInput = document.getElementById("predictPopulation");
  const home = findHome(Number(houseSelect.value)) || HOMES[0];
  const month = Number(monthSelect.value);
  const population = Number(populationInput.value);

  if (!Number.isInteger(population) || population < 1 || population > 20) {
    document.getElementById("predictedValue").innerHTML = "— <small>kWh/日</small>";
    document.getElementById("predictionMeta").textContent = "人口需填写 1–20 的整数";
    if (announce) {
      showToast("人口请输入 1–20 的整数");
      populationInput.focus();
    }
    return;
  }

  const prediction =
    home.base *
    monthSeasonFactor(month) *
    Math.pow(population / home.size, 0.38);
  const monthLabel = MONTHS[month - 1];

  document.getElementById("predictedValue").innerHTML =
    prediction.toFixed(1) + " <small>kWh/日</small>";
  document.getElementById("predictionMeta").textContent =
    monthLabel + " 典型日 · " + home.name;
  document.getElementById("resultMonth").textContent = monthLabel;
  document.getElementById("resultHouse").textContent = home.name;
  document.getElementById("resultPopulation").textContent = population + " 人";

  if (announce) {
    showToast("已生成 " + monthLabel + " 用电预测");
  }
}

function openPredictionModal() {
  calculateForecast(false);
  predictModal.classList.add("open");
  predictModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  window.setTimeout(function () {
    document.getElementById("predictMonth").focus();
  }, 80);
}

function closePredictionModal() {
  predictModal.classList.remove("open");
  predictModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
  document.getElementById("openPredictBtn").focus();
}

function stepPopulation(delta) {
  const input = document.getElementById("predictPopulation");
  const current = Number(input.value);
  const next = Number.isFinite(current) ? current + delta : 1;
  input.value = String(clamp(Math.round(next), 1, 20));
  calculateForecast(false);
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(function () {
    toast.classList.remove("show");
  }, 2200);
}

function refresh() {
  renderHouseList();
  updateSelectionUI();
  buildChartData();
  renderChart();
  renderMetrics();
  renderChartInsights();
  renderCompareTable();
}

document.getElementById("rangeTabs").addEventListener("click", function (event) {
  const button = event.target.closest("[data-range]");
  if (!button) return;
  state.range = Number(button.dataset.range);
  document.querySelectorAll(".range-tab").forEach(function (tab) {
    tab.classList.toggle("active", tab === button);
  });
  buildChartData();
  renderChart();
  renderMetrics();
  renderChartInsights();
});

document.getElementById("applianceFilter").addEventListener("change", function (event) {
  state.filter = event.target.value;
  buildChartData();
  renderChart();
  renderMetrics();
  renderChartInsights();
  renderCompareTable();
});

document.getElementById("averageToggle").addEventListener("change", function (event) {
  state.showAverage = event.target.checked;
  renderChart();
  renderChartInsights();
});

chart.addEventListener("pointermove", updateTooltip);
chart.addEventListener("pointerleave", hideTooltip);

document.getElementById("openPredictBtn").addEventListener("click", openPredictionModal);
document.getElementById("closePredictBtn").addEventListener("click", closePredictionModal);

document.getElementById("predictHouse").addEventListener("change", function () {
  syncPopulationToHouse();
  calculateForecast(false);
});

document.getElementById("predictMonth").addEventListener("change", function (event) {
  state.predictMonth = Number(event.target.value);
  calculateForecast(false);
});

document.getElementById("predictPopulation").addEventListener("input", function () {
  calculateForecast(false);
});

document.getElementById("predictForm").addEventListener("submit", function (event) {
  event.preventDefault();
  calculateForecast(true);
});

document.getElementById("populationMinus").addEventListener("click", function () {
  stepPopulation(-1);
});

document.getElementById("populationPlus").addEventListener("click", function () {
  stepPopulation(1);
});

predictModal.addEventListener("click", function (event) {
  if (event.target === predictModal) closePredictionModal();
});

document.addEventListener("keydown", function (event) {
  if (event.key === "Escape" && predictModal.classList.contains("open")) {
    closePredictionModal();
  }
});

renderApplianceBars();
renderPredictControls();
refresh();
