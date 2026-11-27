import { reactive, watch } from 'vue'
import {
  api,
  ApiError,
  getAccessToken,
  getApiBase,
  setAccessToken,
  setApiBase
} from '../api/client'
import type {
  AverageSeriesPoint,
  AuthUser,
  BreakdownItem,
  Granularity,
  Household,
  HouseholdSeries,
  ModelInfo,
  PredictHistoryPoint,
  PredictForecastPoint,
  PredictResponse,
  RangeOption
} from '../api/types'
import { PALETTE } from '../data/constants'
import {
  addDays,
  downloadBlob,
  formatPeriodCn,
  isoDate,
  periodYear
} from '../utils/format'

export type RangeMode = '7d' | '30d' | '12m'
export type FilterMode = 'all' | 'exclude-ac' | 'exclude-heater' | 'exclude-fridge'
export type AuthStatus = 'connecting' | 'authenticated' | 'anonymous' | 'offline'

export interface RangeParams {
  start: string
  end: string
  granularity: Granularity
  periodLabel: string
}

interface ToastState {
  visible: boolean
  message: string
  tone: 'default' | 'warn'
}

export interface PredictionState {
  householdId: number | null
  month: number
  size: number
  temperature: number
  liveResult: number | null
  lastPrediction: PredictResponse | null
  history: PredictHistoryPoint[]
  forecast: PredictForecastPoint[]
  loading: boolean
}

export interface RecentReport {
  name: string
  time: string
  size: string
}

interface EnergyState {
  authStatus: AuthStatus
  rangeMode: RangeMode
  filterMode: FilterMode
  showAverage: boolean
  connected: boolean
  apiBusy: boolean
  apiError: string
  apiBase: string
  user: AuthUser | null
  households: Household[]
  selectedIds: number[]
  seriesData: HouseholdSeries[]
  averageData: AverageSeriesPoint[]
  breakdown: BreakdownItem[]
  modelInfo: ModelInfo
  loading: boolean
  prediction: PredictionState
  recentReports: RecentReport[]
  toast: ToastState
}

export const RANGE_OPTIONS: RangeOption[] = [
  { id: '7d', label: '7 天' },
  { id: '30d', label: '30 天' },
  { id: '12m', label: '12 个月' }
]

export const FILTER_OPTIONS: Array<{ id: FilterMode; label: string }> = [
  { id: 'all', label: '全部电器' },
  { id: 'exclude-ac', label: '排除空调' },
  { id: 'exclude-heater', label: '排除热水器' },
  { id: 'exclude-fridge', label: '排除冰箱' }
]

export const ENDPOINTS = [
  { method: 'POST', path: '/auth/login' },
  { method: 'GET', path: '/auth/me' },
  { method: 'GET', path: '/households' },
  { method: 'GET', path: '/consumption/series' },
  { method: 'GET', path: '/consumption/average' },
  { method: 'GET', path: '/consumption/breakdown' },
  { method: 'GET', path: '/ai/model' },
  { method: 'POST', path: '/ai/predict' },
  { method: 'GET', path: '/reports/summary' }
]

const EMPTY_MODEL: ModelInfo = {
  version: '',
  trained_at: null,
  target: 'avg_daily_kwh',
  input_fields: ['forecast_monthly_temp_c', 'household_size', 'month'],
  features: [],
  metrics: { mae: null, rmse: null, r2: null },
  training_rows: 0,
  validation_rows: 0
}

export const energy = reactive<EnergyState>({
  authStatus: 'connecting',
  rangeMode: '30d',
  filterMode: 'all',
  showAverage: true,
  connected: false,
  apiBusy: false,
  apiError: '',
  apiBase: getApiBase(),
  user: null,
  households: [],
  selectedIds: [],
  seriesData: [],
  averageData: [],
  breakdown: [],
  modelInfo: { ...EMPTY_MODEL, metrics: { ...EMPTY_MODEL.metrics } },
  loading: false,
  prediction: {
    householdId: null,
    month: new Date().getMonth() + 1,
    size: 1,
    temperature: 20,
    liveResult: null,
    lastPrediction: null,
    history: [],
    forecast: [],
    loading: false
  },
  recentReports: [],
  toast: { visible: false, message: '', tone: 'default' }
})

