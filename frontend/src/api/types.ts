export type Role = 'user' | 'admin'
export type Granularity = 'day' | 'month' | 'year'

export interface AuthUser {
  id: number
  username: string
  display_name: string | null
  role: Role
}

export interface CurrentUser extends AuthUser {
  is_active: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: AuthUser
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface AdminUser extends AuthUser {
  is_active: boolean
  household_count: number
}

export interface CreateUserPayload {
  username: string
  password: string
  display_name?: string | null
  role: Role
}

export interface UpdateUserPayload {
  display_name?: string | null
  role?: Role
  is_active?: boolean
}

export interface Household {
  household_id: number
  display_name: string
  size_median: number | null
  avg_temp_c: number | null
  avg_daily_kwh: number | null
  reading_count: number
  first_date: string | null
  last_date: string | null
  owner_user_id?: number | null
}

export interface Appliance {
  appliance_id: number
  name: string
  reading_count: number
  avg_energy_kwh: number | null
}

export interface SeriesItem {
  household_id: number
  display_name: string
  period: string
  kwh: number
  reading_count: number
  color_index: number
}

export interface SeriesResponse {
  granularity: Granularity
  start_date: string
  end_date: string
  items: SeriesItem[]
  meta: {
    unit: string
    max_households: number
    excluded_appliance_ids: number[]
  }
}

export interface AveragePoint {
  period: string
  avg_kwh: number
  household_count: number
  expected_households: number
}

export interface AverageResponse {
  granularity: Granularity
  scope: 'all' | 'accessible'
  items: AveragePoint[]
  meta: {
    unit: string
    excluded_appliance_ids: number[]
  }
}

export interface BreakdownItem {
  appliance_id: number
  appliance_name: string
  kwh: number
  share: number
}

export interface BreakdownResponse {
  household_id: number
  start_date: string
  end_date: string
  total_kwh: number
  items: BreakdownItem[]
}

export interface ModelInfo {
  version: string
  trained_at: string | null
  target: string
  input_fields: string[]
  features: string[]
  metrics: {
    mae: number | null
    rmse: number | null
    r2: number | null
  }
  training_rows: number
  validation_rows: number
  level_model?: string
  shape_model?: string
}

export interface PredictRequest {
  household_id: number
  month: number
  household_size: number
  forecast_monthly_temp_c: number
}

export interface PredictHistoryPoint {
  period: string
  actual_avg_daily_kwh: number
  temperature_c: number | null
  reading_days: number
  total_kwh: number
}

export interface PredictForecastPoint {
  period: string
  predicted_avg_daily_kwh: number
  temperature_used_c: number
  monthly_energy_estimate_kwh: number | null
}

export interface PredictResponse {
  household_id: number
  display_name: string
  month: number
  household_size: number
  anchor_month: string | null
  forecast_start_month: string | null
  forecast_end_month: string | null
  history_basis: 'aggregate' | 'appliance_sum' | 'mixed' | 'none'
  history: PredictHistoryPoint[]
  forecast: PredictForecastPoint[]
  predicted_avg_daily_kwh: number
  unit: string
  model_version: string
  average_daily_power_curve_kw?: number[]
  monthly_energy_estimate_kwh?: number | null
  temperature_used_c?: number | null
  level_model?: string
  shape_model?: string
  warnings: string[]
}

export interface ImportHistoryItem {
  import_id: number
  filename: string
  status: 'running' | 'completed' | 'failed' | 'dry_run'
  total_rows: number
  inserted_rows: number
  rejected_rows: number
  imported_at: string
}

export interface ImportResponse {
  import_id: number
  status: 'completed' | 'dry_run'
  filename: string
  total_rows: number
  inserted_rows: number
  rejected_rows: number
  duplicate_rows: number
  quality_flagged_rows: number
}

export interface RangeOption {
  id: '7d' | '30d' | '12m'
  label: string
}

export interface HouseholdSeries {
  household_id: number
  display_name: string
  color_index: number
  points: Array<{
    period: string
    kwh: number | null
  }>
}

export interface AverageSeriesPoint {
  period: string
  avg_kwh: number
}
