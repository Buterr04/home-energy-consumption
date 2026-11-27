<script setup lang="ts">
import { computed } from 'vue'
import ApplianceDonut from '../components/ApplianceDonut.vue'
import AppIcon from '../components/AppIcon.vue'
import CompareTable from '../components/CompareTable.vue'
import InsightList from '../components/InsightList.vue'
import MetricCard, { type DashboardMetric } from '../components/MetricCard.vue'
import TrendChart from '../components/TrendChart.vue'
import { useEnergyStore } from '../stores/energy'
import { buildChart } from '../utils/chart'
import { formatPeriodCn } from '../utils/format'

const store = useEnergyStore()
const state = store.state

const chart = computed(() =>
  buildChart(state.seriesData, state.averageData, store.granularity(), null, 0)
)

const metrics = computed<DashboardMetric[]>(() => {
  const homes = store.selectedHouseholds()
  const avgDaily = homes.length
    ? homes.reduce((sum, home) => sum + (home.avg_daily_kwh || 0), 0) / homes.length
    : 0
  const combined = chart.value.avgValues.filter((value): value is number => value !== null)
  const peakValue = combined.length ? Math.max(...combined) : 0
  const temperature = homes.length
    ? homes.reduce((sum, home) => sum + (home.avg_temp_c || 0), 0) / homes.length
    : 0
  const splitIndex = Math.max(1, Math.floor(combined.length / 2))
  const firstHalf = combined.slice(0, splitIndex)
  const secondHalf = combined.slice(splitIndex)
  const firstAvg = firstHalf.length
    ? firstHalf.reduce((sum, value) => sum + value, 0) / firstHalf.length
    : 0
  const secondAvg = secondHalf.length
    ? secondHalf.reduce((sum, value) => sum + value, 0) / secondHalf.length
    : 0
  const delta = firstAvg ? ((secondAvg - firstAvg) / firstAvg) * 100 : 0
  const monthly = store.granularity() === 'month'
  const allPoints = state.seriesData.flatMap((series) => series.points)
  const validPoints = allPoints.filter((point) => point.kwh !== null).length
  const coverage = allPoints.length ? (validPoints / allPoints.length) * 100 : 0

  return [
    {
      label: '所选家庭日均',
      value: avgDaily.toFixed(2),
      unit: 'kWh',
      icon: 'bolt',
      color: '#0a84ff',
      soft: '#eaf4ff',
      trend: `${delta <= 0 ? '↓ ' : '↑ '}${Math.abs(delta).toFixed(1)}%`,
      tone: delta <= 0 ? 'good' : 'warn',
      note: '家庭画像均值'
    },
    {
      label: monthly ? '峰值月份' : '区间峰值',
      value: peakValue.toFixed(monthly ? 0 : 2),
      unit: 'kWh',
      icon: 'activity',
      color: '#ff9f0a',
      soft: '#fff5e6',
      trend: monthly ? '月度汇总' : '日均峰值',
      tone: '',
      note: chart.value.peakPoint ? formatPeriodCn(chart.value.peakPoint.period) : '暂无数据'
    },
    {
      label: '平均室外温度',
      value: temperature.toFixed(1),
      unit: '°C',
      icon: 'thermometer',
      color: '#30a46c',
      soft: '#ebf9f1',
      trend: state.rangeMode === '12m' ? '年度区间' : state.rangeMode === '7d' ? '近 7 天' : '近 30 天',
      tone: '',
      note: '来自所选家庭画像'
    },
    {
      label: '数据覆盖',
      value: coverage.toFixed(1),
      unit: '%',
      icon: 'shield',
      color: '#8b5cf6',
      soft: '#f3efff',
      trend: `${validPoints}/${allPoints.length}`,
      tone: coverage >= 95 ? 'good' : coverage >= 80 ? '' : 'warn',
      note: '有效周期 / 应返回周期'
    }
  ]
})

