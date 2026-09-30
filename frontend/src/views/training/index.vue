<template>
  <section class="page" data-module="training">
    <header class="page-head">
      <div>
        <h2>养护人员资质培训台账</h2>
        <p class="page-desc">
          按作业人员登记培训计划与复训记录；本班组培训管理员才能改动本班组记录，
          跨班组改动只读拦截，管理岗位可核对全部班组。资质过期或被暂停的人员不允许排进养护作业。
        </p>
      </div>
      <div class="page-actions">
        <button v-if="store.isTrainingAdmin" class="btn primary" type="button" @click="openPlan">登记培训计划</button>
        <span class="scope-tag">{{ scopeText }}</span>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="role-banner info">{{ identityHint }}</div>
    <div v-if="errorMessage" class="role-banner error" style="white-space: pre-line">{{ errorMessage }}</div>
    <div v-if="successMessage" class="role-banner ok">{{ successMessage }}</div>

    <nav class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- ============ 台账 ============ -->
    <template v-if="activeTab === 'ledger'">
      <form class="filter-bar" @submit.prevent="reload">
        <label class="filter-item">
          <span>人员/资质/证书</span>
          <input v-model="filters.keyword" placeholder="按姓名、资质名称、证书编号检索" />
        </label>
        <label v-if="store.isManager" class="filter-item">
          <span>所属班组</span>
          <select v-model="filters.crew">
            <option value="">全部班组</option>
            <option v-for="crew in crews" :key="crew" :value="crew">{{ crew }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>资质状态</span>
          <select v-model="filters.qualification">
            <option value="">全部</option>
            <option value="有效">有效</option>
            <option value="已过期">已过期</option>
            <option value="暂停">暂停</option>
          </select>
        </label>
        <label class="check-item">
          <input v-model="filters.onlyDue" type="checkbox" @change="reload" /> 只看待复训
        </label>
        <label class="check-item">
          <input v-model="filters.includeLeft" type="checkbox" @change="reload" /> 含离岗人员历史
        </label>
        <button class="btn" type="submit">查询</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th>所属班组</th>
            <th>作业人员</th>
            <th>在岗状态</th>
            <th>资质名称</th>
            <th>证书编号</th>
            <th>初训有效期至</th>
            <th>下次复训日</th>
            <th>资质状态</th>
            <th>复训提醒</th>
            <th>核对状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row.所属班组 }}</td>
            <td>{{ row.人员姓名 }}</td>
            <td>{{ row.在岗状态 }}</td>
            <td>{{ row.资质名称 }}</td>
            <td>{{ row.证书编号 || '—' }}</td>
            <td>{{ row.初训有效期至 }}</td>
            <td>{{ row.下次复训日 }}</td>
            <td>
              <span class="badge" :class="statusClass(row.资质状态)">{{ row.资质状态 }}</span>
              <div v-if="row.资质状态 === '暂停' && row.暂停原因" class="cell-sub">{{ row.暂停原因 }}</div>
            </td>
            <td>
              <span v-if="row.待复训" class="badge" :class="row.提醒级别 === '已逾期' ? 'danger' : 'warn'">
                {{ row.提醒级别 }}（{{ row.到期天数 < 0 ? `逾期${-row.到期天数}天` : `剩${row.到期天数}天` }}）
              </span>
              <span v-else class="muted">—</span>
            </td>
            <td>{{ row.核对状态 }}<span v-if="row.核对人" class="cell-sub">核对人：{{ row.核对人 }}</span></td>
            <td class="row-actions">
              <button class="link" type="button" @click="openHistory(row)">复训历史</button>
              <template v-if="canEdit(row)">
                <button class="link" type="button" @click="openRetrain(row)">登记复训</button>
                <button v-if="!row.暂停" class="link danger-link" type="button" @click="openSuspend(row)">暂停</button>
                <button v-else class="link" type="button" @click="resumeEntry(row)">恢复</button>
                <button v-if="row.在岗状态 !== '已离岗'" class="link danger-link" type="button" @click="openLeave(row)">离岗</button>
              </template>
              <button v-else-if="store.isManager" class="link" type="button" @click="verifyEntry(row)">
                {{ row.核对状态 === '已核对' ? '重新核对' : '核对' }}
              </button>
              <span v-else-if="store.isWorker" class="muted">只读</span>
              <span v-else class="muted" title="只能维护本班组归属的记录">跨班组只读</span>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="11" class="empty-state">暂无符合条件的培训台账记录</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot"><span>共 {{ total }} 条台账记录</span></footer>
    </template>

    <!-- ============ 复训历史 ============ -->
    <template v-else-if="activeTab === 'history'">
      <p class="block-desc">复训记录按台账归并展示；人员离岗后其历史复训记录继续保留，不删除。</p>
      <div v-for="entry in historyEntries" :key="entry.id" class="history-card">
        <header class="history-head">
          <strong>{{ entry.人员姓名 }}</strong>（{{ entry.所属班组 }}） · {{ entry.资质名称 }}
          <span class="muted">证书 {{ entry.证书编号 || '—' }}</span>
          <span class="badge" :class="statusClass(entry.资质状态)">{{ entry.资质状态 }}</span>
        </header>
        <table v-if="entry.历史复训?.length" class="data-table inner">
          <thead>
            <tr><th>复训日期</th><th>培训内容</th><th>学时</th><th>考核结果</th><th>复训有效期至</th><th>下次复训日</th><th>登记人</th></tr>
          </thead>
          <tbody>
            <tr v-for="(rec, idx) in entry.历史复训" :key="idx">
              <td>{{ rec.复训日期 }}</td>
              <td>{{ rec.培训内容 }}</td>
              <td>{{ rec.学时 }}</td>
              <td :class="rec.考核结果 === '不合格' ? 'error-text' : ''">{{ rec.考核结果 }}</td>
              <td>{{ rec.复训有效期至 }}</td>
              <td>{{ rec.下次复训日 }}</td>
              <td>{{ rec.登记人 }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="muted empty-inline">暂无复训记录（仅完成初训）</div>
      </div>
    </template>

    <!-- ============ 排班 ============ -->
    <template v-else>
      <p class="block-desc">提交养护作业排班时按人逐项校验资质：过期、暂停、离岗或无资质登记的人员会被整体拦下并说明卡点。</p>
      <form class="assign-form" @submit.prevent="submitAssignment">
        <label class="filter-item">
          <span>作业名称</span>
          <input v-model="assignment.作业名称" placeholder="如：国庆前管网巡检" />
        </label>
        <label class="filter-item">
          <span>作业日期</span>
          <input v-model="assignment.作业日期" type="date" />
        </label>
        <fieldset class="staff-pick">
          <legend>选择作业人员</legend>
          <div v-for="crew in crews" :key="crew" class="staff-group">
            <span class="staff-crew">{{ crew }}</span>
            <label v-for="person in staffByCrew[crew] ?? []" :key="person.id" class="staff-option">
              <input v-model="assignment.personIds" type="checkbox" :value="person.id" />
              {{ person.姓名 }}（{{ person.工种 }}）
              <span v-if="person.在岗状态 === '已离岗'" class="error-text">已离岗</span>
            </label>
          </div>
        </fieldset>
        <div class="form-actions">
          <button class="btn" type="button" @click="precheckAssignment">资质预检</button>
          <button class="btn primary" type="submit">提交排班</button>
        </div>
      </form>

      <div v-if="precheck" class="role-banner" :class="precheck.ok ? 'ok' : 'error'">
        <template v-if="precheck.ok">预检通过：{{ precheck.passed.map((p: any) => p.姓名).join('、') }} 可排班。</template>
        <template v-else>
          <div>预检未通过，以下卡点会导致排班被整体拒绝：</div>
          <div v-for="(item, idx) in precheck.blocked" :key="idx">· {{ item.项 }}（{{ item.提交值 }}）：{{ item.原因 }}</div>
        </template>
      </div>

      <h3 class="block-title">已生成排班</h3>
      <table class="data-table">
        <thead>
          <tr><th>作业名称</th><th>作业日期</th><th>涉及班组</th><th>人员与资质</th><th>排单人</th><th>状态</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in assignments" :key="item.id">
            <td>{{ item.作业名称 }}</td>
            <td>{{ item.作业日期 }}</td>
            <td>{{ item.班组 }}</td>
            <td>
              <div v-for="p in item.人员" :key="p.人员id">
                {{ p.姓名 }} · {{ p.资质名称 }}（有效期至 {{ p.有效期至 }}）
                <span v-if="p.提醒" class="cell-sub warn-text">⚠ {{ p.提醒 }}</span>
              </div>
            </td>
            <td>{{ item.排单人 }}</td>
            <td>{{ item.状态 }}</td>
          </tr>
          <tr v-if="!assignments.length"><td colspan="6" class="empty-state">暂未生成排班</td></tr>
        </tbody>
      </table>
    </template>

    <!-- ============ 弹窗：培训计划 / 复训 / 暂停 / 离岗 / 历史 ============ -->
    <div v-if="modal" class="modal-mask" @click.self="modal = null">
      <div class="modal">
        <header class="modal-head">
          <h3>{{ modal.title }}</h3>
          <button class="link" type="button" @click="modal = null">关闭</button>
        </header>

        <template v-if="modal.type === 'plan'">
          <div class="form-grid">
            <label class="filter-item"><span>作业人员（本班组在岗）</span>
              <select v-model="planForm.人员id">
                <option value="" disabled>请选择</option>
                <option v-for="p in ownActiveStaff" :key="p.id" :value="p.id">{{ p.姓名 }}（{{ p.工种 }}）</option>
              </select>
            </label>
            <label class="filter-item"><span>资质名称</span><input v-model="planForm.资质名称" /></label>
            <label class="filter-item"><span>证书编号</span><input v-model="planForm.证书编号" /></label>
            <label class="filter-item"><span>初训日期</span><input v-model="planForm.初训日期" type="date" /></label>
            <label class="filter-item"><span>初训有效期至</span><input v-model="planForm.初训有效期至" type="date" /></label>
            <label class="filter-item"><span>计划复训日</span><input v-model="planForm.计划复训日" type="date" /></label>
          </div>
          <p class="muted form-note">所属班组固定为「{{ store.crew }}」；选别的班组的人员或归属班组会被服务端逐项拦下。</p>
        </template>

        <template v-else-if="modal.type === 'retrain'">
          <div class="form-grid">
            <label class="filter-item"><span>复训日期</span><input v-model="retrainForm.复训日期" type="date" /></label>
            <label class="filter-item"><span>培训内容</span><input v-model="retrainForm.培训内容" /></label>
            <label class="filter-item"><span>学时</span><input v-model="retrainForm.学时" type="number" min="1" /></label>
            <label class="filter-item"><span>考核结果</span>
              <select v-model="retrainForm.考核结果"><option value="合格">合格</option><option value="不合格">不合格</option></select>
            </label>
            <label class="filter-item"><span>复训有效期至</span><input v-model="retrainForm.复训有效期至" type="date" /></label>
            <label class="filter-item"><span>下次复训日</span><input v-model="retrainForm.下次复训日" type="date" /></label>
          </div>
          <p class="muted form-note">考核合格将按「复训有效期至」续期并关闭该人员的到期提醒；不合格仅留痕，不解除排班拦截。</p>
        </template>

        <template v-else-if="modal.type === 'suspend'">
          <label class="filter-item block-field">
            <span>暂停原因（暂停期间该人员不能排进养护作业）</span>
            <textarea v-model="suspendReason" rows="3"></textarea>
          </label>
        </template>

        <template v-else-if="modal.type === 'leave'">
          <label class="filter-item block-field">
            <span>离岗日期</span>
            <input v-model="leaveDate" type="date" />
          </label>
          <p class="muted form-note">离岗后人员档案、培训计划与全部复训历史继续保留，仅关闭其复训到期待办。</p>
        </template>

        <template v-else-if="modal.type === 'history'">
          <div class="history-head">{{ modal?.entry?.人员姓名 }} · {{ modal?.entry?.资质名称 }}</div>
          <table class="data-table inner">
            <thead><tr><th>复训日期</th><th>培训内容</th><th>学时</th><th>考核结果</th><th>登记人</th></tr></thead>
            <tbody>
              <tr v-for="(rec, idx) in modal?.entry?.历史复训 ?? []" :key="idx">
                <td>{{ rec.复训日期 }}</td><td>{{ rec.培训内容 }}</td><td>{{ rec.学时 }}</td>
                <td :class="rec.考核结果 === '不合格' ? 'error-text' : ''">{{ rec.考核结果 }}</td><td>{{ rec.登记人 }}</td>
              </tr>
              <tr v-if="!(modal?.entry?.历史复训?.length)"><td colspan="5" class="empty-state">暂无复训记录</td></tr>
            </tbody>
          </table>
        </template>

        <footer v-if="modal.type !== 'history'" class="modal-foot">
          <button class="btn" type="button" @click="modal = null">取消</button>
          <button class="btn primary" type="button" @click="submitModal">提交</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { request, explainError } from '@/api/client'

type Row = Record<string, any>

const store = useSessionStore()
const route = useRoute()
const crews = ['管网养护一班', '管网养护二班']

const activeTab = ref<'ledger' | 'history' | 'assign'>('ledger')
const tabs = [
  { key: 'ledger', label: '资质培训台账' },
  { key: 'history', label: '复训记录' },
  { key: 'assign', label: '养护作业排班' },
] as const

const rows = ref<Row[]>([])
const total = ref(0)
const staff = ref<Row[]>([])
const assignments = ref<Row[]>([])
const errorMessage = ref('')
const successMessage = ref('')

const filters = reactive({ keyword: '', crew: '', qualification: '', onlyDue: false, includeLeft: true })
const stats = ref<Record<string, number>>({})

const modal = ref<null | { type: string; title: string; entry?: Row }>(null)
const planForm = reactive({ 人员id: '' as number | '', 资质名称: '', 证书编号: '', 初训日期: '', 初训有效期至: '', 计划复训日: '' })
const retrainForm = reactive({ 复训日期: '', 培训内容: '', 学时: 8, 考核结果: '合格', 复训有效期至: '', 下次复训日: '' })
const suspendReason = ref('')
const leaveDate = ref('')

const assignment = reactive<{ 作业名称: string; 作业日期: string; personIds: number[] }>({
  作业名称: '', 作业日期: '', personIds: [],
})
const precheck = ref<null | { ok: boolean; passed: any[]; blocked: any[] }>(null)

const statCards = computed(() => [
  { label: '台账总数', value: stats.value.台账总数 ?? 0 },
  { label: '资质有效', value: stats.value.资质有效 ?? 0 },
  { label: '资质过期', value: stats.value.资质过期 ?? 0 },
  { label: '资质暂停', value: stats.value.资质暂停 ?? 0 },
  { label: '待复训（=工作台待办）', value: stats.value.待复训 ?? 0 },
  { label: '离岗人员历史保留', value: stats.value.离岗人员历史 ?? 0 },
])

const scopeText = computed(() => {
  const op = store.operator
  if (!op) return ''
  if (op.角色 === '管理岗位') return '管理岗位：全部班组只读 + 核对'
  return `${op.角色} · ${op.所属班组}`
})

const identityHint = computed(() => {
  const op = store.operator
  if (!op) return '未识别到操作身份，所有提交将被拒绝。'
  if (op.角色 === '作业人员') return `作业人员身份（${op.所属班组}）：可浏览全部班组台账，但任何改动提交都会按越权直接拒绝。`
  if (op.角色 === '管理岗位') return '管理岗位身份：可查看、核对全部班组台账，但不能登记/修改培训计划与复训记录（提交会被拒绝）。'
  return `培训管理员身份（${op.所属班组}）：只能改动本班组归属的培训与复训记录；其他班组记录仅可查看，页面上不提供改动入口，直接调接口也会被服务端逐项拦下。`
})

const ownActiveStaff = computed(() =>
  staff.value.filter((p) => p.所属班组 === store.crew && p.在岗状态 === '在岗'),
)
const staffByCrew = computed<Record<string, Row[]>>(() =>
  Object.fromEntries(crews.map((crew) => [crew, staff.value.filter((p) => p.所属班组 === crew)])),
)
const historyEntries = computed(() => {
  const list = rows.value.slice()
  if (!list.length) return []
  return list
})

watch(() => store.operator?.id, () => { void reloadAll() })

onMounted(async () => {
  if (route.query.onlyDue === '1') {
    filters.onlyDue = true
    activeTab.value = 'ledger'
  }
  await reloadAll()
})

function canEdit(row: Row): boolean {
  return store.isTrainingAdmin && row.所属班组 === store.crew
}

function statusClass(status: string): string {
  if (status === '有效') return 'ok'
  if (status === '已过期') return 'danger'
  return 'warn'
}

function flashOk(message: string) {
  successMessage.value = message
  window.setTimeout(() => { successMessage.value = '' }, 4000)
}

async function callApi(path: string, body: unknown, okText: string) {
  errorMessage.value = ''
  const response = await request(path, { method: 'POST', body: JSON.stringify(body) })
  if (!response.ok) {
    errorMessage.value = await explainError(response, '提交被拒绝')
    return null
  }
  const payload = await response.json()
  flashOk(payload.message ?? okText)
  return payload
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.keyword) query.set('keyword', filters.keyword)
  if (store.isManager && filters.crew) query.set('crew', filters.crew)
  if (filters.qualification) query.set('qualification', filters.qualification)
  if (filters.onlyDue) query.set('onlyDue', 'true')
  if (!filters.includeLeft) query.set('include_left', 'false')
  query.set('size', '200')
  try {
    const response = await request(`/api/training/entries?${query.toString()}`)
    if (!response.ok) {
      errorMessage.value = await explainError(response, '台账加载失败')
      return
    }
    const payload = await response.json()
    rows.value = payload.items
    total.value = payload.total

    const statQuery = new URLSearchParams()
    if (store.isManager && filters.crew) statQuery.set('crew', filters.crew)
    const statResp = await request(`/api/training/entries/stats?${statQuery.toString()}`)
    if (statResp.ok) stats.value = await statResp.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '台账加载失败'
  }
}

