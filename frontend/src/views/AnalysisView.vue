<script setup lang="ts">
import { computed } from 'vue'
import CompareTable from '../components/CompareTable.vue'
import TrendChart from '../components/TrendChart.vue'
import { useEnergyStore } from '../stores/energy'
import { applianceMix } from '../utils/appliances'
import { formatKwh, formatNumber, formatPeriodCn } from '../utils/format'

const store = useEnergyStore()
const state = store.state
const mix = computed(() => applianceMix(state.breakdown))
const totalReadings = computed(() =>
  store.selectedHouseholds().reduce((sum, home) => sum + (home.reading_count || 0), 0)
)
const periodCoverage = computed(() => {
  const points = state.seriesData.flatMap((series) => series.points)
  const valid = points.filter((point) => point.kwh !== null).length
  return {
    total: points.length,
    valid,
    missing: points.length - valid,
    percent: points.length ? (valid / points.length) * 100 : 0
  }
})
const averagePeople = computed(() => {
  const sizes = store
    .selectedHouseholds()
    .map((home) => home.size_median)
    .filter((value): value is number => value != null)
  if (!sizes.length) return 0
  return sizes.reduce((sum, value) => sum + value, 0) / sizes.length
})
const mixCaption = computed(() => {
  if (store.granularity() === 'month') {
    const range = store.rangeParams()
    return `${formatPeriodCn(range.start)} — ${formatPeriodCn(range.end)}`
  }
  return state.rangeMode === '7d' ? '近 7 天' : '近 30 天'
})
</script>

<template>
  <div>
    <section class="analysis-strip">
      <div class="strip-stats">
        <span class="strip-stat"><span>已选择</span><strong>{{ state.selectedIds.length }} 户</strong></span>
        <span class="strip-stat"><span>累计读数</span><strong>{{ formatNumber(totalReadings) }}</strong></span>
        <span class="strip-stat"><span>数据覆盖</span><strong>{{ periodCoverage.percent.toFixed(1) }}%</strong></span>
      </div>
      <div class="selected-home-chips">
        <span
          v-for="home in store.selectedHouseholds()"
          :key="home.household_id"
          class="selected-home-chip"
        >
          <i :style="{ '--home-color': store.colorForHousehold(home.household_id) }"></i>
          {{ home.display_name }}
        </span>
      </div>
    </section>

    <div class="main-grid analysis-mode">
      <TrendChart title="多家庭聚合趋势" analysis />
    </div>

    <div class="analysis-lower">
      <section class="card breakdown-detail">
        <div class="breakdown-head">
          <div>
            <h2>电器用电明细</h2>
            <p>{{ mixCaption }} · 共 {{ formatKwh(mix.total) }} kWh</p>
          </div>
          <span class="micro-label">BREAKDOWN</span>
        </div>
        <div class="breakdown-list">
          <div
            v-for="item in mix.items"
            :key="item.appliance_id"
            class="breakdown-item"
            :style="{ '--breakdown-color': item.color }"
          >
            <div class="breakdown-line">
              <span><i></i>{{ item.name }}</span>
              <strong>{{ item.percent.toFixed(1) }}%</strong>
            </div>
            <div class="breakdown-track">
              <div
                class="breakdown-fill"
                :style="{ width: Math.max(item.percent, 2) + '%' }"
              ></div>
            </div>
          </div>
        </div>
      </section>

      <section class="card quality-card">
        <div class="quality-head">
          <h2>数据覆盖</h2>
          <p>当前请求区间内实际返回的周期</p>
        </div>
        <div class="quality-body">
          <div
            class="quality-ring"
            :style="{ '--quality': periodCoverage.percent }"
          >
            <div class="quality-ring-copy">
              <strong>{{ periodCoverage.percent.toFixed(1) }}%</strong>
              <span>COVERED</span>
            </div>
          </div>
          <div class="quality-rows">
            <div class="quality-row"><span>有效周期</span><strong>{{ formatNumber(periodCoverage.valid) }}</strong></div>
            <div class="quality-row"><span>缺失周期</span><strong>{{ formatNumber(periodCoverage.missing) }}</strong></div>
            <div class="quality-row"><span>覆盖家庭</span><strong>{{ state.selectedIds.length }} 户</strong></div>
            <div class="quality-row"><span>平均人口</span><strong>{{ averagePeople.toFixed(1) }} 人</strong></div>
          </div>
        </div>
      </section>
    </div>

    <CompareTable variant="analysis" />
  </div>
</template>
