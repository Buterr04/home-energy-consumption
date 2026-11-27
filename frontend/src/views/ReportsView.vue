<script setup lang="ts">
import { computed } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import { ENDPOINTS, useEnergyStore } from '../stores/energy'
import { formatKwh, formatPeople, formatPeriodCn } from '../utils/format'

const store = useEnergyStore()
const state = store.state

const periodLabel = computed(() => {
  const range = store.rangeParams()
  if (store.granularity() === 'month') return `${range.start.slice(0, 4)} 年度`
  return `${formatPeriodCn(range.start)} — ${formatPeriodCn(range.end)}`
})

const rows = computed(() => {
  const allAvg = state.households.length
    ? state.households.reduce((sum, home) => sum + (home.avg_daily_kwh || 0), 0) /
      state.households.length
    : 1
  return store
    .selectedHouseholds()
    .slice()
    .sort((a, b) => (b.avg_daily_kwh || 0) - (a.avg_daily_kwh || 0))
    .map((home) => {
      const series = state.seriesData.find((item) => item.household_id === home.household_id)
      const total = series
        ? series.points.reduce((sum, point) => sum + (point.kwh || 0), 0)
        : 0
      const delta = allAvg ? (((home.avg_daily_kwh || 0) - allAvg) / allAvg) * 100 : 0
      return {
        home,
        total,
        deltaLabel: `${delta >= 0 ? '+' : ''}${delta.toFixed(0)}%`
      }
    })
})
</script>

<template>
  <div>
    <section class="reports-layout">
      <section class="card report-main">
        <div class="report-head">
          <div>
            <h2>家庭用电汇总报告</h2>
            <p>按当前所选家庭生成 CSV 月度汇总</p>
          </div>
          <span class="report-period">{{ periodLabel }}</span>
        </div>

        <div class="report-hero">
          <div class="report-doc-icon">
            <AppIcon name="file" :size="27" />
          </div>
          <div class="report-doc-copy">
            <h3>consumption_report.csv</h3>
            <p>
              {{ state.selectedIds.length }} 户家庭 · {{ periodLabel }} ·
              包含 household_id、period、total_kwh、kwh_per_resident
            </p>
            <div class="report-home-chips">
              <span
                v-for="home in store.selectedHouseholds()"
                :key="'report-' + home.household_id"
                class="report-home-chip"
              >
                <i :style="{ '--home-color': store.colorForHousehold(home.household_id) }"></i>
                {{ home.display_name }}
              </span>
            </div>
          </div>
        </div>

        <div class="table-scroll">
          <table class="report-table">
            <thead>
              <tr>
                <th>家庭</th>
                <th>人口中位数</th>
                <th>区间用电</th>
                <th>人均用电</th>
                <th>与均值</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="'report-row-' + row.home.household_id">
                <td>{{ row.home.display_name }}</td>
                <td>{{ formatPeople(row.home.size_median) }}</td>
                <td>{{ formatKwh(row.total) }} kWh</td>
                <td>
                  {{ formatKwh(row.total / Math.max(row.home.size_median || 1, 1)) }} kWh
                </td>
                <td>{{ row.deltaLabel }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="export-row">
          <span class="export-note">
            导出接口：GET /api/v1/reports/summary · format=csv<br>
            将从当前 FastAPI 会话直接下载真实汇总数据。
          </span>
          <button class="export-button" type="button" @click="store.exportReport()">
            <AppIcon name="download" :size="13" />
            导出 CSV
          </button>
        </div>
      </section>

      <aside class="reports-side">
        <section class="source-card">
          <div class="source-head">
            <span class="source-title">
              <AppIcon name="server" :size="14" />
              数据源
            </span>
            <span class="source-state" :class="{ live: state.connected }">
              API 已连接
            </span>
          </div>
          <p>
            当前页面使用登录 JWT 请求 FastAPI，图表、预测与报告均来自真实接口。
          </p>
          <div class="source-endpoint">{{ state.apiBase }}</div>
          <button
            class="source-button"
            type="button"
            :disabled="state.loading"
            @click="store.refreshData()"
          >
            {{ state.loading ? '正在同步…' : '刷新后端数据' }}
          </button>
        </section>

        <section class="source-card">
          <div class="source-head">
            <span class="source-title">
              <AppIcon name="link" :size="14" />
              已接入接口
            </span>
          </div>
          <div class="endpoint-list">
            <div v-for="endpoint in ENDPOINTS" :key="endpoint.path" class="endpoint-row">
              <span :class="['method', { post: endpoint.method === 'POST' }]">
                {{ endpoint.method }}
              </span>
              <span>{{ endpoint.path }}</span>
            </div>
          </div>
        </section>

        <section class="card recent-card">
          <h2>最近导出</h2>
          <div v-for="item in state.recentReports" :key="item.name" class="recent-row">
            <span class="recent-icon"><AppIcon name="file" :size="12" /></span>
            <span class="recent-copy">
              <strong>{{ item.name }}</strong>
              <span>{{ item.time }}</span>
            </span>
            <span class="recent-size">{{ item.size }}</span>
          </div>
        </section>
      </aside>
    </section>
  </div>
</template>
