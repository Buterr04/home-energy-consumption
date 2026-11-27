<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, api } from '../api/client'
import type {
  AdminUser,
  Household,
  ImportHistoryItem,
  ImportResponse,
  Role
} from '../api/types'
import AppIcon from '../components/AppIcon.vue'
import { useEnergyStore } from '../stores/energy'
import { formatNumber, formatPeople } from '../utils/format'

const store = useEnergyStore()
const state = store.state
const router = useRouter()

const users = ref<AdminUser[]>([])
const households = ref<Household[]>([])
const imports = ref<ImportHistoryItem[]>([])
const importTotal = ref(0)
const loading = ref(false)
const pageError = ref('')
const userQuery = ref('')

const showCreateUser = ref(false)
const createBusy = ref(false)
const createError = ref('')
const createForm = reactive<{
  username: string
  password: string
  display_name: string
  role: Role
}>({
  username: '',
  password: '',
  display_name: '',
  role: 'user'
})

const assignUser = ref<AdminUser | null>(null)
const assignSearch = ref('')
const assignIds = ref<number[]>([])
const assignBusy = ref(false)
const assignError = ref('')

const importFile = ref<File | null>(null)
const importDryRun = ref(true)
const importBusy = ref(false)
const importResult = ref<ImportResponse | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const isAdmin = computed(() => state.user?.role === 'admin')
const filteredUsers = computed(() => {
  const query = userQuery.value.trim().toLowerCase()
  if (!query) return users.value
  return users.value.filter(
    (user) =>
      user.username.toLowerCase().includes(query) ||
      (user.display_name || '').toLowerCase().includes(query)
  )
})
const activeUsers = computed(() => users.value.filter((user) => user.is_active).length)
const assignedHouseholds = computed(
  () => households.value.filter((home) => home.owner_user_id != null).length
)
const unassignedHouseholds = computed(
  () => households.value.length - assignedHouseholds.value
)
const visibleAssignHouseholds = computed(() => {
  const query = assignSearch.value.trim().toLowerCase()
  const matching = households.value.filter((home) => {
    if (!query) return true
    return (
      home.display_name.toLowerCase().includes(query) ||
      String(home.household_id).includes(query)
    )
  })
  const selected = matching.filter((home) => assignIds.value.includes(home.household_id))
  const unselected = matching.filter(
    (home) => !assignIds.value.includes(home.household_id)
  )
  return [...selected, ...unselected].slice(0, 80)
})
const assignHiddenCount = computed(() => {
  const query = assignSearch.value.trim().toLowerCase()
  const matched = households.value.filter((home) => {
    if (!query) return true
    return (
      home.display_name.toLowerCase().includes(query) ||
      String(home.household_id).includes(query)
    )
  })
  return Math.max(0, matched.length - visibleAssignHouseholds.value.length)
})

function readableError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'USERNAME_EXISTS') return '用户名已存在，请更换后重试。'
    if (error.code === 'FORBIDDEN_ADMIN') return '当前账号没有管理员权限。'
    return error.message
  }
  return error instanceof Error ? error.message : '操作失败，请稍后重试。'
}

function handleAuthError(error: unknown): boolean {
  if (error instanceof ApiError && error.status === 401) {
    store.disconnectApi()
    return true
  }
  if (error instanceof ApiError && error.code === 'FORBIDDEN_ADMIN') {
    void router.replace('/overview')
    return true
  }
  return false
}

async function loadAdminData(): Promise<void> {
  loading.value = true
  pageError.value = ''
  try {
    const [userItems, householdItems, importPage] = await Promise.all([
      api.allAdminUsers(),
      api.allAdminHouseholds(),
      api.imports(1, 20)
    ])
    users.value = userItems
    households.value = householdItems
    imports.value = importPage.items
    importTotal.value = importPage.total
  } catch (error) {
    if (!handleAuthError(error)) pageError.value = readableError(error)
  } finally {
    loading.value = false
  }
}

function resetCreateForm(): void {
  createForm.username = ''
  createForm.password = ''
  createForm.display_name = ''
  createForm.role = 'user'
  createError.value = ''
}

function openCreateUser(): void {
  resetCreateForm()
  showCreateUser.value = true
}

async function submitCreateUser(): Promise<void> {
  createBusy.value = true
  createError.value = ''
  try {
    const created = await api.createAdminUser({
      username: createForm.username.trim(),
      password: createForm.password,
      display_name: createForm.display_name.trim() || null,
      role: createForm.role
    })
    users.value = [...users.value, created].sort((a, b) => a.id - b.id)
    showCreateUser.value = false
    store.notify(`已创建用户 ${created.username}。`)
  } catch (error) {
    if (!handleAuthError(error)) createError.value = readableError(error)
  } finally {
    createBusy.value = false
  }
}

