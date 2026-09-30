<template>
  <section class="page" data-module="workbench">
    <header class="page-head">
      <div>
        <h2>班组工作台</h2>
        <p class="page-desc">
          复训到期提醒统一汇入本班组待办；待办口径与资质培训台账「待复训」完全一致，
          下方一致性标记可直接核对。
        </p>
      </div>
      <div class="page-actions">
        <select v-if="store.isManager" v-model="crewFilter" class="filter-control" @change="reload">
          <option value="">全部班组</option>
          <option v-for="crew in crews" :key="crew" :value="crew">{{ crew }}</option>
        </select>
        <span v-else class="scope-tag">本班组：{{ store.crew }}</span>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">工作台待办（复训到期）</span>
        <strong class="stat-value">{{ todos.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">培训台账「待复训」条数</span>
        <strong class="stat-value">{{ ledgerDue }}</strong>
      </article>
      <article class="stat-card" :class="{ matched: matched }">
        <span class="stat-label">口径一致性</span>
        <strong class="stat-value">{{ matched ? '✓ 一致' : '✗ 不一致' }}</strong>
      </article>
    </div>

    <div v-if="identityHint" class="role-banner info">{{ identityHint }}</div>
    <div v-if="errorMessage" class="role-banner error" style="white-space: pre-line">{{ errorMessage }}</div>

    <h3 class="block-title">复训到期待办</h3>
    <table class="data-table">
      <thead>
        <tr>
          <th>提醒级别</th>
          <th>所属班组</th>
          <th>作业人员</th>
          <th>资质名称</th>
          <th>下次复训日</th>
          <th>距今天数</th>
          <th>跳转</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in todos" :key="row.id">
          <td>
            <span class="badge" :class="row.提醒级别 === '已逾期' ? 'danger' : 'warn'">{{ row.提醒级别 }}</span>
          </td>
          <td>{{ row.所属班组 }}</td>
          <td>{{ row.人员姓名 }}</td>
          <td>{{ row.资质名称 }}</td>
          <td>{{ row.下次复训日 }}</td>
          <td :class="row.到期天数 < 0 ? 'error-text' : ''">
            {{ row.到期天数 < 0 ? `已逾期 ${-row.到期天数} 天` : `剩 ${row.到期天数} 天` }}
          </td>
          <td><RouterLink class="link" to="/training?onlyDue=1">去培训台账处理</RouterLink></td>
        </tr>
        <tr v-if="!todos.length">
          <td colspan="7" class="empty-state">暂无复训到期待办</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>待办 {{ todos.length }} 条 ＝ 台账待复训 {{ ledgerDue }} 条（同一数据源实时计算）</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useSessionStore } from '@/stores/session'
import { request, explainError } from '@/api/client'

type Todo = {
  id: number
  提醒级别: string
  所属班组: string
  人员姓名: string
  资质名称: string
  下次复训日: string
  到期天数: number
}

type Workbench = {
  班组: string
  待办: Todo[]
  待办条数: number
  台账待复训条数: number
  条数一致: boolean
}

const store = useSessionStore()
const todos = ref<Todo[]>([])
const ledgerDue = ref(0)
const matched = ref(false)
const crewFilter = ref('')
const errorMessage = ref('')
const crews = ['管网养护一班', '管网养护二班']

const identityHint = computed(() => {
  const op = store.operator
  if (!op) return ''
  if (op.角色 === '作业人员') return `当前为作业人员身份（${op.所属班组}）：只能查看本班组待办，不能改动培训台账。`
  if (op.角色 === '管理岗位') return '当前为管理岗位身份：可核对全部班组台账，待办可切换班组查看；培训/复训内容的改动由各班组培训管理员负责。'
  return `当前为培训管理员身份（${op.所属班组}）：只能处理本班组的资质培训与复训记录，跨班组改动会被拦截。`
})

watch(() => store.operator?.id, () => void reload())

onMounted(reload)

async function reload() {
  errorMessage.value = ''
  try {
    const query = new URLSearchParams()
    if (store.isManager && crewFilter.value) query.set('crew', crewFilter.value)
    const response = await request(`/api/training/workbench?${query.toString()}`)
    if (!response.ok) {
      errorMessage.value = await explainError(response, '工作台加载失败')
      return
    }
    const payload = (await response.json()) as Workbench
    todos.value = payload.待办
    ledgerDue.value = payload.台账待复训条数
    matched.value = payload.条数一致
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '工作台加载失败'
  }
}
</script>

<style scoped>
.page-actions { display: flex; gap: 8px; align-items: center; }
.filter-control { border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; }
.scope-tag { color: var(--muted); font-size: 13px; }
.stat-card.matched { border-color: #16a34a; }
.stat-card.matched .stat-value { color: #16a34a; }
.role-banner { border-radius: 6px; padding: 8px 12px; font-size: 13px; margin-bottom: 12px; }
.role-banner.info { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
.role-banner.error { background: #fef2f2; border: 1px solid #fecaca; color: #b42318; }
.block-title { font-size: 15px; margin: 16px 0 8px; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; }
.badge.danger { background: #fee2e2; color: #b42318; }
.badge.warn { background: #fef3c7; color: #92400e; }
</style>