async function reloadStaff() {
  const response = await request('/api/training/staff')
  if (response.ok) staff.value = (await response.json()).items
}

async function reloadAssignments() {
  const response = await request('/api/training/assignments')
  if (response.ok) assignments.value = (await response.json()).items
}

async function reloadAll() {
  await Promise.all([reload(), reloadStaff(), reloadAssignments()])
}

// ---------- 弹窗动作 ----------

function openPlan() {
  Object.assign(planForm, { 人员id: '', 资质名称: '', 证书编号: '', 初训日期: '', 初训有效期至: '', 计划复训日: '' })
  modal.value = { type: 'plan', title: `登记培训计划（${store.crew}）` }
}

function openRetrain(entry: Row) {
  Object.assign(retrainForm, { 复训日期: '', 培训内容: '', 学时: 8, 考核结果: '合格', 复训有效期至: '', 下次复训日: '' })
  modal.value = { type: 'retrain', title: `登记复训记录 · ${entry.人员姓名} · ${entry.资质名称}`, entry }
}

function openSuspend(entry: Row) {
  suspendReason.value = ''
  modal.value = { type: 'suspend', title: `暂停资质 · ${entry.人员姓名} · ${entry.资质名称}`, entry }
}

function openLeave(entry: Row) {
  leaveDate.value = new Date().toISOString().slice(0, 10)
  modal.value = { type: 'leave', title: `人员离岗 · ${entry.人员姓名}`, entry }
}

