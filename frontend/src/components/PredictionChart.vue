<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { PredictForecastPoint, PredictHistoryPoint } from '../api/types'
import {
  axisValue,
  formatKwh,
  formatPeriodCn,
  formatPeriodShort
} from '../utils/format'

const props = withDefaults(
  defineProps<{
    history: PredictHistoryPoint[]
    forecast: PredictForecastPoint[]
    householdName: string
    anchorMonth: string | null
    historyBasis: 'aggregate' | 'appliance_sum' | 'mixed' | 'none'
    loading?: boolean
  }>(),
  { loading: false }
)

interface Point {
  x: number
  y: number
  index: number
  value: number
}

const stage = ref<HTMLElement | null>(null)
const width = ref(920)
const height = ref(300)
const hoverIndex = ref<number | null>(null)
const hoverPercent = ref(0)
let observer: ResizeObserver | null = null

const basisLabel = computed(() => {
  if (props.historyBasis === 'aggregate') return 'Aggregate 优先'
  if (props.historyBasis === 'appliance_sum') return '分项汇总'
  if (props.historyBasis === 'mixed') return 'Aggregate + 分项'
  return '暂无历史口径'
})

function periodIndex(period: string): number {
  return Number(period.slice(0, 4)) * 12 + Number(period.slice(5, 7)) - 1
}

function periodFromIndex(index: number): string {
  const year = Math.floor(index / 12)
  const month = (index % 12) + 1
  return `${year}-${String(month).padStart(2, '0')}`
}

function linePath(points: Point[]): string {
  if (!points.length) return ''
  return points
    .map((point, index) => {
      const command = index === 0 ? 'M' : 'L'
      return `${command} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`
    })
    .join(' ')
}

function splitPaths(points: Array<Point | null>): string[] {
  const paths: string[] = []
  let segment: Point[] = []
  for (const point of points) {
    if (point) {
      segment.push(point)
    } else if (segment.length) {
      paths.push(linePath(segment))
      segment = []
    }
  }
  if (segment.length) paths.push(linePath(segment))
  return paths
}

function tickIndexes(count: number, chartWidth: number): number[] {
  if (count <= 1) return count ? [0] : []
  const maxTicks = chartWidth < 460 ? 4 : chartWidth < 720 ? 5 : 7
  if (count <= maxTicks) {
    return Array.from({ length: count }, (_, index) => index)
  }
  const indexes = new Set<number>()
  for (let slot = 0; slot < maxTicks; slot += 1) {
    indexes.add(Math.round(((count - 1) * slot) / (maxTicks - 1)))
  }
  return Array.from(indexes).sort((a, b) => a - b)
}

const chart = computed(() => {
  const historyMap = new Map(
    props.history.map((point) => [point.period, point])
  )
  const forecastMap = new Map(
    props.forecast.map((point) => [point.period, point])
  )
  const available = [...historyMap.keys(), ...forecastMap.keys()].sort()
  const periods: string[] = []
  if (available.length) {
    const start = periodIndex(available[0])
    const end = periodIndex(available[available.length - 1])
    for (let index = start; index <= end; index += 1) {
      periods.push(periodFromIndex(index))
    }
  }

  const pad = { top: 24, right: 16, bottom: 34, left: 44 }
  const plotWidth = Math.max(160, width.value - pad.left - pad.right)
  const plotHeight = Math.max(150, height.value - pad.top - pad.bottom)
  const historyValues = periods.map(
    (period) => historyMap.get(period)?.actual_avg_daily_kwh ?? null
  )
  const forecastValues = periods.map(
    (period) => forecastMap.get(period)?.predicted_avg_daily_kwh ?? null
  )
  const values = [...historyValues, ...forecastValues].filter(
    (value): value is number => value !== null && Number.isFinite(value)
  )
  const rawMin = values.length ? Math.min(...values) : 0
  const rawMax = values.length ? Math.max(...values) : 1
  const span = Math.max(rawMax - rawMin, 0.6)
  const yMin = Number(Math.max(0, rawMin - span * 0.2).toFixed(1))
  const yMax = Number((rawMax + span * 0.24).toFixed(1))
  const xAt = (index: number) =>
    pad.left + (plotWidth * index) / Math.max(1, periods.length - 1)
  const yAt = (value: number) =>
    pad.top +
    plotHeight -
    ((value - yMin) / Math.max(0.001, yMax - yMin)) * plotHeight

  const historyPoints = periods.map((_, index) => {
    const value = historyValues[index]
    return value === null
      ? null
      : { x: xAt(index), y: yAt(value), index, value }
  })
  const forecastPoints = periods.map((_, index) => {
    const value = forecastValues[index]
    return value === null
      ? null
      : { x: xAt(index), y: yAt(value), index, value }
  })
  const lastHistoryIndex = historyValues.reduce<number>(
    (last, value, index) => (value === null ? last : index),
    -1
  )
  const firstForecastIndex = forecastValues.findIndex((value) => value !== null)
  const historyPath = splitPaths(historyPoints)
  const forecastPaths = splitPaths(forecastPoints)
  if (
    lastHistoryIndex >= 0 &&
    firstForecastIndex === lastHistoryIndex + 1
  ) {
    const connector = historyPoints[lastHistoryIndex]
    const firstForecast = forecastPoints[firstForecastIndex]
    if (connector && firstForecast) {
      forecastPaths.unshift(linePath([connector, firstForecast]))
    }
  }

  const yTicks = Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3
    const value = yMax - (yMax - yMin) * ratio
    return {
      value,
      y: pad.top + plotHeight * ratio,
      label: axisValue(value)
    }
  })
  const forecastStartX =
    firstForecastIndex >= 0 ? xAt(firstForecastIndex) : pad.left + plotWidth

  return {
    width: width.value,
    height: height.value,
    pad,
    plotWidth,
    plotHeight,
    periods,
    historyMap,
    forecastMap,
    historyValues,
    forecastValues,
    historyPoints,
    forecastPoints,
    historyPath,
    forecastPaths,
    yTicks,
    xTicks: tickIndexes(periods.length, width.value).map((index) => ({
      index,
      x: xAt(index),
      label: formatPeriodShort(periods[index])
    })),
    forecastStartX,
    lastHistoryIndex,
    firstForecastIndex,
    xAt,
    yAt
  }
})