async function updateUser(
  user: AdminUser,
  payload: { role?: Role; is_active?: boolean }
): Promise<void> {
  if (user.id === state.user?.id && payload.is_active === false) {
    store.notify('不能停用当前登录的管理员账号。', 'warn')
    return
  }
  try {
    const updated = await api.updateAdminUser(user.id, payload)
    const index = users.value.findIndex((item) => item.id === updated.id)
    if (index >= 0) users.value[index] = updated
    store.notify(`已更新用户 ${updated.username}。`)
  } catch (error) {
    if (!handleAuthError(error)) store.notify(readableError(error), 'warn')
  }
}

function onRoleChange(user: AdminUser, event: Event): void {
  const role = (event.target as HTMLSelectElement).value as Role
  if (role === user.role) return
  if (user.id === state.user?.id) {
    store.notify('不能修改当前登录管理员的角色。', 'warn')
    return
  }
  void updateUser(user, { role })
}

function openAssignment(user: AdminUser): void {
  assignUser.value = user
  assignSearch.value = ''
  assignError.value = ''
  assignIds.value = households.value
    .filter((home) => home.owner_user_id === user.id)
    .map((home) => home.household_id)
}

function toggleAssignHousehold(id: number): void {
  const index = assignIds.value.indexOf(id)
  if (index >= 0) assignIds.value.splice(index, 1)
  else assignIds.value.push(id)
}

async function saveAssignment(): Promise<void> {
  if (!assignUser.value) return
  if (!assignIds.value.length) {
    assignError.value = '请至少选择 1 户家庭。'
    return
  }
  assignBusy.value = true
  assignError.value = ''
  try {
    await api.assignAdminHouseholds(assignUser.value.id, assignIds.value)
    const username = assignUser.value.username
    assignUser.value = null
    await loadAdminData()
    await store.refreshData()
    store.notify(`已更新 ${username} 的家庭归属。`)
  } catch (error) {
    if (!handleAuthError(error)) assignError.value = readableError(error)
  } finally {
    assignBusy.value = false
  }
}

function pickImportFile(event: Event): void {
  const input = event.target as HTMLInputElement
  importFile.value = input.files?.[0] || null
  importResult.value = null
}

async function runImport(): Promise<void> {
  if (!importFile.value) return
  importBusy.value = true
  importResult.value = null
  try {
    const result = await api.uploadImport(importFile.value, importDryRun.value)
    importResult.value = result
    const importPage = await api.imports(1, 20)
    imports.value = importPage.items
    importTotal.value = importPage.total
    if (result.status === 'completed') await store.refreshData()
    store.notify(result.status === 'dry_run' ? 'CSV 校验完成。' : 'CSV 导入完成。')
  } catch (error) {
    if (!handleAuthError(error)) store.notify(readableError(error), 'warn')
  } finally {
    importBusy.value = false
  }
}

function formatImportedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(() => {
  if (!isAdmin.value) {
    void router.replace('/overview')
    return
  }
  void loadAdminData()
})
</script>

