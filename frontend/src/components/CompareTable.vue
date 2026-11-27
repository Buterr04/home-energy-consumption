<script setup lang="ts">
import { computed } from 'vue'
import { useEnergyStore } from '../stores/energy'
import { formatKwh, formatPeople, formatTemp } from '../utils/format'

const props = withDefaults(
  defineProps<{
    variant?: 'overview' | 'analysis'
  }>(),
  { variant: 'overview' }
)

const store = useEnergyStore()
const state = store.state

const rows = computed(() => {
  const homes = store.selectedHouseholds()
  const allAvg = state.households.length
    ? state.households.reduce((sum, home) => sum + (home.avg_daily_kwh || 0), 0) /
      state.households.length
    : 1
  const maxAvg = Math.max(...homes.map((home) => home.avg_daily_kwh || 0), 0.001)
  return homes
    .slice()
    .sort((a, b) => (b.avg_daily_kwh || 0) - (a.avg_daily_kwh || 0))
    .map((home) => {
      const avg = home.avg_daily_kwh || 0
      const series = state.seriesData.find((item) => item.household_id === home.household_id)
      const total = series
        ? series.points.reduce((sum, point) => sum + (point.kwh || 0), 0)
        : 0
      const delta = allAvg ? ((avg - allAvg) / allAvg) * 100 : 0
      return {
        home,
        color: store.colorForHousehold(home.household_id),
        avg,
        total,
        barWidth: Math.max(6, (avg / maxAvg) * 100),
        delta,
        deltaLabel: `${delta >= 0 ? '+' : ''}${delta.toFixed(0)}%`
      }
    })
})

const subtitle = computed(() => {
  const homes = store.selectedHouseholds()
  if (!homes.length) return '尚未选择家庭'
  const temperatures = homes
    .map((home) => home.avg_temp_c)
    .filter((value): value is number => value != null)
  const span = temperatures.length ? Math.max(...temperatures) - Math.min(...temperatures) : 0
  return `${state.selectedIds.length} 户家庭 · 最大平均温差 ${span.toFixed(1)}°C`
})
</script>

<template>
  <section
    class="card compare-card"
    :class="{ 'analysis-compare': props.variant === 'analysis' }"
    aria-label="家庭对比"
  >
    <div class="compare-header">
      <div>
        <h2>{{ props.variant === 'analysis' ? '家庭明细' : '家庭对比' }}</h2>
        <p>{{ props.variant === 'analysis' ? '按日均用电量降序排列，最多对比 5 户' : subtitle }}</p>
      </div>
      <span class="micro-label">
        {{ props.variant === 'analysis' ? `${state.selectedIds.length} SELECTED` : 'UP TO 5 HOMES' }}
      </span>
    </div>
    <div class="table-scroll">
      <table class="compare-table">
        <thead>
          <tr>
            <th>家庭</th>
            <th>人数</th>
            <th>日均用电</th>
            <th>均温</th>
            <th>对比均值</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.home.household_id">
            <td>
              <span class="table-home">
                <span class="table-home-dot" :style="{ '--home-color': row.color }"></span>
                <span class="table-home-name">{{ row.home.display_name }}</span>
              </span>
            </td>
            <td>{{ formatPeople(row.home.size_median) }}</td>
            <td>
              <span class="table-bar" :style="{ '--home-color': row.color }">
                <span :style="{ width: row.barWidth + '%' }"></span>
              </span>
              {{ formatKwh(row.avg) }}
            </td>
            <td>{{ formatTemp(row.home.avg_temp_c) }}</td>
            <td>
              <span
                class="tiny-trend"
                :class="{ low: row.delta < 0, high: row.delta > 8 }"
              >{{ row.deltaLabel }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
