import { useMemo } from 'react'
import type { PanelId, PanelState } from '../types'

export type PageId = 'welcome' | 'discover' | 'plan' | 'act'

/**
 * Derives the current page from session state and panel confirmations.
 *
 * welcome   — no session (pre-start)
 * discover  — session active, profile + direction panels
 * plan      — direction confirmed, gap + path panels
 * act       — path confirmed, action panel
 */
export function derivePage(
  sessionId: string | null,
  panelStates: Record<PanelId, PanelState>,
): PageId {
  if (!sessionId) return 'welcome'
  if (panelStates.path === 'CONFIRMED') return 'act'
  if (panelStates.direction === 'CONFIRMED') return 'plan'
  return 'discover'
}

export function usePageNavigation(
  sessionId: string | null,
  panelStates: Record<PanelId, PanelState>,
) {
  const currentPage = useMemo(
    () => derivePage(sessionId, panelStates),
    [sessionId, panelStates],
  )
  return { currentPage }
}
