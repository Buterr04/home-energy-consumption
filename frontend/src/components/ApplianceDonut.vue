<script setup lang="ts">
import { computed } from 'vue'
import { useEnergyStore } from '../stores/energy'
import { applianceMix } from '../utils/appliances'
import { formatCompact, formatPeriodCn } from '../utils/format'

const store = useEnergyStore()
const state = store.state
const mix = computed(() => applianceMix(state.breakdown))
const caption = computed(() => {
  if (store.granularity() === 'month') {
    const range = store.rangeParams()
    return `${formatPeriodCn(range.start)} — ${formatPeriodCn(range.end)}`
  }
  if (state.rangeMode === '7d') return '近 7 天'
  return '近 30 天'
})
</script>

<template>
  <section class="card mix-card" aria-label="电器用电构成">
    <div class="compact-card-head">
      <h2>电器构成</h2>
      <span>{{ caption }}</span>
    </div>
    <div class="mix-body">
      <div
        class="donut"
        :style="{ background: mix.gradient }"
        role="img"
        :aria-label="'电器用电构成，共 ' + formatCompact(mix.total) + ' 千瓦时'"
      >
        <div class="donut-center">
          <strong>{{ formatCompact(mix.total) }}</strong>
          <span>kWh</span>
        </div>
      </div>
      <div class="mix-legend">
        <div v-for="item in mix.legend" :key="item.name" class="mix-row">
          <span class="mix-color" :style="{ '--mix-color': item.color }"></span>
          <span class="mix-name">{{ item.name }}</span>
          <span class="mix-percent">{{ item.percent }}%</span>
        </div>
      </div>
    </div>
  </section>
</template>
