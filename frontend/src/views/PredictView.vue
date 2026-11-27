<script setup lang="ts">
import { computed, onMounted } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import { useEnergyStore } from '../stores/energy'
import { formatNumber } from '../utils/format'

const store = useEnergyStore()
const state = store.state
const months = Array.from({ length: 12 }, (_, index) => index + 1)

const predictionDisplay = computed(() => {
  const value = state.prediction.liveResult
  return value == null ? '—' : Number(value).toFixed(2)
})

const predictionSubline = computed(() => {
  const value = state.prediction.liveResult
  if (value == null) {
    return '点击生成预测以调用后端模型'
  }
  return `输入温度 ${state.prediction.temperature}°C · API 推理结果`
})

const forecastMonths = computed(() => {
  if (
    !state.liveForecast ||
    state.liveForecast.length !== 12 ||
    !state.liveForecast.every((value) => Number.isFinite(Number(value)))
  ) {
    return months.map((month) => ({ month, value: null, height: 0 }))
  }
  const values = months.map((month) => Number(state.liveForecast?.[month - 1]) || 0)
  const max = Math.max(...values, 0.001)
  return values.map((value, index) => ({
    month: index + 1,
    value,
    height: Math.max(6, (value / max) * 100)
  }))
})

const metricWidths = computed(() => ({
  mae: Math.min(100, Math.max(8, Number(state.modelInfo.metrics.mae || 0) * 100)),
  rmse: Math.min(100, Math.max(8, Number(state.modelInfo.metrics.rmse || 0) * 80)),
  r2: Math.min(100, Math.max(8, Number(state.modelInfo.metrics.r2 || 0) * 100))
}))

onMounted(() => {
  if (state.connected && state.prediction.liveResult === null && !state.prediction.loading) {
    void store.runPrediction()
  }
})
</script>

<template>
  <div>
    <section class="predict-layout">
      <div class="predict-form-card">
        <span class="form-kicker">
          <AppIcon name="sparkles" :size="10" />
          PRETRAINED · DAILY FORECAST
        </span>
        <h2>预测每日用电量</h2>
        <p>输入月份、温度和居住人口，调用已加载的离线模型进行推理，不绑定具体家庭。</p>

        <div class="form-grid">
          <div class="field-group">
            <label class="field-label" for="predict-month">预测月份</label>
            <div class="select-wrap">
              <select id="predict-month" v-model.number="state.prediction.month">
                <option v-for="month in months" :key="month" :value="month">
                  {{ month }} 月
                </option>
              </select>
              <span class="select-chevron"><AppIcon name="chevronDown" :size="12" /></span>
            </div>
          </div>

          <div class="field-group">
            <label class="field-label" for="predict-temperature">室外温度</label>
            <div class="stepper">
              <input
                id="predict-temperature"
                v-model.number="state.prediction.temperature"
                type="number"
                min="-50"
                max="60"
                step="0.1"
              >
              <span>°C</span>
            </div>
          </div>

          <div class="field-group form-span-2">
            <label class="field-label" for="predict-size">居住人口</label>
            <div class="stepper">
              <button type="button" aria-label="减少人口" @click="store.changePopulation(-1)">−</button>
              <input
                id="predict-size"
                v-model.number="state.prediction.size"
                type="number"
                min="1"
                max="20"
                @blur="store.normalizePopulation()"
              >
              <span>人</span>
              <button type="button" aria-label="增加人口" @click="store.changePopulation(1)">+</button>
            </div>
          </div>
        </div>

        <p class="form-help">
          <strong>POST</strong> /api/v1/ai/predict · 输入字段：forecast_monthly_temp_c、household_size、month。
          预测结果不绑定具体家庭。
        </p>

        <button
          class="predict-submit"
          type="button"
          :disabled="state.prediction.loading"
          @click="store.runPrediction()"
        >
          <AppIcon
            :name="state.prediction.loading ? 'refresh' : 'arrowRight'"
            :size="13"
          />
          {{ state.prediction.loading ? '模型推理中…' : '生成预测' }}
        </button>
      </div>

      <div class="predict-result">
        <div class="result-top">
          <span class="result-label">
            <AppIcon name="bolt" :size="12" />
            预计平均日用电
          </span>
          <span class="model-tag">{{ state.modelInfo.version || '后端模型' }}</span>
        </div>
        <div class="result-main-value">
          {{ predictionDisplay }}<small>kWh / 日</small>
        </div>
        <div class="result-subline">
          <i></i>
          {{ predictionSubline }}
        </div>
        <div class="result-divider"></div>
        <div class="result-facts">
          <div class="result-fact">
            <span>月份</span>
            <strong>{{ state.prediction.month }} 月</strong>
          </div>
          <div class="result-fact">
            <span>温度</span>
            <strong>{{ state.prediction.temperature }} °C</strong>
          </div>
          <div class="result-fact">
            <span>居住人口</span>
            <strong>{{ state.prediction.size }} 人</strong>
          </div>
        </div>
        <p class="result-note">
          结果为给定温度、人口和月份下的典型日均用电估计，不绑定具体家庭。
        </p>
      </div>
    </section>

    <div class="predict-bottom">
      <section class="card forecast-card">
        <div class="forecast-head">
          <div>
            <h2>全年季节曲线</h2>
            <p>{{ state.prediction.temperature }}°C · {{ state.prediction.size }} 人 · 按当前温度估算全年</p>
          </div>
          <span class="micro-label">12 MONTHS</span>
        </div>
        <div class="forecast-bars">
          <div
            v-for="item in forecastMonths"
            :key="item.month"
            class="forecast-bar-col"
            :class="{ active: item.month === state.prediction.month }"
          >
            <div class="forecast-bar-space">
              <span
                v-if="item.value !== null"
                class="forecast-bar"
                :style="{ height: item.height + '%' }"
                :title="`${item.month}月 · ${item.value.toFixed(2)} kWh/日`"
              ></span>
              <span v-else class="forecast-bar-empty"></span>
            </div>
            <small>{{ item.month }}</small>
          </div>
        </div>
      </section>

      <section class="card model-card">
        <div class="model-head">
          <h2>模型信息</h2>
          <p>GET /api/v1/ai/model</p>
        </div>
        <div class="model-body">
          <div class="model-metric">
            <span>MAE</span>
            <div class="model-metric-bar"><i :style="{ width: metricWidths.mae + '%' }"></i></div>
            <strong>{{ state.modelInfo.metrics.mae ?? '—' }}</strong>
          </div>
          <div class="model-metric">
            <span>RMSE</span>
            <div class="model-metric-bar"><i :style="{ width: metricWidths.rmse + '%' }"></i></div>
            <strong>{{ state.modelInfo.metrics.rmse ?? '—' }}</strong>
          </div>
          <div class="model-metric">
            <span>R²</span>
            <div class="model-metric-bar"><i :style="{ width: metricWidths.r2 + '%' }"></i></div>
            <strong>{{ state.modelInfo.metrics.r2 ?? '—' }}</strong>
          </div>
        </div>
        <div class="model-meta">
          <span>{{ state.modelInfo.version || '模型信息' }} · 离线预训练</span>
          <span>{{ formatNumber(state.modelInfo.training_rows) }} rows</span>
        </div>
      </section>
    </div>
  </div>
</template>