let toastTimer: number | undefined
let requestSeq = 0

function selectedHouseholds(): Household[] {
  return energy.selectedIds
    .map((id) => energy.households.find((home) => home.household_id === id))
    .filter((home): home is Household => Boolean(home))
}

function activeEndDate(): string {
  const dates = selectedHouseholds()
    .map((home) => home.last_date)
    .filter((date): date is string => Boolean(date))
    .sort()
  return dates.length ? dates[dates.length - 1] : isoDate(new Date())
}

function granularity(): Granularity {
  return energy.rangeMode === '12m' ? 'month' : 'day'
}

function filterLabel(): string {
  return (FILTER_OPTIONS.find((option) => option.id === energy.filterMode) || FILTER_OPTIONS[0]).label
}

function excludedApplianceId(): number | null {
  if (energy.filterMode === 'exclude-ac') return 6
  if (energy.filterMode === 'exclude-heater') return 4
  if (energy.filterMode === 'exclude-fridge') return 1
  return null
}

function rangeParams(): RangeParams {
  const end = activeEndDate()
  let start = end
  if (energy.rangeMode === '7d') {
    const date = new Date(`${end}T00:00:00Z`)
    date.setUTCDate(date.getUTCDate() - 6)
    start = isoDate(date)
  } else if (energy.rangeMode === '30d') {
    const date = new Date(`${end}T00:00:00Z`)
    date.setUTCDate(date.getUTCDate() - 29)
    start = isoDate(date)
  } else {
    const endYear = Number(periodYear(end))
    const endMonth = Number(end.slice(5, 7))
    const startIndex = endYear * 12 + endMonth - 12
    const startYear = Math.floor(startIndex / 12)
    const startMonth = (startIndex % 12) + 1
    start = `${startYear}-${String(startMonth).padStart(2, '0')}-01`
  }
  return {
    start,
    end,
    granularity: granularity(),
    periodLabel: formatPeriodCn(end)
  }
}

function expectedPeriods(start: string, end: string, unit: Granularity): string[] {
  const periods: string[] = []
  if (unit === 'day') {
    let cursor = start
    while (cursor <= end) {
      periods.push(cursor)
      cursor = addDays(cursor, 1)
    }
    return periods
  }
  if (unit === 'month') {
    let year = Number(start.slice(0, 4))
    let month = Number(start.slice(5, 7))
    const endYear = Number(end.slice(0, 4))
    const endMonth = Number(end.slice(5, 7))
    while (year < endYear || (year === endYear && month <= endMonth)) {
      periods.push(`${year}-${String(month).padStart(2, '0')}`)
      month += 1
      if (month > 12) {
        month = 1
        year += 1
      }
    }
    return periods
  }
  for (let year = Number(start.slice(0, 4)); year <= Number(end.slice(0, 4)); year += 1) {
    periods.push(String(year))
  }
  return periods
}

function buildQueryParams(): URLSearchParams {
  const range = rangeParams()
  const params = new URLSearchParams()
  energy.selectedIds.forEach((id) => params.append('household_ids', String(id)))
  params.set('granularity', range.granularity)
  params.set('start_date', range.start)
  params.set('end_date', range.end)
  const excluded = excludedApplianceId()
  if (excluded) params.append('exclude_appliance_ids', String(excluded))
  return params
}

function colorForHousehold(id: number): string {
  const selectedIndex = energy.selectedIds.indexOf(id)
  if (selectedIndex >= 0) return PALETTE[selectedIndex % PALETTE.length]
  const originalIndex = energy.households.findIndex((home) => home.household_id === id)
  return PALETTE[Math.max(0, originalIndex) % PALETTE.length]
}

function resetPredictionOutput(): void {
  energy.prediction.liveResult = null
  energy.prediction.lastPrediction = null
  energy.prediction.history = []
  energy.prediction.forecast = []
}