const selectedPeriod = computed(() => {
  if (
    hoverIndex.value === null ||
    hoverIndex.value < 0 ||
    hoverIndex.value >= chart.value.periods.length
  ) {
    return null
  }
  const period = chart.value.periods[hoverIndex.value]
  return {
    period,
    history: chart.value.historyMap.get(period) ?? null,
    forecast: chart.value.forecastMap.get(period) ?? null,
    x: chart.value.xAt(hoverIndex.value)
  }
})

const tooltipLeft = computed(() =>
  Math.min(86, Math.max(14, hoverPercent.value))
)

function onChartMove(event: MouseEvent): void {
  const count = chart.value.periods.length
  if (!count) return
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const xPercent = Math.min(
    100,
    Math.max(0, ((event.clientX - rect.left) / rect.width) * 100)
  )
  const plotStart = (chart.value.pad.left / chart.value.width) * 100
  const plotEnd =
    ((chart.value.width - chart.value.pad.right) / chart.value.width) * 100
  const ratio = Math.min(
    1,
    Math.max(0, (xPercent - plotStart) / (plotEnd - plotStart))
  )
  hoverPercent.value = xPercent
  hoverIndex.value = Math.round(ratio * (count - 1))
}

const chartWindow = computed(() => {
  const periods = chart.value.periods
  if (!periods.length) return '暂无曲线数据'
  return `${formatPeriodCn(periods[0])} — ${formatPeriodCn(periods[periods.length - 1])}`
})

onMounted(() => {
  if (!stage.value) return
  observer = new ResizeObserver((entries) => {
    const rect = entries[0]?.contentRect
    if (!rect) return
    width.value = Math.max(300, Math.round(rect.width))
    height.value = Math.max(230, Math.round(rect.height))
  })
  observer.observe(stage.value)
})

onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <section class="card prediction-chart-card" aria-label="历史与预测曲线">
    <header class="prediction-chart-head">
      <div>
        <span class="prediction-chart-kicker">HISTORY + FORECAST</span>
        <h2>历史用电与预测曲线</h2>
        <p>{{ props.householdName }} · {{ chartWindow }} · 实线为实际值，虚线为模型预测</p>
      </div>
      <span class="prediction-basis">{{ basisLabel }}</span>
    </header>

    <div class="prediction-chart-legend">
      <span class="prediction-legend-item">
        <i class="prediction-legend-line history"></i>
        历史实际
      </span>
      <span class="prediction-legend-item">
        <i class="prediction-legend-line forecast"></i>
        未来预测
      </span>
      <span v-if="props.anchorMonth" class="prediction-legend-item muted">
        历史截至 {{ formatPeriodCn(props.anchorMonth) }}
      </span>
    </div>

    <div
      ref="stage"
      class="prediction-chart-stage"
      @mousemove="onChartMove"
      @mouseleave="hoverIndex = null"
    >
      <svg
        class="prediction-chart-svg"
        :viewBox="`0 0 ${chart.width} ${chart.height}`"
        role="img"
        aria-label="选定家庭的历史与预测用电曲线"
      >
        <defs>
          <linearGradient id="predictionHistoryArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#4e8ff0" stop-opacity="0.16" />
            <stop offset="100%" stop-color="#4e8ff0" stop-opacity="0" />
          </linearGradient>
          <linearGradient id="predictionForecastArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#8b68f4" stop-opacity="0.13" />
            <stop offset="100%" stop-color="#8b68f4" stop-opacity="0" />
          </linearGradient>
        </defs>

        <rect
          v-if="chart.firstForecastIndex >= 0"
          class="forecast-band"
          :x="chart.forecastStartX"
          :y="chart.pad.top"
          :width="Math.max(0, chart.width - chart.pad.right - chart.forecastStartX)"
          :height="chart.plotHeight"
        />

        <g v-for="tick in chart.yTicks" :key="'y-' + tick.value">
          <line
            class="grid-line"
            :x1="chart.pad.left"
            :x2="chart.width - chart.pad.right"
            :y1="tick.y"
            :y2="tick.y"
          />
          <text
            class="axis-label"
            :x="chart.pad.left - 9"
            :y="tick.y + 3"
            text-anchor="end"
          >{{ tick.label }}</text>
        </g>
        <text class="axis-unit" :x="chart.pad.left" y="10">KWH / DAY</text>

        <path
          v-for="(path, index) in chart.historyPath"
          :key="'history-' + index"
          class="history-line"
          :d="path"
        />
        <path
          v-for="(path, index) in chart.forecastPaths"
          :key="'forecast-' + index"
          class="forecast-line"
          :d="path"
        />

        <line
          v-if="chart.firstForecastIndex >= 0"
          class="forecast-divider"
          :x1="chart.forecastStartX"
          :x2="chart.forecastStartX"
          :y1="chart.pad.top"
          :y2="chart.height - chart.pad.bottom"
        />
        <text
          v-if="chart.firstForecastIndex >= 0"
          class="forecast-divider-label"
          :x="chart.forecastStartX + 6"
          :y="chart.pad.top + 10"
        >预测起点</text>

        <g v-for="tick in chart.xTicks" :key="'x-' + tick.index">
          <text
            class="axis-label"
            :x="tick.x"
            :y="chart.height - 9"
            text-anchor="middle"
          >{{ tick.label }}</text>
        </g>

        <circle
          v-if="chart.lastHistoryIndex >= 0 && chart.historyPoints[chart.lastHistoryIndex]"
          class="history-dot"
          :cx="chart.historyPoints[chart.lastHistoryIndex]?.x"
          :cy="chart.historyPoints[chart.lastHistoryIndex]?.y"
          r="3.4"
        />

        <g v-if="selectedPeriod">
          <line
            class="hover-line"
            :x1="selectedPeriod.x"
            :x2="selectedPeriod.x"
            :y1="chart.pad.top"
            :y2="chart.height - chart.pad.bottom"
          />
          <circle
            v-if="selectedPeriod.history"
            class="hover-dot history"
            :cx="selectedPeriod.x"
            :cy="chart.yAt(selectedPeriod.history.actual_avg_daily_kwh)"
            r="3.5"
          />
          <circle
            v-if="selectedPeriod.forecast"
            class="hover-dot forecast"
            :cx="selectedPeriod.x"
            :cy="chart.yAt(selectedPeriod.forecast.predicted_avg_daily_kwh)"
            r="3.5"
          />
        </g>
      </svg>

      <div
        v-if="selectedPeriod"
        class="chart-tooltip prediction-tooltip"
        :style="{ left: tooltipLeft + '%' }"
      >
        <div class="tooltip-date">{{ formatPeriodCn(selectedPeriod.period) }}</div>
        <div v-if="selectedPeriod.history" class="tooltip-row">
          <span class="tt-dot" style="--tt-color: #4e8ff0"></span>
          <span>历史实际</span>
          <strong>{{ formatKwh(selectedPeriod.history.actual_avg_daily_kwh) }}</strong>
        </div>
        <div v-if="selectedPeriod.forecast" class="tooltip-row">
          <span class="tt-dot" style="--tt-color: #9a78ff"></span>
          <span>模型预测</span>
          <strong>{{ formatKwh(selectedPeriod.forecast.predicted_avg_daily_kwh) }}</strong>
        </div>
        <div
          v-if="selectedPeriod.history?.temperature_c != null || selectedPeriod.forecast"
          class="tooltip-row prediction-temp-row"
        >
          <span class="tt-dot"></span>
          <span>平均温度</span>
          <strong>
            {{
              selectedPeriod.history?.temperature_c ??
                selectedPeriod.forecast?.temperature_used_c
            }} °C
          </strong>
        </div>
      </div>

      <div v-if="!chart.periods.length" class="prediction-chart-empty">
        生成预测后显示历史与未来曲线
      </div>
      <div v-if="props.loading" class="chart-loading">
        <span class="spinner" aria-label="正在生成预测"></span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.prediction-chart-card {
  min-height: 350px;
  display: flex;
  flex-direction: column;
  margin-top: 16px;
  padding: 18px 19px 12px;
}

