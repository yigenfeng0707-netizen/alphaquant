const BASE = import.meta.env.VITE_API_BASE || ''

export function getSource() {
  return localStorage.getItem('aq_source') || 'offline'
}

export function setSource(v) {
  localStorage.setItem('aq_source', v)
}

function extractError(body, status) {
  if (!body) return `HTTP ${status}`
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail)) {
    return body.detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
  }
  if (body.error) return body.error
  return `HTTP ${status}`
}

async function parse(res) {
  let body = null
  try {
    body = await res.json()
  } catch (err) {
    throw new Error(`响应不是 JSON（HTTP ${res.status}）`)
  }
  if (!res.ok) throw new Error(extractError(body, res.status))
  if (body && body.ok === false) throw new Error(body.error || '接口返回失败')
  return body
}

export async function getJson(path) {
  const res = await fetch(`${BASE}${path}`)
  return parse(res)
}

export async function postJson(path, payload) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
  return parse(res)
}

export function withSource(path) {
  const src = getSource()
  const join = path.includes('?') ? '&' : '?'
  return `${path}${join}source=${encodeURIComponent(src)}`
}

export function pct(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

export function num(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Number(v).toFixed(digits)
}

export function money(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `¥${Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
}
