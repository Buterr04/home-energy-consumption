<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEnergyStore } from '../stores/energy'
import { formatKwh, formatPeople, formatTemp } from '../utils/format'
import AppIcon from './AppIcon.vue'

const store = useEnergyStore()
const state = store.state
const route = useRoute()
const router = useRouter()
const profileOpen = ref(false)
const homeSearch = ref('')

const baseNavItems = [
  { id: 'overview', label: '能源总览', icon: 'layout', path: '/overview' },
  { id: 'analysis', label: '用电分析', icon: 'chart', path: '/analysis' },
  { id: 'predict', label: '智能预测', icon: 'sparkles', path: '/predict', badge: 'AI' },
  { id: 'reports', label: '报告中心', icon: 'file', path: '/reports' }
]

const userName = computed(
  () => state.user?.display_name || state.user?.username || '未登录'
)
const userInitial = computed(() =>
  state.user ? userName.value.slice(0, 1).toUpperCase() : '·'
)
const userRoleLabel = computed(() =>
  state.user ? (state.user.role === 'admin' ? '管理员' : '普通用户') : '未登录'
)
const isAdmin = computed(() => state.user?.role === 'admin')
const navItems = computed(() =>
  isAdmin.value
    ? [
        ...baseNavItems,
        {
          id: 'admin',
          label: '管理控制台',
          icon: 'shield',
          path: '/admin',
          badge: 'ADMIN'
        }
      ]
    : baseNavItems
)
const householdSectionLabel = computed(() => (isAdmin.value ? '全部家庭' : '我的家庭'))
const selectionPercent = computed(() => Math.min(100, (state.selectedIds.length / 5) * 100))
const visibleHouseholds = computed(() => {
  const query = homeSearch.value.trim().toLowerCase()
  const matching = state.households.filter((home) => {
    if (!query) return true
    return (
      home.display_name.toLowerCase().includes(query) ||
      String(home.household_id).includes(query)
    )
  })
  const selected = matching.filter((home) => state.selectedIds.includes(home.household_id))
  const unselected = matching.filter(
    (home) => !state.selectedIds.includes(home.household_id)
  )
  const limit = isAdmin.value ? 24 : 64
  return [...selected, ...unselected].slice(0, limit)
})
const hiddenHouseholdCount = computed(() => {
  const query = homeSearch.value.trim().toLowerCase()
  const matched = state.households.filter((home) => {
    if (!query) return true
    return (
      home.display_name.toLowerCase().includes(query) ||
      String(home.household_id).includes(query)
    )
  })
  return Math.max(0, matched.length - visibleHouseholds.value.length)
})
const connectionLabel = computed(() => {
  if (state.authStatus === 'connecting') return '正在连接后端…'
  if (state.connected) return isAdmin.value ? 'FastAPI · 管理员会话' : 'FastAPI 已连接'
  if (state.authStatus === 'offline') return '后端连接失败'
  return '需要登录后端'
})

function navigate(path: string): void {
  profileOpen.value = false
  void router.push(path)
}

function handleDocumentClick(event: MouseEvent): void {
  if (!(event.target as Element | null)?.closest('.profile-wrap')) {
    profileOpen.value = false
  }
}

function handleEscape(event: KeyboardEvent): void {
  if (event.key === 'Escape') profileOpen.value = false
}

watch(
  () => route.path,
  () => {
    profileOpen.value = false
  }
)

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
  window.addEventListener('keydown', handleEscape)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
  window.removeEventListener('keydown', handleEscape)
})
</script>