.prediction-chart-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.prediction-chart-kicker {
  display: block;
  margin-bottom: 5px;
  color: #7c5ef0;
  font-size: 7.5px;
  font-weight: 720;
  letter-spacing: 0.11em;
}

.prediction-chart-head h2 {
  margin: 0;
  color: #263244;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.prediction-chart-head p {
  margin: 4px 0 0;
  color: #9099a7;
  font-size: 9.5px;
}

.prediction-basis {
  flex: 0 0 auto;
  padding: 5px 9px;
  border: 1px solid rgba(139, 92, 246, 0.12);
  border-radius: 999px;
  color: #7a63cb;
  background: rgba(139, 92, 246, 0.06);
  font-size: 8px;
  font-weight: 650;
}

.prediction-chart-legend {
  min-height: 24px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px 14px;
  margin-top: 8px;
}

.prediction-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #788494;
  font-size: 9px;
  font-weight: 540;
}

.prediction-legend-item.muted {
  color: #9aa3b1;
}

.prediction-legend-line {
  width: 16px;
  height: 0;
  border-top: 2px solid #4e8ff0;
}

.prediction-legend-line.forecast {
  border-top: 2px dashed #8b68f4;
}

.prediction-chart-stage {
  position: relative;
  min-height: 260px;
  flex: 1;
  margin-top: 2px;
  cursor: crosshair;
}

.prediction-chart-svg {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.forecast-band {
  fill: rgba(139, 104, 244, 0.035);
}

.grid-line {
  stroke: rgba(65, 85, 112, 0.085);
  stroke-width: 1;
  stroke-dasharray: 2 5;
}

.axis-label {
  fill: #979fad;
  font-size: 8.5px;
  font-family: var(--font);
  font-variant-numeric: tabular-nums;
}

.axis-unit {
  fill: #a5adba;
  font-size: 7.5px;
  font-family: var(--font);
  font-weight: 650;
  letter-spacing: 0.09em;
}

.history-line,
.forecast-line {
  fill: none;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.history-line {
  stroke: #4e8ff0;
  filter: drop-shadow(0 3px 4px rgba(50, 112, 206, 0.12));
}

.forecast-line {
  stroke: #8b68f4;
  stroke-dasharray: 6 5;
  filter: drop-shadow(0 3px 4px rgba(109, 78, 217, 0.12));
}

.forecast-divider {
  stroke: rgba(122, 99, 203, 0.22);
  stroke-width: 1;
  stroke-dasharray: 3 4;
}

.forecast-divider-label {
  fill: #806ac8;
  font-size: 7.5px;
  font-family: var(--font);
  font-weight: 650;
}

.history-dot {
  fill: #fff;
  stroke: #4e8ff0;
  stroke-width: 2;
}

.hover-line {
  stroke: rgba(62, 89, 128, 0.25);
  stroke-width: 1;
  stroke-dasharray: 2 3;
}

.hover-dot {
  stroke: #fff;
  stroke-width: 1.8;
}

.hover-dot.history {
  fill: #4e8ff0;
}

.hover-dot.forecast {
  fill: #8b68f4;
}

.prediction-tooltip {
  width: 150px;
}

.prediction-temp-row {
  margin-top: 3px;
  padding-top: 4px;
  border-top: 1px solid rgba(255, 255, 255, 0.13);
}

.prediction-temp-row .tt-dot {
  border: 1px solid rgba(255, 255, 255, 0.5);
  background: transparent;
}

.prediction-chart-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #9aa4b3;
  font-size: 10px;
}

@media (max-width: 720px) {
  .prediction-chart-card {
    padding: 15px 13px 9px;
  }

  .prediction-chart-head {
    flex-direction: column;
    gap: 7px;
  }

  .prediction-chart-stage {
    min-height: 235px;
  }
}
</style>
