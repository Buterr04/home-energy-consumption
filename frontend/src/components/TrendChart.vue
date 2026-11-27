<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { FILTER_OPTIONS, useEnergyStore } from '../stores/energy'
import { buildChart } from '../utils/chart'
import { formatKwh, formatPeriodCn } from '../utils/format'
import AppIcon from './AppIcon.vue'

const props = withDefaults(
  defineProps<{
    title?: string
    analysis?: boolean
  }>(),
  {
    title: '用电趋势',
    analysis: false
  }
)

const store = useEnergyStore()
const state = store.state
const hoverIndex = ref<number | null>(null)
const hoverPercent = ref(0)
const filterOpen = ref(false)
const filterWrap = ref<HTMLElement | null>(null)

const chart = computed(() =>
  buildChart(
    state.seriesData,
    state.averageData,
    store.granularity(),
    hoverIndex.value,
    hoverPercent.value
  )
)

const chartWindowLabel = computed(() => {
  const periods = chart.value.periods
  if (!periods.length) return '暂无数据'
  if (store.granularity() === 'month') {
    return `${periods[0].slice(0, 4)} 年 1 月 — 12 月`
  }
  return `${formatPeriodCn(periods[0])} — ${formatPeriodCn(periods[periods.length - 1])}`
})

const chartSubtitle = computed(() =>
  store.granularity() === 'month' ? '按月汇总用电量' : '每日总用电量'
)

const tooltipRows = computed(() => {
  const index = hoverIndex.value
  if (index === null || !chart.value.periods.length) return []
  return chart.value.series.map((series) => ({
    id: series.household_id,
    name: series.display_name,
    color: series.color,
    value: series.values[index],
    y:
      series.values[index] === null
        ? 0
        : chart.value.pad.top +
          chart.value.plotHeight -
          (((series.values[index] as number) - chart.value.yMin) /
            Math.max(0.001, chart.value.yMax - chart.value.yMin)) *
            chart.value.plotHeight
  }))
})

const tooltipAverage = computed(() =>
  hoverIndex.value === null ? null : chart.value.avgValues[hoverIndex.value]
)

const tooltipPeriodLabel = computed(() => {
  if (hoverIndex.value === null || !chart.value.periods.length) return ''
  return formatPeriodCn(chart.value.periods[hoverIndex.value])
})

const tooltipLeft = computed(() => Math.min(86, Math.max(14, hoverPercent.value)))

function onChartMove(event: MouseEvent): void {
  const length = chart.value.periods.length
  if (!length) return
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const xPercent = Math.min(100, Math.max(0, ((event.clientX - rect.left) / rect.width) * 100))
  const plotStart = (chart.value.pad.left / chart.value.width) * 100
  const plotEnd = ((chart.value.width - chart.value.pad.right) / chart.value.width) * 100
  const ratio = Math.min(1, Math.max(0, (xPercent - plotStart) / (plotEnd - plotStart)))
  hoverPercent.value = xPercent
  hoverIndex.value = Math.round(ratio * (length - 1))
}

async function selectFilter(mode: (typeof FILTER_OPTIONS)[number]['id']): Promise<void> {
  filterOpen.value = false
  hoverIndex.value = null
  await store.setFilter(mode)
}