<template>
  <div class="admin-view">
    <section class="admin-stats" aria-label="管理员概览">
      <article class="admin-stat">
        <span class="admin-stat-icon blue"><AppIcon name="shield" :size="15" /></span>
        <span><small>系统用户</small><strong>{{ formatNumber(users.length) }}</strong></span>
        <em>{{ activeUsers }} 个启用</em>
      </article>
      <article class="admin-stat">
        <span class="admin-stat-icon green"><AppIcon name="home" :size="15" /></span>
        <span><small>全部家庭</small><strong>{{ formatNumber(households.length) }}</strong></span>
        <em>{{ assignedHouseholds }} 户已分配</em>
      </article>
      <article class="admin-stat">
        <span class="admin-stat-icon orange"><AppIcon name="database" :size="15" /></span>
        <span><small>未分配家庭</small><strong>{{ formatNumber(unassignedHouseholds) }}</strong></span>
        <em>可在用户行中转移归属</em>
      </article>
      <article class="admin-stat">
        <span class="admin-stat-icon violet"><AppIcon name="refresh" :size="15" /></span>
        <span><small>导入批次</small><strong>{{ formatNumber(importTotal) }}</strong></span>
        <em>GET /admin/imports</em>
      </article>
    </section>

    <div v-if="pageError" class="admin-page-error">
      <AppIcon name="alert" :size="15" />
      <span>{{ pageError }}</span>
      <button type="button" @click="loadAdminData">重试</button>
    </div>

    <div class="admin-grid">
      <section class="card admin-users-card">
        <div class="admin-card-head">
          <div>
            <h2>用户与权限</h2>
            <p>创建账号、切换角色或停用用户。当前管理员不能停用自己。</p>
          </div>
          <div class="admin-card-actions">
            <label class="admin-search">
              <AppIcon name="search" :size="12" />
              <input v-model.trim="userQuery" type="search" placeholder="搜索用户名">
            </label>
            <button class="admin-primary" type="button" @click="openCreateUser">
              <AppIcon name="plus" :size="12" />
              新建用户
            </button>
          </div>
        </div>

        <div v-if="loading" class="admin-loading">
          <span class="spinner"></span>
          正在加载管理员数据
        </div>

        <div v-else class="table-scroll">
          <table class="admin-table">
            <thead>
              <tr>
                <th>用户</th>
                <th>角色</th>
                <th>家庭</th>
                <th>状态</th>
                <th class="admin-table-actions">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in filteredUsers" :key="user.id">
                <td>
                  <span class="admin-user-cell">
                    <span class="admin-avatar">{{ user.username.slice(0, 1).toUpperCase() }}</span>
                    <span>
                      <strong>{{ user.display_name || user.username }}</strong>
                      <small>@{{ user.username }} · ID {{ user.id }}</small>
                    </span>
                  </span>
                </td>
                <td>
                  <select
                    class="admin-role-select"
                    :value="user.role"
                    :disabled="user.id === state.user?.id"
                    @change="onRoleChange(user, $event)"
                  >
                    <option value="user">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </td>
                <td>{{ user.household_count }} 户</td>
                <td>
                  <span class="admin-status" :class="{ inactive: !user.is_active }">
                    <i></i>{{ user.is_active ? '启用' : '停用' }}
                  </span>
                </td>
                <td>
                  <span class="admin-row-actions">
                    <button type="button" @click="openAssignment(user)">
                      分配家庭
                    </button>
                    <button
                      type="button"
                      :disabled="user.id === state.user?.id"
                      @click="updateUser(user, { is_active: !user.is_active })"
                    >
                      {{ user.is_active ? '停用' : '启用' }}
                    </button>
                  </span>
                </td>
              </tr>
              <tr v-if="!filteredUsers.length">
                <td colspan="5" class="admin-empty">没有匹配的用户</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <aside class="admin-side">
        <section class="card admin-import-card">
          <div class="admin-card-head compact">
            <div>
              <h2>CSV 数据导入</h2>
              <p>先校验再入库，避免直接污染业务数据。</p>
            </div>
            <span class="admin-api-tag">POST /admin/imports</span>
          </div>

          <input
            ref="fileInput"
            class="admin-file-input"
            type="file"
            accept=".csv,text/csv"
            @change="pickImportFile"
          >
          <button
            class="admin-file-picker"
            type="button"
            :disabled="importBusy"
            @click="fileInput?.click()"
          >
            <span class="admin-file-icon"><AppIcon name="file" :size="18" /></span>
            <span>
              <strong>{{ importFile?.name || '选择 CSV 文件' }}</strong>
              <small>
                {{ importFile ? `${(importFile.size / 1024 / 1024).toFixed(2)} MB` : '支持原始家庭用电数据 CSV' }}
              </small>
            </span>
          </button>

          <label class="admin-check">
            <input v-model="importDryRun" type="checkbox" :disabled="importBusy">
            <span></span>
            仅校验，不写入数据库
          </label>

          <button
            class="admin-primary full"
            type="button"
            :disabled="!importFile || importBusy"
            @click="runImport"
          >
            <span v-if="importBusy" class="spinner"></span>
            <AppIcon v-else name="database" :size="12" />
            {{ importBusy ? '正在处理 CSV…' : importDryRun ? '校验 CSV' : '导入 CSV' }}
          </button>

          <div v-if="importResult" class="admin-import-result">
            <span>{{ importResult.status === 'dry_run' ? '校验完成' : '导入完成' }}</span>
            <dl>
              <div><dt>总行数</dt><dd>{{ formatNumber(importResult.total_rows) }}</dd></div>
              <div><dt>已写入</dt><dd>{{ formatNumber(importResult.inserted_rows) }}</dd></div>
              <div><dt>重复</dt><dd>{{ formatNumber(importResult.duplicate_rows) }}</dd></div>
              <div><dt>质量标记</dt><dd>{{ formatNumber(importResult.quality_flagged_rows) }}</dd></div>
            </dl>
          </div>
        </section>

        <section class="card admin-history-card">
          <div class="admin-card-head compact">
            <div>
              <h2>最近导入</h2>
              <p>后端返回的最新 {{ imports.length }} 条记录</p>
            </div>
          </div>
          <div class="admin-history-list">
            <div v-for="item in imports" :key="item.import_id" class="admin-history-row">
              <span class="admin-history-icon"><AppIcon name="file" :size="12" /></span>
              <span class="admin-history-copy">
                <strong>{{ item.filename }}</strong>
                <small>
                  {{ formatImportedAt(item.imported_at) }} · {{ formatNumber(item.inserted_rows) }} 行
                </small>
              </span>
              <span class="admin-import-status" :class="item.status">
                {{ item.status === 'completed' ? '完成' : item.status === 'dry_run' ? '校验' : item.status === 'failed' ? '失败' : '进行中' }}
              </span>
            </div>
            <p v-if="!imports.length" class="admin-empty">暂无导入记录</p>
          </div>
        </section>
      </aside>
    </div>

    <Transition name="page-fade">
      <div v-if="showCreateUser" class="admin-modal-backdrop" @click.self="showCreateUser = false">
        <form class="admin-modal" @submit.prevent="submitCreateUser">
          <div class="admin-modal-head">
            <div>
              <span class="form-kicker">ADMIN · CREATE USER</span>
              <h2>创建系统用户</h2>
            </div>
            <button type="button" aria-label="关闭" @click="showCreateUser = false">
              <AppIcon name="close" :size="14" />
            </button>
          </div>

          <div v-if="createError" class="login-error">
            <AppIcon name="alert" :size="14" />
            <span>{{ createError }}</span>
          </div>

          <label class="admin-field">
            <span>用户名</span>
            <input v-model.trim="createForm.username" required maxlength="64" autocomplete="off">
          </label>
          <label class="admin-field">
            <span>初始密码</span>
            <input
              v-model="createForm.password"
              type="password"
              required
              minlength="6"
              maxlength="72"
              autocomplete="new-password"
            >
          </label>
          <label class="admin-field">
            <span>显示名称</span>
            <input v-model.trim="createForm.display_name" maxlength="120">
          </label>
          <label class="admin-field">
            <span>角色</span>
            <select v-model="createForm.role">
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </label>

          <div class="admin-modal-actions">
            <button type="button" class="admin-secondary" @click="showCreateUser = false">
              取消
            </button>
            <button type="submit" class="admin-primary" :disabled="createBusy">
              <span v-if="createBusy" class="spinner"></span>
              <AppIcon v-else name="plus" :size="12" />
              {{ createBusy ? '正在创建…' : '创建用户' }}
            </button>
          </div>
        </form>
      </div>
    </Transition>

    <Transition name="page-fade">
      <div v-if="assignUser" class="admin-modal-backdrop" @click.self="assignUser = null">
        <section class="admin-modal assign-modal">
          <div class="admin-modal-head">
            <div>
              <span class="form-kicker">HOUSEHOLD OWNERSHIP</span>
              <h2>分配家庭给 {{ assignUser.display_name || assignUser.username }}</h2>
            </div>
            <button type="button" aria-label="关闭" @click="assignUser = null">
              <AppIcon name="close" :size="14" />
            </button>
          </div>

          <p class="assign-note">
            保存后，所选家庭会转移给该用户。未选中的家庭保持原归属不变。
          </p>

          <label class="admin-search wide">
            <AppIcon name="search" :size="12" />
            <input
              v-model.trim="assignSearch"
              type="search"
              placeholder="按家庭名称或 ID 搜索"
            >
          </label>

          <div class="assign-selected-line">
            <span>已选择 <strong>{{ assignIds.length }}</strong> 户</span>
            <button v-if="assignIds.length" type="button" @click="assignIds = []">清空</button>
          </div>

          <div class="assign-household-list">
            <button
              v-for="home in visibleAssignHouseholds"
              :key="home.household_id"
              class="assign-household"
              :class="{ selected: assignIds.includes(home.household_id) }"
              type="button"
              @click="toggleAssignHousehold(home.household_id)"
            >
              <span class="home-check"><AppIcon name="check" :size="10" /></span>
              <span>
                <strong>{{ home.display_name }}</strong>
                <small>
                  #{{ home.household_id }} · {{ formatPeople(home.size_median) }}
                  · 当前 {{ home.owner_user_id ? `用户 ${home.owner_user_id}` : '未分配' }}
                </small>
              </span>
            </button>
            <p v-if="!visibleAssignHouseholds.length" class="admin-empty">没有匹配的家庭</p>
          </div>
          <p v-if="assignHiddenCount" class="assign-hidden-note">
            还有 {{ assignHiddenCount }} 户未显示，请使用搜索定位。
          </p>
          <p v-if="assignError" class="assign-error">{{ assignError }}</p>

          <div class="admin-modal-actions">
            <button type="button" class="admin-secondary" @click="assignUser = null">
              取消
            </button>
            <button
              type="button"
              class="admin-primary"
              :disabled="assignBusy"
              @click="saveAssignment"
            >
              <span v-if="assignBusy" class="spinner"></span>
              <AppIcon v-else name="check" :size="12" />
              {{ assignBusy ? '正在保存…' : '保存归属' }}
            </button>
          </div>
        </section>
      </div>
    </Transition>
  </div>
</template>
