<script setup lang="ts">
import { computed, onMounted } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import PredictionChart from '../components/PredictionChart.vue'
import { useEnergyStore } from '../stores/energy'
import { formatPeriodCn } from '../utils/format'

const store = useEnergyStore()
const state = store.state
const months = Array.from({ length: 12 }, (_, index) => index + 1)

const selectedHousehold = computed(() =>
  state.households.find(
    (home) => home.household_id === state.prediction.householdId
  ) ?? null
)

const predictionDisplay = computed(() => {
  const value = state.prediction.liveResult
  return value == null ? '—' : Number(value).toFixed(2)
})

const predictionSubline = computed(() => {
  const result = state.prediction.lastPrediction
  if (!result) {
    return '点击生成预测以调用后端模型'
  }
  return `${formatPeriodCn(result.forecast_start_month ?? '')} 起 · 历史截至 ${formatPeriodCn(result.anchor_month ?? '')}`
})

const historyBasisLabel = computed(() => {
  const basis = state.prediction.lastPrediction?.history_basis
  if (!basis) return '—'
  if (basis === 'aggregate') return 'Aggregate'
  if (basis === 'mixed') return '混合口径'
  if (basis === 'appliance_sum') return '分项汇总'
  return '暂无数据'
})

function onHouseholdChange(event: Event): void {
  const householdId = Number((event.target as HTMLSelectElement).value)
  if (Number.isFinite(householdId)) {
    store.selectPredictionHousehold(householdId)
  }
}

onMounted(() => {
  if (!state.connected) return
  if (state.prediction.householdId === null && state.households.length) {
    store.selectPredictionHousehold(state.households[0].household_id)
  }
  if (state.prediction.liveResult === null && !state.prediction.loading) {
    void store.runPrediction()
  }
})
</script>

<template>
  <div class="predict-page">
    <section class="predict-layout">
      <div class="predict-form-card">
        <span class="form-kicker">
          <AppIcon name="sparkles" :size="10" />
          PRETRAINED · DAILY FORECAST
        </span>
        <h2>预测每日用电量</h2>
        <p>选择家庭后，模型用温度、人口和月份推理，并把该家庭历史曲线与未来预测连续展示。</p>

        <div class="form-grid">
          <div class="field-group form-span-2">
            <label class="field-label" for="predict-household">预测家庭</label>
            <div class="select-wrap">
              <select
                id="predict-household"
                :value="state.prediction.householdId ?? ''"
                @change="onHouseholdChange"
              >
                <option disabled value="">请选择家庭</option>
                <option
                  v-for="home in state.households"
                  :key="home.household_id"
                  :value="home.household_id"
                >
                  {{ home.display_name }}
                </option>
              </select>
              <span class="select-chevron"><AppIcon name="chevronDown" :size="12" /></span>
            </div>
            <p v-if="selectedHousehold" class="predict-household-meta">
              {{ selectedHousehold.size_median ?? '—' }} 人 ·
              数据 {{ selectedHousehold.first_date ? formatPeriodCn(selectedHousehold.first_date) : '—' }}
              至 {{ selectedHousehold.last_date ? formatPeriodCn(selectedHousehold.last_date) : '—' }}
            </p>
          </div>

          <div class="field-group">
            <label class="field-label" for="predict-month">预测起始月</label>
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
          <strong>POST</strong> /api/v1/ai/predict · 输入 household_id、month、household_size、forecast_monthly_temp_c。
          历史取最近 12 个月，预测默认从家庭最后数据月的下一个月开始。
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
          <span v-if="selectedHousehold" class="result-home-tag">
            {{ selectedHousehold.display_name }}
          </span>
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
            <span>预测起点</span>
            <strong>
              {{
                state.prediction.lastPrediction?.forecast_start_month
                  ? formatPeriodCn(state.prediction.lastPrediction.forecast_start_month)
                  : `${state.prediction.month} 月`
              }}
            </strong>
          </div>
          <div class="result-fact">
            <span>温度</span>
            <strong>{{ state.prediction.temperature }} °C</strong>
          </div>
          <div class="result-fact">
            <span>居住人口</span>
            <strong>{{ state.prediction.size }} 人</strong>
          </div>
          <div class="result-fact">
            <span>历史口径</span>
            <strong>{{ historyBasisLabel }}</strong>
          </div>
        </div>
        <p class="result-note">
          历史总用电优先使用 Aggregate，缺失时回退到分项汇总；未来除起始月外，其余月份使用该家庭同月份历史均温。
        </p>
      </div>
    </section>

    <PredictionChart
      v-if="state.prediction.lastPrediction"
      :history="state.prediction.history"
      :forecast="state.prediction.forecast"
      :household-name="state.prediction.lastPrediction.display_name"
      :anchor-month="state.prediction.lastPrediction.anchor_month"
      :history-basis="state.prediction.lastPrediction.history_basis"
      :loading="state.prediction.loading"
    />
  </div>
</template>