<template>
  <aside class="sidebar" aria-label="应用侧边栏">
    <div class="workspace">
      <div class="app-mark"><AppIcon name="bolt" :size="17" /></div>
      <div class="workspace-copy">
        <p class="workspace-name">WattHome</p>
        <span class="workspace-sub">家庭能源分析</span>
      </div>
    </div>

    <div class="sidebar-scroll">
      <p class="section-label">工作区</p>
      <nav class="nav-list">
        <button
          v-for="item in navItems"
          :key="item.id"
          class="nav-item"
          :class="{ active: route.path === item.path }"
          type="button"
          :aria-label="item.label"
          :title="item.label"
          @click="navigate(item.path)"
        >
          <AppIcon :name="item.icon" :size="15" />
          <span>{{ item.label }}</span>
          <span v-if="item.badge" class="nav-suffix">{{ item.badge }}</span>
        </button>
      </nav>

      <p class="section-label">
        <span class="section-label-copy">
          {{ householdSectionLabel }}
          <em v-if="isAdmin" class="section-role">ADMIN</em>
        </span>
        <span class="count-badge">{{ state.selectedIds.length }}/5</span>
      </p>
      <label v-if="state.households.length > 8" class="home-search">
        <AppIcon name="search" :size="11" />
        <input
          v-model.trim="homeSearch"
          type="search"
          :placeholder="isAdmin ? `搜索 ${state.households.length} 户家庭` : '搜索家庭'"
          aria-label="搜索家庭"
        >
        <button
          v-if="homeSearch"
          type="button"
          aria-label="清除搜索"
          @click="homeSearch = ''"
        >
          <AppIcon name="close" :size="10" />
        </button>
      </label>
      <div v-if="state.households.length" class="home-list">
        <button
          v-for="home in visibleHouseholds"
          :key="home.household_id"
          class="home-row"
          :class="{ selected: state.selectedIds.includes(home.household_id) }"
          type="button"
          :aria-label="`${home.display_name}，${formatPeople(home.size_median)}，日均 ${formatKwh(home.avg_daily_kwh)} kWh`"
          :aria-pressed="state.selectedIds.includes(home.household_id)"
          @click="store.toggleHousehold(home.household_id)"
        >
          <span
            class="home-dot"
            :style="{ '--home-color': store.colorForHousehold(home.household_id) }"
          ></span>
          <span class="home-copy">
            <span class="home-name">{{ home.display_name }}</span>
            <span class="home-meta">
              {{ formatPeople(home.size_median) }} · {{ formatTemp(home.avg_temp_c) }}
            </span>
          </span>
          <span class="home-check" aria-hidden="true">
            <AppIcon name="check" :size="10" />
          </span>
        </button>
        <p v-if="!visibleHouseholds.length" class="home-list-empty">
          没有匹配的家庭
        </p>
        <p v-else-if="hiddenHouseholdCount" class="home-list-note">
          还有 {{ hiddenHouseholdCount }} 户未显示，使用搜索快速定位
        </p>
      </div>

      <div v-if="state.households.length" class="selection-meter">
        <div class="selection-meter-head">
          <span>对比选择</span>
          <strong>{{ state.selectedIds.length }} / 5</strong>
        </div>
        <div class="meter-track">
          <div class="meter-fill" :style="{ width: selectionPercent + '%' }"></div>
        </div>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="connection-mini">
        <AppIcon :name="state.connected ? 'shield' : 'info'" :size="11" />
        <span>{{ connectionLabel }}</span>
      </div>
      <div class="profile-wrap">
        <button
          class="profile-button"
          :class="{ open: profileOpen }"
          type="button"
          :aria-label="'账户：' + userName"
          @click.stop="profileOpen = !profileOpen"
        >
          <span class="avatar">{{ userInitial }}</span>
          <span class="profile-copy">
            <span class="profile-name">{{ userName }}</span>
            <span class="profile-role">
              {{ userRoleLabel }}<template v-if="state.connected"> · {{ state.households.length }} 户</template>
            </span>
          </span>
          <span class="profile-chevron"><AppIcon name="chevronDown" :size="12" /></span>
        </button>

        <div v-if="profileOpen" class="profile-popover">
          <div class="popover-head">
            <strong>{{ userName }}</strong>
            <span v-if="state.user">
              @{{ state.user.username }} · {{ userRoleLabel }} · API 会话
            </span>
            <span v-else>后端会话未建立</span>
          </div>
          <button
            v-if="state.connected"
            class="popover-action"
            type="button"
            @click="profileOpen = false; store.refreshData()"
          >
            <AppIcon name="refresh" :size="13" />
            刷新后端数据
          </button>
          <button
            v-if="state.connected"
            class="popover-action"
            type="button"
            @click="profileOpen = false; store.disconnectApi()"
          >
            <AppIcon name="arrowRight" :size="13" />
            退出登录
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>
