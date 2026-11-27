import type {
  AdminUser,
  AverageResponse,
  BreakdownResponse,
  CreateUserPayload,
  CurrentUser,
  Household,
  ImportHistoryItem,
  ImportResponse,
  LoginResponse,
  ModelInfo,
  Page,
  PredictRequest,
  PredictResponse,
  SeriesResponse,
  UpdateUserPayload
} from './types'

const DEFAULT_API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api/v1'
const API_BASE_KEY = 'watthome.apiBase'
const TOKEN_KEY = 'watthome.token'

let apiBase = localStorage.getItem(API_BASE_KEY) || DEFAULT_API_BASE
let accessToken = sessionStorage.getItem(TOKEN_KEY)

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, message: string, code = 'REQUEST_FAILED') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export function getApiBase(): string {
  return apiBase
}

export function setApiBase(base: string): void {
  apiBase = base.trim().replace(/\/+$/, '') || DEFAULT_API_BASE
  localStorage.setItem(API_BASE_KEY, apiBase)
}

export function setAccessToken(token: string | null): void {
  accessToken = token
  if (token) sessionStorage.setItem(TOKEN_KEY, token)
  else sessionStorage.removeItem(TOKEN_KEY)
}

export function getAccessToken(): string | null {
  return accessToken
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)

  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(
      0,
      `无法连接 ${apiBase}。请确认 FastAPI 已启动，或检查数据源地址。`,
      'NETWORK_ERROR'
    )
  }

  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`
    let code = 'REQUEST_FAILED'
    try {
      const payload = (await response.json()) as {
        detail?: string | { code?: string; message?: string }
      }
      if (typeof payload.detail === 'string') {
        message = payload.detail
      } else if (payload.detail) {
        message = payload.detail.message || payload.detail.code || message
        code = payload.detail.code || code
      }
    } catch {
      // Non-JSON responses keep the HTTP status message.
    }
    throw new ApiError(response.status, message, code)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  async login(username: string, password: string): Promise<LoginResponse> {
    return request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    })
  },

  async me(): Promise<CurrentUser> {
    return request<CurrentUser>('/auth/me')
  },

  async households(page = 1, pageSize = 100): Promise<Page<Household>> {
    return request<Page<Household>>(`/households?page=${page}&page_size=${pageSize}`)
  },

  async allHouseholds(): Promise<Household[]> {
    const firstPage = await this.households(1, 100)
    const items = [...firstPage.items]
    const pageCount = Math.ceil(firstPage.total / firstPage.page_size)
    if (pageCount > 1) {
      const remainingPages = await Promise.all(
        Array.from({ length: pageCount - 1 }, (_, index) => this.households(index + 2, 100))
      )
      remainingPages.forEach((page) => items.push(...page.items))
    }
    return items
  },

  async adminUsers(page = 1, pageSize = 100): Promise<Page<AdminUser>> {
    return request<Page<AdminUser>>(`/admin/users?page=${page}&page_size=${pageSize}`)
  },

  async allAdminUsers(): Promise<AdminUser[]> {
    const firstPage = await this.adminUsers(1, 100)
    const items = [...firstPage.items]
    const pageCount = Math.ceil(firstPage.total / firstPage.page_size)
    if (pageCount > 1) {
      const remainingPages = await Promise.all(
        Array.from({ length: pageCount - 1 }, (_, index) =>
          this.adminUsers(index + 2, 100)
        )
      )
      remainingPages.forEach((page) => items.push(...page.items))
    }
    return items
  },

  async createAdminUser(payload: CreateUserPayload): Promise<AdminUser> {
    return request<AdminUser>('/admin/users', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },

  async updateAdminUser(
    userId: number,
    payload: UpdateUserPayload
  ): Promise<AdminUser> {
    return request<AdminUser>(`/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  },

  async assignAdminHouseholds(
    userId: number,
    householdIds: number[]
  ): Promise<{ user_id: number; owned: number[] }> {
    return request<{ user_id: number; owned: number[] }>(
      `/admin/users/${userId}/households`,
      {
        method: 'POST',
        body: JSON.stringify({ household_ids: householdIds })
      }
    )
  },

  async adminHouseholds(page = 1, pageSize = 100): Promise<Page<Household>> {
    return request<Page<Household>>(
      `/admin/households?page=${page}&page_size=${pageSize}`
    )
  },

  async allAdminHouseholds(): Promise<Household[]> {
    const firstPage = await this.adminHouseholds(1, 100)
    const items = [...firstPage.items]
    const pageCount = Math.ceil(firstPage.total / firstPage.page_size)
    if (pageCount > 1) {
      const remainingPages = await Promise.all(
        Array.from({ length: pageCount - 1 }, (_, index) =>
          this.adminHouseholds(index + 2, 100)
        )
      )
      remainingPages.forEach((page) => items.push(...page.items))
    }
    return items
  },

  async imports(page = 1, pageSize = 20): Promise<Page<ImportHistoryItem>> {
    return request<Page<ImportHistoryItem>>(
      `/admin/imports?page=${page}&page_size=${pageSize}`
    )
  },

  async uploadImport(file: File, dryRun: boolean): Promise<ImportResponse> {
    const body = new FormData()
    body.append('file', file)
    body.append('dry_run', String(dryRun))
    return request<ImportResponse>('/admin/imports', {
      method: 'POST',
      body
    })
  },

  async series(params: URLSearchParams): Promise<SeriesResponse> {
    return request<SeriesResponse>(`/consumption/series?${params.toString()}`)
  },

  async average(params: URLSearchParams): Promise<AverageResponse> {
    return request<AverageResponse>(`/consumption/average?${params.toString()}`)
  },

  async breakdown(params: URLSearchParams): Promise<BreakdownResponse> {
    return request<BreakdownResponse>(`/consumption/breakdown?${params.toString()}`)
  },

  async model(): Promise<ModelInfo> {
    return request<ModelInfo>('/ai/model')
  },

  async predict(payload: PredictRequest): Promise<PredictResponse> {
    return request<PredictResponse>('/ai/predict', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },

  async report(params: URLSearchParams): Promise<Blob> {
    const headers = new Headers({ Accept: 'text/csv' })
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
    const response = await fetch(`${apiBase}/reports/summary?${params.toString()}`, {
      headers
    })
    if (!response.ok) {
      throw new ApiError(response.status, `导出失败（HTTP ${response.status}）`)
    }
    return response.blob()
  }
}
