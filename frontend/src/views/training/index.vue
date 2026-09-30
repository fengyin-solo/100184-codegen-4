<template>
  <section class="page training-page">
    <header class="page-head">
      <div>
        <h2>养护人员资质培训台账</h2>
        <p class="page-desc">
          按作业人员维护资质、培训计划与复训记录；其他班组只读，本班组培训管理员可写，管理岗可核对全部班组。
        </p>
      </div>
      <div class="identity-note">
        当前身份：{{ session.operator }} · {{ session.role }}<template v-if="session.team"> · {{ session.team }}</template>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">工作台复训待办</span>
        <strong class="stat-value">{{ workbench.total }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已逾期</span>
        <strong class="stat-value danger">{{ workbench.overdue }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">30 天内到期</span>
        <strong class="stat-value">{{ workbench.due_soon }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">培训台账提醒条数</span>
        <strong class="stat-value">{{ currentReminderRows.length }}</strong>
      </article>
    </div>

    <div class="training-layout">
      <aside class="training-side">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-button"
          :class="{ active: activeTab === tab.key }"
          type="button"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
        </button>
      </aside>

      <main class="training-main">
        <form class="filter-bar" @submit.prevent="reload">
          <label class="filter-item">
            <span>班组</span>
            <select v-model="teamFilter">
              <option value="">全部班组</option>
              <option v-for="team in teams" :key="team" :value="team">{{ team }}</option>
            </select>
          </label>
          <label v-if="statusOptions.length" class="filter-item">
            <span>状态</span>
            <select v-model="statusFilter">
              <option value="">全部状态</option>
              <option v-for="status in statusOptions" :key="status" :value="status">{{ status }}</option>
            </select>
          </label>
          <label class="filter-item">
            <span>关键词</span>
            <input v-model="keyword" placeholder="编号 / 人员 / 课程" />
          </label>
          <button class="btn" type="submit">查询</button>
        </form>

        <div class="table-toolbar">
          <button v-if="canCreate" class="btn primary" type="button" @click="openCreate">
            {{ createLabel }}
          </button>
          <span v-else class="readonly-note">{{ session.role }}仅可查看台账记录，不能改动。</span>
          <span class="consistency-note">{{ consistencyMessage }}</span>
        </div>

        <table class="data-table">
          <thead>
            <tr>
              <th v-for="column in columns" :key="column">{{ columnLabels[column] ?? column }}</th>
              <th>权限与操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="String(row.id)">
              <td v-for="column in columns" :key="column">
                <span v-if="column === 'status'" class="status-pill" :class="statusClass(row[column])">{{ row[column] ?? '—' }}</span>
                <span v-else>{{ formatValue(row[column]) }}</span>
              </td>
              <td class="row-actions training-actions">
                <template v-if="activeTab === 'qualifications'">
                  <button v-if="session.isManager" class="link" type="button" @click="verifyQualification(row)">管理岗核对</button>
                  <button v-if="canEditTeam(row.team)" class="link" type="button" @click="openEditQualification(row)">修改</button>
                  <button v-if="canEditTeam(row.team)" class="link danger-link" type="button" @click="leaveQualification(row)">登记离岗</button>
                  <span v-if="!session.isManager && !canEditTeam(row.team)" class="readonly-note">其他班组：只读</span>
                </template>
                <template v-else-if="activeTab === 'plans'">
                  <button v-if="canEditTeam(row.team)" class="link" type="button" @click="openEditPlan(row)">修改</button>
                  <span v-else-if="!session.isManager" class="readonly-note">其他班组：只读</span>
                  <span v-else class="readonly-note">管理岗核对，不改记录</span>
                </template>
                <template v-else-if="activeTab === 'retraining'">
                  <button v-if="canEditTeam(row.team)" class="link" type="button" @click="openEditRetraining(row)">修改</button>
                  <button v-if="canEditTeam(row.team) && row.status !== '已完成'" class="link" type="button" @click="completeRetraining(row)">登记完成</button>
                  <span v-else-if="!session.isManager" class="readonly-note">其他班组：只读</span>
                  <span v-else class="readonly-note">管理岗核对，不改记录</span>
                </template>
                <template v-else-if="activeTab === 'reminders'">
                  <span class="readonly-note">由复训台账自动汇总，待办完成后同步消除</span>
                </template>
                <template v-else>
                  <span class="readonly-note">资质校验通过后生成作业计划</span>
                </template>
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的数据</td>
            </tr>
          </tbody>
        </table>
      </main>
    </div>

    <div v-if="formMode" class="form-panel">
      <div class="form-head">
        <strong>{{ formMode.title }}</strong>
        <button class="link" type="button" @click="closeForm">关闭</button>
      </div>
      <div class="form-grid">
        <label v-for="field in formFields" :key="field.name" class="form-item">
          <span>{{ field.label }}</span>
          <select v-if="field.type === 'select'" v-model="formValues[field.name]" :disabled="field.disabled">
            <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
          </select>
          <input
            v-else-if="field.type === 'checkbox'"
            v-model="formValues[field.name]"
            type="checkbox"
          />
          <input
            v-else
            v-model="formValues[field.name]"
            :type="field.type"
            :placeholder="field.placeholder"
          />
        </label>
      </div>
      <footer class="form-foot">
        <button class="btn primary" type="button" @click="submitForm">提交</button>
        <span v-if="successMessage" class="success-text">{{ successMessage }}</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </div>

    <footer class="page-foot">
      <span>{{ activeTab === 'assignments' ? '排单仅在全部人员资质有效时落单' : '离岗人员历史记录保留，不做物理删除' }}</span>
      <span v-if="blockedItem" class="error-text">拦截项：{{ blockedItem }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore, TEAMS } from '@/stores/session'

type RowValue = string | number | boolean | null | string[]
type Row = Record<string, RowValue>
type Entity = 'qualifications' | 'plans' | 'retraining' | 'reminders' | 'assignments'
type FieldType = 'text' | 'date' | 'number' | 'select' | 'checkbox'
type FormField = {
  name: string
  label: string
  type?: FieldType
  placeholder?: string
  options?: string[]
  disabled?: boolean
}
type FormMode = {
  entity: Entity
  id?: number
  title: string
}
type ApiError = Error & { blockedItem?: string; blockers?: { personnel_name: string; blocked_item: string; reason: string }[] }

const session = useSessionStore()
const teams = [...TEAMS]
const activeTab = ref<Entity>('qualifications')
const rows = ref<Row[]>([])
const workbench = ref({ team: '', total: 0, overdue: 0, due_soon: 0, items: [] as Row[], source: '' })
const keyword = ref('')
const teamFilter = ref<string>(session.isManager ? '' : session.team)
const statusFilter = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const blockedItem = ref('')
const formMode = ref<FormMode | null>(null)
const formValues = ref<Record<string, RowValue>>({})

const tabs = [
  { key: 'qualifications' as Entity, label: '人员资质' },
  { key: 'plans' as Entity, label: '培训计划' },
  { key: 'retraining' as Entity, label: '复训记录' },
  { key: 'reminders' as Entity, label: '复训到期提醒' },
  { key: 'assignments' as Entity, label: '养护作业排单' },
]

const columnMap: Record<Exclude<Entity, 'reminders' | 'assignments'>, string[]> = {
  qualifications: ['id', 'personnel_id', 'personnel_name', 'team', 'certificate_name', 'certificate_no', 'certificate_expiry', 'employment_status', 'status', 'assignment_allowed', 'verified'],
  plans: ['id', 'plan_no', 'team', 'training_topic', 'training_type', 'personnel_id', 'personnel_name', 'planned_date', 'status'],
  retraining: ['id', 'record_no', 'team', 'personnel_id', 'personnel_name', 'course_name', 'last_training_date', 'due_date', 'status', 'completed_date', 'result'],
}

const columnLabels: Record<string, string> = {
  id: 'ID',
  personnel_id: '人员编号',
  personnel_name: '姓名',
  team: '班组',
  certificate_name: '资质名称',
  certificate_no: '证书编号',
  certificate_expiry: '有效期至',
  employment_status: '用工状态',
  status: '台账状态',
  assignment_allowed: '允许排作业',
  verified: '管理岗核对',
  plan_no: '计划编号',
  training_topic: '培训主题',
  training_type: '培训类型',
  planned_date: '计划日期',
  record_no: '复训编号',
  course_name: '复训课程',
  last_training_date: '上次培训',
  due_date: '复训到期',
  completed_date: '完成日期',
  result: '复训结果',
  record_no2: '记录编号',
  days_remaining: '剩余天数',
  qualification_status: '资质状态',
  assignment_no: '作业单号',
  work_name: '作业名称',
  scheduled_date: '计划日期',
  worker_ids: '作业人员',
}

const statusOptionsMap: Record<Entity, string[]> = {
  qualifications: ['正常', '待复训', '已过期', '已暂停', '离岗'],
  plans: ['待开始', '进行中', '已完成', '已取消'],
  retraining: ['待复训', '已完成'],
  reminders: [],
  assignments: ['待作业', '已完成', '已取消'],
}

const columns = computed<string[]>(() => {
  if (activeTab.value === 'reminders') {
    return ['record_no', 'team', 'personnel_id', 'personnel_name', 'course_name', 'due_date', 'days_remaining', 'qualification_status']
  }
  if (activeTab.value === 'assignments') {
    return ['assignment_no', 'team', 'work_name', 'scheduled_date', 'worker_ids', 'status']
  }
  return columnMap[activeTab.value]
})
const statusOptions = computed(() => statusOptionsMap[activeTab.value])
const reminderRows = computed(() => workbench.value.items)
const currentReminderRows = computed(() => {
  if (activeTab.value !== 'reminders') return reminderRows.value
  return rows.value
})
const reminderScopeTeam = computed(() => teamFilter.value || '全部班组')
const consistencyMessage = computed(() => {
  if (activeTab.value !== 'reminders') {
    return `${workbench.value.team}工作台待办 ${workbench.value.total} 条（来自培训台账复训记录）`
  }
  if (workbench.value.team === reminderScopeTeam.value) {
    return `工作台待办 ${workbench.value.total} 条 = 当前培训台账复训到期提醒 ${currentReminderRows.value.length} 条（${workbench.value.source}）`
  }
  return `当前为跨班组只读：培训台账显示 ${currentReminderRows.value.length} 条；本班组（${workbench.value.team}）工作台待办为 ${workbench.value.total} 条`
})
const canCreate = computed(() => session.isTrainingAdmin && activeTab.value !== 'reminders')
const createLabel = computed(() => {
  if (activeTab.value === 'assignments') return session.isManager ? '跨班组校验排单' : '提交本班组排单'
  return `登记${currentLabel.value}`
})
const currentLabel = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.label ?? '')
const formFields = computed<FormField[]>(() => buildFormFields(formMode.value))

function buildFormFields(mode: FormMode | null): FormField[] {
  if (!mode) return []
  if (mode.entity === 'assignments') {
    return [
      { name: 'assignment_no', label: '养护作业单号', placeholder: 'WORK-2026-001' },
      { name: 'team', label: '作业班组', type: 'select', options: teams, disabled: !session.isManager },
      { name: 'work_name', label: '作业名称', placeholder: '检查井清淤' },
      { name: 'scheduled_date', label: '计划作业日期', type: 'date' },
      { name: 'worker_ids_text', label: '人员编号（逗号分隔）', placeholder: 'YG-001,YG-002' },
    ]
  }
  if (mode.id) {
    if (mode.entity === 'qualifications') {
      return [
        { name: 'certificate_no', label: '证书编号' },
        { name: 'certificate_name', label: '资质名称' },
        { name: 'certificate_level', label: '资质等级' },
        { name: 'certificate_issue_date', label: '发证日期', type: 'date' },
        { name: 'certificate_expiry', label: '有效期至', type: 'date' },
        { name: 'suspended', label: '暂停资质', type: 'checkbox' },
        { name: 'suspend_reason', label: '暂停原因' },
      ]
    }
    if (mode.entity === 'plans') {
      return [
        { name: 'training_topic', label: '培训主题' },
        { name: 'training_type', label: '培训类型', type: 'select', options: ['初训', '年度培训', '复训', '补训'] },
        { name: 'personnel_id', label: '人员编号' },
        { name: 'personnel_name', label: '姓名' },
        { name: 'planned_date', label: '计划日期', type: 'date' },
        { name: 'trainer', label: '培训讲师' },
        { name: 'location', label: '培训地点' },
        { name: 'hours', label: '培训学时', type: 'number' },
        { name: 'status', label: '状态', type: 'select', options: statusOptionsMap.plans },
        { name: 'remark', label: '备注' },
      ]
    }
    return [
      { name: 'course_name', label: '复训课程' },
      { name: 'last_training_date', label: '上次培训日期', type: 'date' },
      { name: 'due_date', label: '复训到期日', type: 'date' },
      { name: 'trainer', label: '培训讲师' },
      { name: 'remark', label: '备注' },
    ]
  }
  if (mode.entity === 'qualifications') {
    return [
      { name: 'personnel_id', label: '人员编号', placeholder: 'YG-007' },
      { name: 'personnel_name', label: '姓名' },
      { name: 'team', label: '归属班组', type: 'select', options: teams, disabled: true },
      { name: 'certificate_no', label: '证书编号' },
      { name: 'certificate_name', label: '资质名称' },
      { name: 'certificate_level', label: '资质等级' },
      { name: 'certificate_issue_date', label: '发证日期', type: 'date' },
      { name: 'certificate_expiry', label: '有效期至', type: 'date' },
    ]
  }
  if (mode.entity === 'plans') {
    return [
      { name: 'plan_no', label: '计划编号' },
      { name: 'team', label: '归属班组', type: 'select', options: teams, disabled: true },
      { name: 'training_topic', label: '培训主题' },
      { name: 'training_type', label: '培训类型', type: 'select', options: ['初训', '年度培训', '复训', '补训'] },
      { name: 'personnel_id', label: '人员编号' },
      { name: 'personnel_name', label: '姓名' },
      { name: 'planned_date', label: '计划日期', type: 'date' },
      { name: 'trainer', label: '培训讲师' },
      { name: 'location', label: '培训地点' },
      { name: 'hours', label: '培训学时', type: 'number' },
      { name: 'remark', label: '备注' },
    ]
  }
  return [
    { name: 'record_no', label: '复训记录编号' },
    { name: 'qualification_id', label: '关联资质ID', type: 'number' },
    { name: 'course_name', label: '复训课程' },
    { name: 'last_training_date', label: '上次培训日期', type: 'date' },
    { name: 'due_date', label: '复训到期日', type: 'date' },
    { name: 'trainer', label: '培训讲师' },
    { name: 'remark', label: '备注' },
  ]
}

function canEditTeam(team: RowValue) {
  return session.isTrainingAdmin && session.team === team
}

function formatValue(value: RowValue) {
  if (Array.isArray(value)) return value.join('、')
  if (value === true) return '是'
  if (value === false) return '否'
  return value ?? '—'
}

function statusClass(value: RowValue) {
  return {
    danger: value === '已过期' || value === '已暂停' || value === '已逾期',
    warning: value === '待复训' || value === '进行中' || value === '待开始',
    muted: value === '离岗' || value === '已完成',
  }
}

function switchTab(tab: Entity) {
  activeTab.value = tab
  statusFilter.value = ''
  closeForm()
  void reload()
}

async function apiAction(path: string, init?: RequestInit) {
  const response = await request(path, { ...init, headers: { ...session.authHeaders, ...(init?.headers ?? {}) } })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(payload.message ?? `接口返回 ${response.status}`) as ApiError
    error.blockedItem = payload.blocked_item
    error.blockers = payload.blockers
    throw error
  }
  return payload
}

async function loadWorkbench() {
  const query = new URLSearchParams()
  const workbenchTeam = session.isManager ? teamFilter.value : session.team
  if (workbenchTeam) query.set('team', workbenchTeam)
  const payload = await apiAction(`/api/training/workbench?${query.toString()}`)
  workbench.value = payload
}

async function reload() {
  errorMessage.value = ''
  successMessage.value = ''
  blockedItem.value = ''
  try {
    await loadWorkbench()
    const query = new URLSearchParams()
    if (teamFilter.value) query.set('team', teamFilter.value)
    if (statusFilter.value && activeTab.value !== 'assignments') query.set('status', statusFilter.value)
    if (keyword.value && activeTab.value !== 'assignments') query.set('keyword', keyword.value)
    const payload = await apiAction(`/api/training/${activeTab.value}?${query.toString()}`)
    rows.value = payload.items ?? []
  } catch (error) {
    applyError(error)
  }
}

function openCreate() {
  errorMessage.value = ''
  successMessage.value = ''
  if (activeTab.value === 'assignments') {
    formMode.value = { entity: 'assignments', title: '养护作业排单资质校验' }
    formValues.value = {
      assignment_no: `WORK-${new Date().toISOString().slice(0, 10)}-01`,
      team: session.team || teams[0],
      work_name: '检查井养护作业',
      scheduled_date: new Date().toISOString().slice(0, 10),
      worker_ids_text: 'YG-001',
    }
    return
  }
  formMode.value = { entity: activeTab.value, title: createLabel.value }
  formValues.value = activeTab.value === 'qualifications'
    ? { team: session.team }
    : activeTab.value === 'plans'
      ? { team: session.team, training_type: '复训' }
      : {}
}

function openEditQualification(row: Row) {
  formMode.value = { entity: 'qualifications', id: Number(row.id), title: '修改人员资质' }
  formValues.value = pick(row, buildFormFields(formMode.value).map((field) => field.name))
}

function openEditPlan(row: Row) {
  formMode.value = { entity: 'plans', id: Number(row.id), title: '修改培训计划' }
  formValues.value = pick(row, buildFormFields(formMode.value).map((field) => field.name))
}

function openEditRetraining(row: Row) {
  formMode.value = { entity: 'retraining', id: Number(row.id), title: '修改复训记录' }
  formValues.value = pick(row, buildFormFields(formMode.value).map((field) => field.name))
}

function pick(row: Row, keys: string[]) {
  return Object.fromEntries(keys.map((key) => [key, row[key] ?? '']))
}

function closeForm() {
  formMode.value = null
  formValues.value = {}
}

async function submitForm() {
  if (!formMode.value) return
  errorMessage.value = ''
  successMessage.value = ''
  blockedItem.value = ''
  try {
    if (formMode.value.entity === 'assignments') {
      const payload = {
        team: formValues.value.team,
        assignment_no: formValues.value.assignment_no,
        work_name: formValues.value.work_name,
        scheduled_date: formValues.value.scheduled_date,
        worker_ids: String(formValues.value.worker_ids_text ?? '').split(/[,，\s]+/).filter(Boolean),
      }
      await apiAction('/api/training/assignments', { method: 'POST', body: JSON.stringify(payload) })
      successMessage.value = '资质校验通过，养护作业排单成功'
    } else {
      const entity = formMode.value.entity
      const body = { values: sanitizeValues(formValues.value) }
      const path = formMode.value.id
        ? `/api/training/${entity}/${formMode.value.id}`
        : `/api/training/${entity}`
      await apiAction(path, { method: formMode.value.id ? 'PATCH' : 'POST', body: JSON.stringify(body) })
      successMessage.value = formMode.value.id ? '记录已更新' : '记录已登记'
    }
    closeForm()
    await reload()
  } catch (error) {
    applyError(error)
  }
}

function sanitizeValues(values: Record<string, RowValue>) {
  const result: Record<string, RowValue> = {}
  Object.entries(values).forEach(([key, value]) => {
    if (value === '') result[key] = ''
    else result[key] = value
  })
  return result
}

async function verifyQualification(row: Row) {
  await simpleAction(`/api/training/qualifications/${row.id}/verify`, { values: {} }, '管理岗已核对')
}

async function leaveQualification(row: Row) {
  await simpleAction(`/api/training/qualifications/${row.id}/leave`, { values: { left_at: new Date().toISOString().slice(0, 10) } }, '离岗历史已保留')
}

async function completeRetraining(row: Row) {
  await simpleAction(`/api/training/retraining/${row.id}/complete`, { values: { completed_date: new Date().toISOString().slice(0, 10), result: '合格' } }, '复训已完成，待办已同步')
}

async function simpleAction(path: string, body: unknown, message: string) {
  errorMessage.value = ''
  successMessage.value = ''
  blockedItem.value = ''
  try {
    await apiAction(path, { method: 'POST', body: JSON.stringify(body) })
    successMessage.value = message
    await reload()
  } catch (error) {
    applyError(error)
  }
}

function applyError(error: unknown) {
  const apiError = error as ApiError
  errorMessage.value = apiError.message ?? '操作失败'
  blockedItem.value = apiError.blockedItem ?? ''
  if (apiError.blockers?.length) {
    errorMessage.value = apiError.blockers
      .map((item) => `${item.personnel_name}：卡在【${item.blocked_item}】，${item.reason}`)
      .join('；')
  }
}

watch(() => [session.userId, session.role, session.team], () => {
  if (!session.isManager) teamFilter.value = session.team
  void reload()
})

onMounted(reload)
</script>
