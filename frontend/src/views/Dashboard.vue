<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>

    <section class="workbench-card">
      <div>
        <span class="stat-label">班组工作台 · 复训到期待办（{{ workbench.team }}）</span>
        <strong class="workbench-total">{{ workbench.total }}</strong>
        <span class="page-desc">待办直接读取培训台账复训记录，逾期 {{ workbench.overdue }} 条、30 天内到期 {{ workbench.due_soon }} 条。</span>
      </div>
      <RouterLink class="btn" to="/training">打开资质培训台账</RouterLink>
    </section>

    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { fetchJson } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

type Workbench = {
  team: string
  total: number
  overdue: number
  due_soon: number
  items: unknown[]
}

const session = useSessionStore()
const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const workbench = ref<Workbench>({ team: session.team || '全部班组', total: 0, overdue: 0, due_soon: 0, items: [] })

async function loadOverview() {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = []
    moduleRows.value = []
  }
}

async function loadWorkbench() {
  try {
    workbench.value = await fetchJson<Workbench>('/api/training/workbench', {
      headers: session.authHeaders,
    })
  } catch {
    workbench.value = { team: session.team || '全部班组', total: 0, overdue: 0, due_soon: 0, items: [] }
  }
}

onMounted(() => {
  void loadOverview()
  void loadWorkbench()
})

watch(() => [session.userId, session.role, session.team], () => {
  void loadWorkbench()
})
</script>