function openHistory(entry: Row) {
  modal.value = { type: 'history', title: '复训历史', entry }
}

async function submitModal() {
  if (!modal.value) return
  const entry = modal.value.entry
  let path: string
  let body: { values: Record<string, unknown> }

  if (modal.value.type === 'plan') {
    path = '/api/training/entries'
    body = {
      values: {
        人员id: planForm.人员id,
        所属班组: store.crew,
        资质名称: planForm.资质名称,
        证书编号: planForm.证书编号,
        初训日期: planForm.初训日期,
        初训有效期至: planForm.初训有效期至,
        计划复训日: planForm.计划复训日,
      },
    }
  } else if (modal.value.type === 'retrain' && entry) {
    path = `/api/training/entries/${entry.id}/retrain`
    body = { values: { ...retrainForm } }
  } else if (modal.value.type === 'suspend' && entry) {
    path = `/api/training/entries/${entry.id}/suspend`
    body = { values: { 暂停原因: suspendReason.value } }
  } else if (modal.value.type === 'leave' && entry) {
    path = `/api/training/staff/${entry.人员id}/leave`
    body = { values: { 离岗日期: leaveDate.value } }
  } else {
    return
  }

  const payload = await callApi(path, body, '提交成功')
  if (payload) {
    modal.value = null
    await reloadAll()
  }
}