function clearData(): void {
  requestSeq += 1
  energy.user = null
  energy.households = []
  energy.selectedIds = []
  energy.seriesData = []
  energy.averageData = []
  energy.breakdown = []
  energy.modelInfo = { ...EMPTY_MODEL, metrics: { ...EMPTY_MODEL.metrics } }
  energy.loading = false
  energy.prediction.size = 1
  energy.prediction.temperature = 20
  energy.prediction.liveResult = null
  energy.prediction.lastPrediction = null
  energy.prediction.history = []
  energy.prediction.forecast = []
  energy.prediction.householdId = null
  energy.recentReports = []
  energy.connected = false
}

async function loadLiveData(): Promise<void> {
  if (!energy.connected || !getAccessToken()) return
  if (!energy.selectedIds.length) {
    energy.seriesData = []
    energy.averageData = []
    energy.breakdown = []
    return
  }
  const sequence = ++requestSeq
  energy.loading = true
  try {
    const range = rangeParams()
    const seriesParams = buildQueryParams()
    const averageParams = new URLSearchParams(seriesParams)
    averageParams.delete('household_ids')
    averageParams.set('scope', 'accessible')
    const breakdownParams = new URLSearchParams({
      household_id: String(energy.selectedIds[0]),
      start_date: range.start,
      end_date: range.end
    })
    const [seriesResponse, averageResponse, breakdownResponse] = await Promise.all([
      api.series(seriesParams),
      api.average(averageParams),
      api.breakdown(breakdownParams)
    ])
    if (sequence !== requestSeq) return

    const allPeriods = expectedPeriods(
      range.start,
      range.end,
      range.granularity
    )
    energy.seriesData = energy.selectedIds.map((id, index) => {
      const rows = seriesResponse.items.filter((item) => item.household_id === id)
      const rowMap = new Map(rows.map((row) => [row.period, row]))
      return {
        household_id: id,
        display_name:
          rows[0]?.display_name ||
          energy.households.find((home) => home.household_id === id)?.display_name ||
          `Home ${id}`,
        color_index: rows[0]?.color_index ?? index,
        points: allPeriods.map((period) => {
          const row = rowMap.get(period)
          return { period, kwh: row?.kwh ?? null }
        })
      }
    })
    energy.averageData = averageResponse.items.map((item) => ({
      period: item.period,
      avg_kwh: item.avg_kwh
    }))
    energy.breakdown = breakdownResponse.items
  } catch (error) {
    if (sequence !== requestSeq) return
    if (error instanceof ApiError && error.status === 401) {
      handleSessionExpired()
      return
    }
    notify(error instanceof Error ? error.message : '载入后端数据失败。', 'warn')
  } finally {
    if (sequence === requestSeq) energy.loading = false
  }
}

function notify(message: string, tone: 'default' | 'warn' = 'default'): void {
  energy.toast.message = message
  energy.toast.tone = tone
  energy.toast.visible = true
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    energy.toast.visible = false
  }, 2800)
}

async function refreshData(): Promise<void> {
  if (!energy.connected) {
    notify('请先登录后端服务。', 'warn')
    return
  }
  try {
    const [homes, model] = await Promise.all([api.allHouseholds(), api.model()])
    if (!homes.length) {
      throw new Error('当前账号没有可访问的家庭数据。')
    }
    energy.households = homes
    energy.modelInfo = model
    const accessibleIds = new Set(homes.map((home) => home.household_id))
    energy.selectedIds = energy.selectedIds.filter((id) => accessibleIds.has(id))
    if (!energy.selectedIds.length) {
      energy.selectedIds = homes
        .slice(0, Math.min(3, homes.length))
        .map((home) => home.household_id)
    }
    resetPredictionOutput()
    await loadLiveData()
    notify('已从 FastAPI 刷新当前数据。')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      handleSessionExpired()
      return
    }
    notify(errorMessage(error), 'warn')
  }
}