function handleDocumentClick(event: MouseEvent): void {
  if (filterWrap.value && !filterWrap.value.contains(event.target as Node)) {
    filterOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', handleDocumentClick))
</script>

<template>
  <section class="card trend-card" aria-label="用电趋势">
    <header class="card-heading">
      <div>
        <h2>{{ props.title }}</h2>
        <p>
          {{ chartWindowLabel }} · {{ chartSubtitle }}
          <template v-if="props.analysis"> · 最多 5 户同时对比</template>
        </p>
      </div>
      <div class="chart-actions">
        <label class="switch-control">
          <input
            :checked="state.showAverage"
            type="checkbox"
            @change="store.setShowAverage(($event.target as HTMLInputElement).checked)"
          >
          <span class="switch-track"></span>
          <span>全部家庭均值</span>
        </label>
        <div ref="filterWrap" class="filter-wrap">
          <button
            class="filter-button"
            :class="{ open: filterOpen }"
            type="button"
            @click.stop="filterOpen = !filterOpen"
          >
            <AppIcon name="sliders" :size="12" />
            {{ store.filterLabel() }}
            <span class="chevron"><AppIcon name="chevronDown" :size="10" /></span>
          </button>
          <div v-if="filterOpen" class="filter-menu">
            <button
              v-for="option in FILTER_OPTIONS"
              :key="option.id"
              class="filter-option"
              :class="{ active: state.filterMode === option.id }"
              type="button"
              @click.stop="selectFilter(option.id)"
            >
              <span>{{ option.label }}</span>
              <span class="option-check"><AppIcon name="check" :size="10" /></span>
            </button>
          </div>
        </div>
      </div>
    </header>

    <div class="chart-legend">
      <span v-for="series in chart.series" :key="series.household_id" class="legend-item">
        <span class="legend-dot" :style="{ '--legend-color': series.color }"></span>
        {{ series.display_name }}
      </span>
      <span v-if="state.showAverage" class="legend-item">
        <span class="legend-line"></span>
        可访问家庭平均
      </span>
    </div>

    <div
      class="chart-stage"
      @mousemove="onChartMove"
      @mouseleave="hoverIndex = null"
    >
      <svg
        class="chart-svg"
        viewBox="0 0 920 320"
        role="img"
        aria-label="所选家庭用电趋势折线图"
      >
        <defs>
          <linearGradient id="averageArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#6c829f" stop-opacity="0.12" />
            <stop offset="100%" stop-color="#6c829f" stop-opacity="0" />
          </linearGradient>
        </defs>

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

        <text class="axis-unit" :x="chart.pad.left" y="10">{{ chart.axisUnit }}</text>

        <template v-if="state.showAverage">
          <path
            v-for="(area, index) in chart.avgAreas"
            :key="'avg-area-' + index"
            :d="area"
            fill="url(#averageArea)"
          />
          <path
            v-for="(path, index) in chart.avgPaths"
            :key="'avg-path-' + index"
            class="average-line"
            :d="path"
          />
        </template>

        <g
          v-for="(series, seriesIndex) in chart.series"
          :key="'series-' + seriesIndex"
        >
          <path
            v-for="(path, pathIndex) in series.paths"
            :key="'p-' + pathIndex"
            class="series-line"
            :d="path"
            :stroke="series.color"
          />
          <circle
            v-if="series.lastPoint"
            class="series-end-dot"
            :cx="series.lastPoint.x"
            :cy="series.lastPoint.y"
            r="3.2"
            :fill="series.color"
          />
        </g>

        <g v-for="tick in chart.xTicks" :key="'x-' + tick.index">
          <text
            class="axis-label"
            :x="tick.x"
            :y="chart.height - 9"
            text-anchor="middle"
          >{{ tick.label }}</text>
        </g>

        <g v-if="chart.peakPoint" class="peak-marker">
          <line
            :x1="chart.peakPoint.x"
            :x2="chart.peakPoint.x"
            :y1="chart.pad.top"
            :y2="chart.height - chart.pad.bottom"
          />
          <circle :cx="chart.peakPoint.x" :cy="chart.peakPoint.y" r="2.8" />
          <text :x="chart.peakPoint.x + 6" :y="chart.peakPoint.y - 6">峰值</text>
        </g>

        <g v-if="hoverIndex !== null && chart.periods.length">
          <line
            class="hover-line"
            :x1="chart.hoverX"
            :x2="chart.hoverX"
            :y1="chart.pad.top"
            :y2="chart.height - chart.pad.bottom"
          />
          <template v-for="row in tooltipRows" :key="'dot-' + row.id">
            <circle
              v-if="row.value !== null"
              class="hover-dot"
              :cx="chart.hoverX"
              :cy="row.y"
              r="3.5"
              :fill="row.color"
            />
          </template>
        </g>
      </svg>

      <div
        v-if="hoverIndex !== null && tooltipRows.length"
        class="chart-tooltip"
        :style="{ left: tooltipLeft + '%' }"
      >
        <div class="tooltip-date">{{ tooltipPeriodLabel }}</div>
        <div v-for="row in tooltipRows" :key="'tip-' + row.id" class="tooltip-row">
          <span class="tt-dot" :style="{ '--tt-color': row.color }"></span>
          <span>{{ row.name }}</span>
          <strong>{{ row.value === null ? '—' : formatKwh(row.value) }}</strong>
        </div>
        <div v-if="state.showAverage" class="tooltip-row average">
          <span class="tt-dot"></span>
          <span>全部家庭平均</span>
          <strong>{{ tooltipAverage === null ? '—' : formatKwh(tooltipAverage) }}</strong>
        </div>
      </div>

      <div v-if="state.loading" class="chart-loading">
        <span class="spinner" aria-label="正在载入数据"></span>
      </div>
    </div>
  </section>
</template>
