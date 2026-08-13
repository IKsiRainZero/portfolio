import type { PanelId, WorkbenchEvent } from '../types'

const BASE = '/api/workbench'

export async function startSession(): Promise<{ session_id: string }> {
  const r = await fetch(`${BASE}/start`, { method: 'POST' })
  if (!r.ok) throw new Error('引擎启动失败，请刷新页面重试。')
  return r.json()
}

export async function sendMessage(
  sessionId: string,
  text: string,
): Promise<{ events?: WorkbenchEvent[]; error?: string }> {
  const r = await fetch(`${BASE}/${sessionId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  return r.json()
}

export async function confirmPanel(
  sessionId: string,
  panelId: PanelId,
): Promise<{ events?: WorkbenchEvent[]; error?: string }> {
  const r = await fetch(`${BASE}/${sessionId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ panel_id: panelId }),
  })
  return r.json()
}

export async function revokePanel(
  sessionId: string,
  panelId: PanelId,
  reason: string,
): Promise<{ events?: WorkbenchEvent[]; error?: string }> {
  const r = await fetch(`${BASE}/${sessionId}/revoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ panel_id: panelId, reason }),
  })
  return r.json()
}