async function toggleHousehold(id: number): Promise<void> {
  if (!energy.connected) {
    notify('请先登录后端服务。', 'warn')
    return
  }
  const index = energy.selectedIds.indexOf(id)
  if (index >= 0) {
    if (energy.selectedIds.length === 1) {
      notify('至少保留 1 户家庭用于展示。', 'warn')
      return
    }
    energy.selectedIds.splice(index, 1)
  } else {
    if (energy.selectedIds.length >= 5) {
      notify('最多同时对比 5 户家庭。', 'warn')
      return
    }
    energy.selectedIds.push(id)
  }
  resetPredictionOutput()
  await loadLiveData()
}

async function setRange(mode: RangeMode): Promise<void> {
  if (energy.rangeMode === mode) return
  energy.rangeMode = mode
  await loadLiveData()
}

async function setFilter(mode: FilterMode): Promise<void> {
  energy.filterMode = mode
  await loadLiveData()
}

function setShowAverage(value: boolean): void {
  energy.showAverage = value
}

function handleSessionExpired(): void {
  setAccessToken(null)
  clearData()
  energy.authStatus = 'anonymous'
  energy.apiError = '登录状态已失效，请重新登录。'
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'AUTH_INVALID_CREDENTIALS') return '用户名或密码错误。'
    if (error.code === 'NETWORK_ERROR') {
      return `无法连接后端 ${energy.apiBase}，请确认 FastAPI 已启动。`
    }
    return error.message
  }
  return error instanceof Error ? error.message : '无法连接后端。'
}

function authStatusForError(error: unknown): AuthStatus {
  if (
    error instanceof ApiError &&
    (error.status === 0 || error.status >= 500)
  ) {
    return 'offline'
  }
  return 'anonymous'
}

async function connectApi(base: string, username: string, password: string): Promise<boolean> {
  energy.apiBusy = true
  energy.apiError = ''
  energy.authStatus = 'connecting'
  const normalizedBase = base.trim().replace(/\/+$/, '')
  try {
    setApiBase(normalizedBase)
    energy.apiBase = normalizedBase
    const login = await api.login(username, password)
    setAccessToken(login.access_token)
    energy.user = login.user
    energy.user = await api.me()
    const [homes, model] = await Promise.all([api.allHouseholds(), api.model()])
    if (!homes.length) throw new Error('当前账号没有可访问的家庭数据。')
    energy.households = homes
    energy.selectedIds = homes
      .slice(0, Math.min(3, homes.length))
      .map((home) => home.household_id)
    energy.modelInfo = model
    energy.connected = true
    energy.authStatus = 'authenticated'
    resetPredictionOutput()
    await loadLiveData()
    notify(`已连接后端，登录用户：${energy.user.display_name || energy.user.username}`)
    return true
  } catch (error) {
    setAccessToken(null)
    clearData()
    energy.authStatus = authStatusForError(error)
    energy.apiError = errorMessage(error)
    return false
  } finally {
    energy.apiBusy = false
  }
}

function disconnectApi(): void {
  setAccessToken(null)
  clearData()
  energy.authStatus = 'anonymous'
  energy.apiError = ''
  notify('已退出当前后端会话。')
}

async function restoreSession(): Promise<void> {
  const token = getAccessToken()
  if (!token) {
    energy.authStatus = 'anonymous'
    return
  }
  energy.authStatus = 'connecting'
  try {
    const [me, homes, model] = await Promise.all([
      api.me(),
      api.allHouseholds(),
      api.model()
    ])
    if (!homes.length) throw new Error('当前账号没有可访问的家庭数据。')
    energy.user = me
    energy.households = homes
    energy.selectedIds = homes
      .slice(0, Math.min(3, homes.length))
      .map((home) => home.household_id)
    energy.modelInfo = model
    energy.connected = true
    energy.authStatus = 'authenticated'
    resetPredictionOutput()
    await loadLiveData()
  } catch (error) {
    setAccessToken(null)
    clearData()
    energy.authStatus = authStatusForError(error)
    energy.apiError = errorMessage(error)
  }
}