const sparklinePath = computed(() => {
  const values = chart.value.avgValues
    .map((value, index) => ({ value, index }))
    .filter((point): point is { value: number; index: number } => point.value !== null)
  if (values.length < 2) return ''
  const min = Math.min(...values.map((point) => point.value))
  const max = Math.max(...values.map((point) => point.value))
  const range = Math.max(max - min, 0.001)
  return values
    .map((point, index) => {
      const x = 2 + (96 * index) / (values.length - 1)
      const y = 27 - ((point.value - min) / range) * 23
      return `${index ? 'L' : 'M'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
})

const averageAccessible = computed(() => {
  const values = state.households
    .map((home) => home.avg_daily_kwh)
    .filter((value): value is number => value != null)
  if (!values.length) return 0
  return values.reduce((sum, value) => sum + value, 0) / values.length
})
const averageSelected = computed(() => {
  const values = store
    .selectedHouseholds()
    .map((home) => home.avg_daily_kwh)
    .filter((value): value is number => value != null)
  if (!values.length) return 0
  return values.reduce((sum, value) => sum + value, 0) / values.length
})
const relativeUsage = computed(() =>
  averageAccessible.value
    ? (averageSelected.value / averageAccessible.value) * 100
    : 0
)
const relativeDelta = computed(() => relativeUsage.value - 100)
const scoreValue = computed(() => Math.min(100, Math.max(0, relativeUsage.value)))
const relativeTitle = computed(() => {
  if (!averageAccessible.value) return '等待后端数据'
  if (relativeUsage.value < 95) return '低于可访问家庭平均'
  if (relativeUsage.value > 105) return '高于可访问家庭平均'
  return '接近可访问家庭平均'
})
const scoreDash = 2 * Math.PI * 35
const scoreOffset = computed(() => scoreDash * (1 - scoreValue.value / 100))
const validPeriodCount = computed(
  () =>
    state.seriesData
      .flatMap((series) => series.points)
      .filter((point) => point.kwh !== null).length
)
</script>

<template>
  <div>
    <section class="metrics-grid" aria-label="关键指标">
      <MetricCard
        v-for="metric in metrics"
        :key="metric.label"
        :metric="metric"
        :sparkline="sparklinePath"
      />
    </section>

    <div class="main-grid">
      <TrendChart />

      <aside class="rail">
        <section class="score-card" aria-label="相对用能水平">
          <div class="score-head">
            <span class="score-label">
              <AppIcon name="leaf" :size="13" />
              相对用能
            </span>
            <span class="score-pill">当前区间</span>
          </div>
          <div class="score-body">
            <div class="score-ring">
              <svg viewBox="0 0 88 88" aria-hidden="true">
                <circle class="score-ring-track" cx="44" cy="44" r="35" />
                <circle
                  class="score-ring-value"
                  cx="44"
                  cy="44"
                  r="35"
                  :stroke-dasharray="scoreDash"
                  :stroke-dashoffset="scoreOffset"
                />
              </svg>
              <div class="score-ring-copy">
                <strong>{{ relativeUsage ? relativeUsage.toFixed(0) : '—' }}</strong>
                <span>% AVG</span>
              </div>
            </div>
            <div class="score-copy">
              <h3>{{ relativeTitle }}</h3>
              <p>
                所选日均 {{ averageSelected.toFixed(2) }} kWh ·
                可访问均值 {{ averageAccessible.toFixed(2) }} kWh
              </p>
              <span class="score-chip">
                <AppIcon name="arrowUp" :size="9" />
                {{ relativeDelta >= 0 ? '+' : '' }}{{ relativeDelta.toFixed(1) }}%
              </span>
            </div>
          </div>
          <div class="score-foot">
            <span>
              区间峰值
              <strong>
                {{ chart.peakPoint ? formatPeriodCn(chart.peakPoint.period) : '—' }}
              </strong>
            </span>
            <span>有效周期 <strong>{{ validPeriodCount }}</strong></span>
          </div>
        </section>

        <ApplianceDonut />
      </aside>
    </div>

    <div class="bottom-grid">
      <CompareTable />
      <InsightList />
    </div>
  </div>
</template>
