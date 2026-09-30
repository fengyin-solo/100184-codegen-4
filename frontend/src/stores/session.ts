import { defineStore } from 'pinia'

export const ROLES = ['培训管理员', '管理岗', '作业人员'] as const
export type UserRole = (typeof ROLES)[number]

export const TEAMS = ['排水一班', '排水二班'] as const
export type Team = (typeof TEAMS)[number] | ''

type SessionState = {
  operator: string
  userId: string
  role: UserRole
  team: Team
  shiftLabel: string
  scope: string
}

const saved = loadSession()

function loadSession(): Partial<SessionState> {
  try {
    return JSON.parse(localStorage.getItem('training-session') ?? '{}') as Partial<SessionState>
  } catch {
    return {}
  }
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    operator: saved.operator ?? '王培训',
    userId: saved.userId ?? 'TRAIN-A1',
    role: saved.role ?? '培训管理员',
    team: saved.team ?? '排水一班',
    shiftLabel: '白班 08:00-20:00',
    scope: '城市地下管网巡检养护平台',
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    isManager: (state) => state.role === '管理岗',
    isTrainingAdmin: (state) => state.role === '培训管理员',
    authHeaders: (state) => ({
      'X-User-Id': state.userId,
      'X-User-Name': state.operator,
      'X-User-Role': state.role,
      'X-User-Team': state.team,
    }),
  },
  actions: {
    setSession(payload: { operator: string; userId: string; role: UserRole; team: Team }) {
      this.operator = payload.operator
      this.userId = payload.userId
      this.role = payload.role
      this.team = payload.role === '管理岗' ? '' : payload.team
      localStorage.setItem('training-session', JSON.stringify({
        operator: this.operator,
        userId: this.userId,
        role: this.role,
        team: this.team,
      }))
    },
    setShift(label: string) {
      this.shiftLabel = label
    },
  },
})
