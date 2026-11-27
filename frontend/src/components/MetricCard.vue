<script setup lang="ts">
import AppIcon from './AppIcon.vue'

export interface DashboardMetric {
  label: string
  value: string
  unit: string
  icon: string
  color: string
  soft: string
  trend: string
  tone: string
  note: string
}

defineProps<{
  metric: DashboardMetric
  sparkline: string
}>()
</script>

<template>
  <article
    class="metric-card"
    :style="{
      '--metric-color': metric.color,
      '--metric-soft': metric.soft
    }"
  >
    <div class="metric-top">
      <span class="metric-label">{{ metric.label }}</span>
      <span class="metric-icon"><AppIcon :name="metric.icon" :size="13" /></span>
    </div>
    <div class="metric-value">
      {{ metric.value }}<small>{{ metric.unit }}</small>
    </div>
    <div class="metric-bottom">
      <span class="trend-pill" :class="metric.tone">{{ metric.trend }}</span>
      <span class="metric-note">{{ metric.note }}</span>
    </div>
    <svg class="metric-spark" viewBox="0 0 100 30" aria-hidden="true">
      <path
        :d="sparkline"
        fill="none"
        :stroke="metric.color"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  </article>
</template>
