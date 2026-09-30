/** 统一请求封装：拼后端地址、带操作人员身份头、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const OPERATOR_STORAGE_KEY = 'training-operator-id'

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const operatorId = localStorage.getItem(OPERATOR_STORAGE_KEY) ?? ''
  return fetch(url, {
    headers: { 'Content-Type': 'application/json', 'X-Operator-Id': operatorId, ...(init?.headers ?? {}) },
    ...init,
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}

/** 解析后端业务卡控 / 越权拒绝返回的结构化说明。 */
export async function explainError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as {
      detail?: { message?: string; 卡控项?: { 项: string; 提交值: unknown; 原因: string }[] } | string
    }
    const detail = body.detail
    if (typeof detail === 'object' && detail !== null) {
      const lines = detail.卡控项?.map((item) => `· ${item.项}：${item.原因}`) ?? []
      return [detail.message ?? fallback, ...lines].join('\n')
    }
    if (typeof detail === 'string') return detail
  } catch {
    /* 非 JSON 错误体时走兜底文案 */
  }
  return fallback
}