function changePopulation(delta: number): void {
  energy.prediction.size = Math.min(20, Math.max(1, Number(energy.prediction.size || 1) + delta))
}

function normalizePopulation(): void {
  energy.prediction.size = Math.min(20, Math.max(1, Math.round(Number(energy.prediction.size) || 1)))
}

function nextForecastMonth(lastDate: string | null): number {
  const month = lastDate ? Number(lastDate.slice(5, 7)) : new Date().getMonth() + 1
  return month >= 1 && month <= 12 ? (month % 12) + 1 : new Date().getMonth() + 1
}

function selectPredictionHousehold(householdId: number): void {
  const household = energy.households.find((home) => home.household_id === householdId)
  if (!household) return
  energy.prediction.householdId = household.household_id
  energy.prediction.size = Math.min(
    20,
    Math.max(1, Math.round(Number(household.size_median) || 1))
  )
  energy.prediction.temperature = Number(
    (household.avg_temp_c ?? energy.prediction.temperature).toFixed(1)
  )
  energy.prediction.month = nextForecastMonth(household.last_date)
  resetPredictionOutput()
}

async function runPrediction(): Promise<void> {
  if (!energy.connected) {
    notify('请先登录后端服务。', 'warn')
    return
  }
  const householdId = energy.prediction.householdId
  if (householdId === null) {
    notify('请先选择预测家庭。', 'warn')
    return
  }
  normalizePopulation()
  energy.prediction.temperature = Math.max(
    -50,
    Math.min(60, Number(energy.prediction.temperature) || 0)
  )
  energy.prediction.loading = true
  try {
    const result = await api.predict({
      household_id: householdId,
      month: energy.prediction.month,
      household_size: energy.prediction.size,
      forecast_monthly_temp_c: energy.prediction.temperature
    })
    energy.prediction.liveResult = result.predicted_avg_daily_kwh
    energy.prediction.lastPrediction = result
    energy.prediction.history = result.history
    energy.prediction.forecast = result.forecast
    notify('模型推理完成。')
  } catch (error) {
    notify(errorMessage(error), 'warn')
  } finally {
    energy.prediction.loading = false
  }
}

async function exportReport(): Promise<void> {
  if (!energy.connected) {
    notify('请先登录后端服务。', 'warn')
    return
  }
  try {
    const range = rangeParams()
    const params = new URLSearchParams()
    energy.selectedIds.forEach((id) => params.append('household_ids', String(id)))
    params.set('granularity', 'month')
    params.set('start_date', range.start)
    params.set('end_date', range.end)
    params.set('format', 'csv')
    const excluded = excludedApplianceId()
    if (excluded) params.append('exclude_appliance_ids', String(excluded))
    const blob = await api.report(params)
    const filename = `consumption_report_${range.start}_${range.end}.csv`
    downloadBlob(blob, filename)
    energy.recentReports.unshift({
      name: filename,
      time: '刚刚',
      size: `${Math.max(0.1, blob.size / 1024).toFixed(1)} KB`
    })
    energy.recentReports = energy.recentReports.slice(0, 3)
    notify('汇总报告已开始下载。')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      handleSessionExpired()
      return
    }
    notify(errorMessage(error), 'warn')
  }
}

export function useEnergyStore() {
  return {
    state: energy,
    selectedHouseholds,
    activeEndDate,
    granularity,
    filterLabel,
    rangeParams,
    colorForHousehold,
    toggleHousehold,
    setRange,
    setFilter,
    setShowAverage,
    refreshData,
    connectApi,
    disconnectApi,
    runPrediction,
    exportReport,
    changePopulation,
    normalizePopulation,
    selectPredictionHousehold,
    notify
  }
}

export function initializeEnergyStore(): void {
  watch(
    () => [
      energy.prediction.householdId,
      energy.prediction.month,
      energy.prediction.size,
      energy.prediction.temperature
    ],
    () => resetPredictionOutput()
  )
  void restoreSession()
}
