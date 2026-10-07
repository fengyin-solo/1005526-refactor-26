/** 统一请求封装：拼后端地址、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    headers: { 'Content-Type': 'application/json' },
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

/**
 * 统一导出入口：所有模块共用的下载通道。
 * 带上与列表查询相同的过滤参数，保证导出文件与列表读到的是同一批数据；
 * 后端按同一模块 + 同一范围落盘，重复导出只覆盖同名文件。
 */
export function openExport(endpoint: string, filters?: Record<string, string>): void {
  const query = filters ? new URLSearchParams(filters).toString() : ''
  window.open(`${endpoint}/export${query ? `?${query}` : ''}`, '_blank')
}
