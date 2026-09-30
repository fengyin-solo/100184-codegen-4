import { defineStore } from 'pinia'

export type Operator = {
  id: number
  姓名: string
  角色: '培训管理员' | '作业人员' | '管理岗位'
  所属班组: string
}

const STORAGE_KEY = 'training-operator-id'

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: null as Operator | null,
    operators: [] as Operator[],
    shiftLabel: '白班 08:00-20:00',
    scope: '城市地下管网巡检养护平台',
  }),
  getters: {
    // 兼容旧页面：有登录身份即视为可操作系统。
    canOperate: (state) => state.operator !== null,
    isTrainingAdmin: (state) => state.operator?.角色 === '培训管理员',
    isManager: (state) => state.operator?.角色 === '管理岗位',
    isWorker: (state) => state.operator?.角色 === '作业人员',
    crew: (state) => state.operator?.所属班组 ?? '',
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    async loadOperators() {
      const response = await fetch('/api/training/operators')
      if (!response.ok) return
      const payload = (await response.json()) as { items: Operator[] }
      this.operators = payload.items
      const savedId = Number(localStorage.getItem(STORAGE_KEY))
      const saved = this.operators.find((item) => item.id === savedId)
      this.operator = saved ?? this.operators[0] ?? null
    },
    switchOperator(id: number) {
      this.operator = this.operators.find((item) => item.id === id) ?? null
      if (this.operator) localStorage.setItem(STORAGE_KEY, String(this.operator.id))
    },
  },
})
