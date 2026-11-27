<script setup lang="ts">
import { computed } from 'vue'
import { useEnergyStore } from '../stores/energy'
import { applianceMix } from '../utils/appliances'
import { buildChart } from '../utils/chart'
import { formatKwh, formatPeriodCn } from '../utils/format'
import AppIcon from './AppIcon.vue'

const store = useEnergyStore()
const state = store.state

const insights = computed(() => {
  const mix = applianceMix(state.breakdown).items
  const top = mix.slice(0, 2)
  const chart = buildChart(
    state.seriesData,
    state.averageData,
    store.granularity(),
    null,
    0
  )
  const allAvg = state.households.length
    ? state.households.reduce((sum, home) => sum + (home.avg_daily_kwh || 0), 0) /
      state.households.length
    : 1
  const highest = store
    .selectedHouseholds()
    .slice()
    .sort((a, b) => (b.avg_daily_kwh || 0) - (a.avg_daily_kwh || 0))[0]
  const highestDelta = highest && allAvg
    ? (((highest.avg_daily_kwh || 0) - allAvg) / allAvg) * 100
    : 0
  const totalText = top.length
    ? `${top[0].name}与${top[1] ? top[1].name : '其他电器'}贡献 ${(top[0].percent + (top[1]?.percent || 0)).toFixed(0)}%`
    : '电器占比正在计算'

  return [
    {
      title: totalText,
      detail: '优先检查高占比电器的使用时段，可更快降低日均用电。',
      icon: 'bolt',
      color: '#0a84ff'
    },
    {
      title: highest ? `${highest.display_name} 是当前用电最高家庭` : '等待家庭数据',
      detail: highest
        ? `日均 ${formatKwh(highest.avg_daily_kwh)} kWh，较全部家庭均值 ${highestDelta >= 0 ? '+' : ''}${highestDelta.toFixed(0)}%。`
        : '选择家庭后显示对比洞察。',
      icon: 'home',
      color: '#ff9f0a'
    },
    {
      title: chart.peakPoint ? `${formatPeriodCn(chart.peakPoint.period)} 出现区间峰值` : '暂无峰值记录',
      detail: chart.peakPoint
        ? `峰值 ${formatKwh(chart.peakPoint.value)} kWh，建议避开同时开启大功率电器。`
        : '缺失周期会以空档展示。',
      icon: 'activity',
      color: '#8b5cf6'
    }
  ]
})
</script>

<template>
  <section class="card insight-card" aria-label="智能洞察">
    <div class="insight-head">
      <div>
        <h2>智能洞察</h2>
        <p>从当前家庭数据中自动发现</p>
      </div>
      <span class="spark-badge"><AppIcon name="sparkles" :size="14" /></span>
    </div>
    <div class="insight-list">
      <div
        v-for="insight in insights"
        :key="insight.title"
        class="insight-item"
        :style="{ '--insight-color': insight.color }"
      >
        <span class="insight-icon"><AppIcon :name="insight.icon" :size="12" /></span>
        <span>
          <strong>{{ insight.title }}</strong>
          <span>{{ insight.detail }}</span>
        </span>
      </div>
    </div>
  </section>
</template>
