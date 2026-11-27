<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import AppIcon from './components/AppIcon.vue'
import AppSidebar from './components/AppSidebar.vue'
import LoginScreen from './components/LoginScreen.vue'
import { RANGE_OPTIONS, useEnergyStore } from './stores/energy'
import { formatPeriodCn } from './utils/format'

const store = useEnergyStore()
const state = store.state
const route = useRoute()
const router = useRouter()

const currentLabel = computed(() => String(route.meta.label || '能源总览'))
const showRangeControls = computed(
  () => route.path === '/overview' || route.path === '/analysis'
)
const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
})
const userName = computed(
  () => state.user?.display_name || state.user?.username || '当前用户'
)
const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    '/overview': `${greeting.value}，今天用能如何？`,
    '/analysis': '把每一度电看得更清楚',
    '/predict': '按温度、人口和月份预估用电',
    '/reports': '把洞察整理成可分享的汇总',
    '/admin': '管理系统用户、家庭归属与数据导入'
  }
  return titles[route.path] || '家庭能源分析'
})
const headerSubtitle = computed(() => {
  if (route.path === '/overview') {
    return `${userName.value}，正在查看 ${state.selectedIds.length} 户家庭。数据截至 ${store.activeEndDate()}，缺失周期会保留为空档。`
  }
  if (route.path === '/analysis') {
    return '按日或按月聚合，最多同时对比 5 户家庭，并可按电器类型排除读数。'
  }
  if (route.path === '/predict') {
    return `使用离线预训练的 ${state.modelInfo.version || 'linear-v1'} 模型，只做推理，不在线训练。`
  }
  if (route.path === '/admin') {
    return '管理员可管理全部家庭、创建或停用用户、调整家庭归属并上传 CSV 数据。'
  }
  return '选择家庭后可导出月度或年度 CSV，普通用户只会看到自己有权访问的数据。'
})
const rangeHint = computed(() => formatPeriodCn(store.activeEndDate()))
const isAdmin = computed(() => state.user?.role === 'admin')

function goPredict(): void {
  void router.push('/predict')
}
</script>

<template>
  <div class="ipad-stage">
    <div class="ambient-orb orb-a"></div>
    <div class="ambient-orb orb-b"></div>
    <div class="ambient-orb orb-c"></div>

    <LoginScreen v-if="!state.connected" />

    <section
      v-else
      class="ipad-shell"
      aria-label="WattHome 家庭能源分析"
    >
      <AppSidebar />

      <section class="content">
        <header class="content-header">
          <div class="header-copy">
            <div class="breadcrumb">
              <span>WattHome</span>
              <span>/</span>
              <b>{{ currentLabel }}</b>
            </div>
            <h1 class="header-title">{{ pageTitle }}</h1>
            <p class="header-subtitle">{{ headerSubtitle }}</p>
          </div>

          <div class="header-actions">
            <span class="data-chip">
              <span
                class="status-dot"
                :class="{ live: state.loading }"
              ></span>
              <span>{{ state.loading ? '正在同步数据' : 'FastAPI 已连接' }}</span>
            </span>
            <span v-if="isAdmin" class="role-chip">ADMIN</span>
            <div v-if="state.connected && showRangeControls" class="segmented" aria-label="时间范围">
              <button
                v-for="option in RANGE_OPTIONS"
                :key="option.id"
                class="segment-button"
                :class="{ active: state.rangeMode === option.id }"
                type="button"
                :title="rangeHint"
                @click="store.setRange(option.id)"
              >
                {{ option.label }}
              </button>
            </div>
            <button
              v-if="route.path === '/reports' || route.path === '/admin'"
              class="ghost-button"
              type="button"
              :disabled="state.loading"
              @click="store.refreshData()"
            >
              <AppIcon name="refresh" :size="13" />
              刷新数据
            </button>
            <button
              v-if="route.path !== '/predict' && route.path !== '/admin'"
              class="primary-button"
              type="button"
              @click="goPredict"
            >
              <AppIcon name="sparkles" :size="14" />
              智能预测
            </button>
            <button
              v-else-if="route.path === '/predict'"
              class="primary-button"
              type="button"
              @click="router.push('/overview')"
            >
              <AppIcon name="layout" :size="14" />
              返回总览
            </button>
          </div>
        </header>

        <div class="content-scroll">
          <RouterView v-slot="{ Component }">
            <Transition name="page-fade" mode="out-in">
              <component :is="Component" :key="route.path" />
            </Transition>
          </RouterView>
        </div>
      </section>
    </section>

    <Transition name="page-fade">
      <div
        v-if="state.toast.visible"
        class="toast"
        :class="state.toast.tone"
        aria-live="polite"
      >
        <AppIcon
          :name="state.toast.tone === 'warn' ? 'info' : 'checkCircle'"
          :size="13"
        />
        <span>{{ state.toast.message }}</span>
      </div>
    </Transition>
  </div>
</template>
