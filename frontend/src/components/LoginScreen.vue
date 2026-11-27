<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useEnergyStore } from '../stores/energy'
import AppIcon from './AppIcon.vue'

const store = useEnergyStore()
const state = store.state
const usernameInput = ref<HTMLInputElement | null>(null)
const passwordVisible = ref(false)
const showAdvanced = ref(false)
const form = reactive({
  base: state.apiBase,
  username: '',
  password: ''
})

async function submit(): Promise<void> {
  if (state.apiBusy || state.authStatus === 'connecting') return
  await store.connectApi(form.base, form.username, form.password)
}

onMounted(() => {
  if (window.matchMedia('(min-width: 961px)').matches) {
    usernameInput.value?.focus()
  }
})
</script>

<template>
  <main class="login-page">
    <section class="login-brand-panel">
      <div class="login-brand-head">
        <div class="login-logo">
          <AppIcon name="bolt" :size="27" />
        </div>
        <div>
          <strong>WattHome</strong>
          <span>Household Energy Intelligence</span>
        </div>
      </div>

      <div class="login-brand-copy">
        <span class="login-kicker">ENERGY · INSIGHT · FORECAST</span>
        <h1>把家庭用电，<br>看得更清楚。</h1>
        <p>连接 FastAPI 后端后，实时查看家庭趋势、电器构成、智能预测与可导出报告。</p>
      </div>

      <div class="login-visual" aria-hidden="true">
        <div class="login-visual-head">
          <span>家庭负荷</span>
          <span class="login-live"><i></i>LIVE</span>
        </div>
        <svg viewBox="0 0 430 140">
          <defs>
            <linearGradient id="loginArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#4aa8ff" stop-opacity="0.44" />
              <stop offset="100%" stop-color="#4aa8ff" stop-opacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M0 105 C38 93 52 54 88 64 C126 75 139 110 176 88 C210 68 225 28 262 45 C301 63 310 105 347 79 C376 59 395 48 430 34 L430 140 L0 140 Z"
            fill="url(#loginArea)"
          />
          <path
            d="M0 105 C38 93 52 54 88 64 C126 75 139 110 176 88 C210 68 225 28 262 45 C301 63 310 105 347 79 C376 59 395 48 430 34"
            fill="none"
            stroke="#90c9ff"
            stroke-width="2.2"
            stroke-linecap="round"
          />
          <circle cx="262" cy="45" r="4" fill="#fff" stroke="#59adff" stroke-width="2" />
        </svg>
        <div class="login-visual-stats">
          <div><span>趋势分析</span><strong>Real-time</strong></div>
          <div><span>模型推理</span><strong>Offline</strong></div>
          <div><span>访问权限</span><strong>JWT</strong></div>
        </div>
      </div>

      <ul class="login-features">
        <li><AppIcon name="chart" :size="15" /><span>多家庭趋势与电器构成分析</span></li>
        <li><AppIcon name="sparkles" :size="15" /><span>预训练模型月度用电预测</span></li>
        <li><AppIcon name="shield" :size="15" /><span>基于角色的数据访问控制</span></li>
      </ul>

      <p class="login-brand-foot">FastAPI · SQLite · Vue 3 · Role-based access</p>
    </section>

    <section class="login-form-panel">
      <form class="login-form" @submit.prevent="submit">
        <div class="login-form-head">
          <span class="login-form-eyebrow">WELCOME BACK</span>
          <h2>登录 WattHome</h2>
          <p>使用你的后端账号继续。普通用户与管理员按角色加载各自可访问的数据。</p>
        </div>

        <div v-if="state.apiError" class="login-error" role="alert">
          <AppIcon name="alert" :size="15" />
          <span>{{ state.apiError }}</span>
        </div>

        <label class="login-field">
          <span>用户名</span>
          <div class="login-input">
            <AppIcon name="home" :size="15" />
            <input
              ref="usernameInput"
              v-model.trim="form.username"
              type="text"
              autocomplete="username"
              placeholder="输入后端用户名"
              required
              :disabled="state.apiBusy || state.authStatus === 'connecting'"
            >
          </div>
        </label>

        <label class="login-field">
          <span>密码</span>
          <div class="login-input">
            <AppIcon name="shield" :size="15" />
            <input
              v-model="form.password"
              :type="passwordVisible ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="输入密码"
              required
              :disabled="state.apiBusy || state.authStatus === 'connecting'"
            >
            <button
              class="login-eye"
              type="button"
              :aria-label="passwordVisible ? '隐藏密码' : '显示密码'"
              @click="passwordVisible = !passwordVisible"
            >
              <AppIcon :name="passwordVisible ? 'eyeOff' : 'eye'" :size="15" />
            </button>
          </div>
        </label>

        <button
          class="login-advanced-toggle"
          type="button"
          @click="showAdvanced = !showAdvanced"
        >
          后端地址
          <span>{{ state.apiBase }}</span>
          <AppIcon name="chevronDown" :size="11" />
        </button>

        <label v-if="showAdvanced" class="login-field login-advanced">
          <span>API Base URL</span>
          <div class="login-input">
            <AppIcon name="server" :size="15" />
            <input
              v-model.trim="form.base"
              type="text"
              autocomplete="off"
              spellcheck="false"
              placeholder="/api/v1"
              :disabled="state.apiBusy || state.authStatus === 'connecting'"
              required
            >
          </div>
        </label>

        <button
          class="login-submit"
          type="submit"
          :disabled="state.apiBusy || state.authStatus === 'connecting'"
        >
          <span
            v-if="state.apiBusy || state.authStatus === 'connecting'"
            class="spinner"
          ></span>
          <AppIcon v-else name="arrowRight" :size="15" />
          {{
            state.apiBusy
              ? '正在登录并加载数据…'
              : state.authStatus === 'connecting'
                ? '正在恢复后端会话…'
                : '登录'
          }}
        </button>

        <div class="login-session-note">
          <span class="status-dot" :class="{ live: state.authStatus === 'connecting' }"></span>
          <span v-if="state.authStatus === 'connecting'">正在恢复后端会话…</span>
          <span v-else-if="state.authStatus === 'offline'">后端暂不可用，请检查服务状态后重试</span>
          <span v-else>JWT 仅保存在当前浏览器会话中</span>
        </div>
      </form>
    </section>
  </main>
</template>