async function resumeEntry(row: Row) {
  const payload = await callApi(`/api/training/entries/${row.id}/resume`, { values: {} }, '资质已恢复')
  if (payload) await reloadAll()
}

async function verifyEntry(row: Row) {
  const payload = await callApi(`/api/training/entries/${row.id}/verify`, { values: {} }, '台账已核对')
  if (payload) await reload()
}

// ---------- 排班 ----------

async function precheckAssignment() {
  errorMessage.value = ''
  const response = await request('/api/training/assignments/check', {
    method: 'POST',
    body: JSON.stringify({ values: { 人员ids: assignment.personIds } }),
  })
  if (!response.ok) {
    errorMessage.value = await explainError(response, '资质预检失败')
    return
  }
  precheck.value = await response.json()
}

async function submitAssignment() {
  precheck.value = null
  const payload = await callApi('/api/training/assignments', {
    values: { 作业名称: assignment.作业名称, 作业日期: assignment.作业日期, 人员ids: assignment.personIds },
  }, '排班已生成')
  if (payload) {
    assignment.作业名称 = ''
    assignment.作业日期 = ''
    assignment.personIds = []
    await reloadAssignments()
  }
}
</script>

<style scoped>
.scope-tag { color: var(--muted); font-size: 13px; }
.role-banner { border-radius: 6px; padding: 8px 12px; font-size: 13px; margin-bottom: 12px; }
.role-banner.info { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
.role-banner.error { background: #fef2f2; border: 1px solid #fecaca; color: #b42318; }
.role-banner.ok { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
.tabs { display: flex; gap: 4px; margin: 8px 0 12px; }
.tab { border: 1px solid var(--border); background: #fff; border-bottom: none; padding: 6px 16px; border-radius: 6px 6px 0 0; cursor: pointer; font-size: 13px; }
.tab.active { background: var(--brand); color: #fff; border-color: var(--brand); }
.badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; }
.badge.ok { background: #dcfce7; color: #166534; }
.badge.danger { background: #fee2e2; color: #b42318; }
.badge.warn { background: #fef3c7; color: #92400e; }
.muted { color: var(--muted); font-size: 12px; }
.cell-sub { display: block; color: var(--muted); font-size: 12px; margin-top: 2px; max-width: 220px; }
.warn-text { color: #92400e; }
.danger-link { color: #b42318; }
.check-item { font-size: 13px; display: flex; align-items: center; gap: 4px; }
.block-title { font-size: 15px; margin: 16px 0 8px; }
.block-desc { color: var(--muted); font-size: 13px; }
.history-card { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; }
.history-head { font-size: 13px; margin-bottom: 8px; display: flex; gap: 8px; align-items: center; }
.data-table.inner { margin-top: 6px; }
.empty-inline { padding: 8px 0; }
.assign-form { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.staff-pick { border: 1px dashed var(--border); border-radius: 6px; padding: 8px 12px; }
.staff-group { display: flex; flex-wrap: wrap; gap: 12px; padding: 4px 0; align-items: center; }
.staff-crew { font-size: 12px; color: var(--muted); min-width: 96px; }
.staff-option { font-size: 13px; display: flex; gap: 4px; align-items: center; }
.form-actions { display: flex; gap: 8px; }
.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 20; }
.modal { background: #fff; border-radius: 8px; width: 720px; max-width: 92vw; max-height: 86vh; overflow: auto; padding: 16px 18px; }
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.modal-head h3 { margin: 0; font-size: 16px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; }
.block-field { display: block; margin-bottom: 8px; }
.block-field span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.block-field textarea, .block-field input { width: 100%; }
.form-note { font-size: 12px; margin-top: 8px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; border-top: 1px solid var(--border); padding-top: 12px; }
select.filter-control, .filter-item input, .filter-item select, textarea { border: 1px solid var(--border); border-radius: 6px; padding: 5px 8px; font-size: 13px; }
</style>
