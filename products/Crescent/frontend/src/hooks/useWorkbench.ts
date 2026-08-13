import { useState, useCallback, useRef } from 'react'
import type { PanelId, PanelState, WorkbenchEvent } from '../types'
import { DEPENDENCIES, SEQUENCE } from '../types'
import * as api from '../lib/api'

export interface Message {
  type: 'system' | 'user' | 'guide'
  html: string
}

function escapeHtml(str: string): string {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

const INIT_STATES: Record<PanelId, PanelState> = {
  profile: 'EMPTY',
  direction: 'EMPTY',
  gap: 'EMPTY',
  source: 'EMPTY',
  path: 'EMPTY',
  action: 'EMPTY',
}

export function useWorkbench() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [panelStates, setPanelStates] = useState<Record<PanelId, PanelState>>({ ...INIT_STATES })
  const [panelPayloads, setPanelPayloads] = useState<Record<PanelId, Record<string, unknown>>>({
    profile: {}, direction: {}, gap: {}, source: {}, path: {}, action: {},
  })
  const [activePid, setActivePid] = useState<PanelId>('profile')
  const [processing, setProcessing] = useState(false)
  const [processingMsg, setProcessingMsg] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const confirmedCount = useRef(0)

  const addMessage = useCallback((type: Message['type'], html: string) => {
    setMessages((prev) => [...prev, { type, html }])
  }, [])

  const isStepAccessible = useCallback(
    (pid: PanelId): boolean => {
      const deps = DEPENDENCIES[pid] || []
      for (const dep of deps) {
        if (panelStates[dep] !== 'CONFIRMED') return false
      }
      return true
    },
    [panelStates],
  )

  const getNextInSequence = useCallback((pid: PanelId): PanelId | null => {
    const idx = SEQUENCE.indexOf(pid)
    if (idx === -1 || idx >= SEQUENCE.length - 1) return null
    return SEQUENCE[idx + 1]
  }, [])

  const applyEvent = useCallback(
    (evt: WorkbenchEvent) => {
      // Handle narrator messages (greetings, query responses) — no panel_id
      if (evt.event_type === 'narrator.message') {
        setProcessing(false)
        setProcessingMsg('')
        const p = evt.payload as Record<string, unknown>
        const html = (p.html as string) || ''
        const intent = p.intent as string || ''
        if (html && intent !== 'greeting') {
          addMessage('guide', html)
        } else if (html && intent === 'greeting') {
          addMessage('system', html)
        }
        return
      }

      const pid = evt.panel_id
      if (!pid) return

      if (evt.event_type === 'system.processing') {
        setProcessing(true)
        setProcessingMsg((evt.payload as Record<string, string>).message || '处理中...')
        return
      }

      setProcessing(false)
      setProcessingMsg('')

      if (evt.event_type.endsWith('.revoked')) {
        setPanelStates((prev) => ({ ...prev, [pid]: 'EMPTY' }))
        setPanelPayloads((prev) => ({ ...prev, [pid]: {} }))
        addMessage('guide', `<p><strong>${escapeHtml(pid)}</strong> 已重置。下游面板也已清空。</p>`)
      } else if (evt.event_type.endsWith('.confirmed')) {
        setPanelStates((prev) => ({ ...prev, [pid]: 'CONFIRMED' }))
        confirmedCount.current++
        addMessage('guide', `<p><strong>${escapeHtml(pid)}</strong> 已确认。</p>`)
      } else {
        const newState: PanelState =
          evt.payload && (evt.payload as Record<string, unknown>).to
            ? ((evt.payload as Record<string, unknown>).to as PanelState)
            : 'READY_FOR_REVIEW'
        setPanelStates((prev) => ({ ...prev, [pid]: newState }))
        if (evt.payload) {
          setPanelPayloads((prev) => ({ ...prev, [pid]: evt.payload as Record<string, unknown> }))
        }
        // Auto-navigate to updated panel if accessible
        if (newState === 'READY_FOR_REVIEW') {
          setActivePid((current) => {
            if (isStepAccessible(pid)) return pid
            return current
          })
        }
      }
    },
    [addMessage, isStepAccessible],
  )

  const processEvents = useCallback(
    (data: { events?: WorkbenchEvent[]; error?: string }) => {
      if (data.events) {
        data.events.forEach(applyEvent)
        // Check if any confirmed panel should auto-advance
        for (const evt of data.events) {
          if (evt.event_type.endsWith('.confirmed') && evt.panel_id) {
            const nextPid = getNextInSequence(evt.panel_id)
            if (nextPid && isStepAccessible(nextPid)) {
              // Will auto-navigate when the next panel gets READY_FOR_REVIEW
            }
          }
        }
      }
      if (data.error) {
        addMessage('system', `<p>${escapeHtml(data.error)}</p>`)
      }
    },
    [applyEvent, addMessage, getNextInSequence, isStepAccessible],
  )

  const startSession = useCallback(async () => {
    try {
      const data = await api.startSession()
      setSessionId(data.session_id)
      addMessage('system', '<p>引擎已就绪。按 <kbd>Ctrl+J</kbd> 打开对话框，描述你的技能和经历。</p>')
      setActivePid('profile')
    } catch {
      addMessage('system', '<p>引擎启动失败，请刷新页面重试。</p>')
    }
  }, [addMessage])

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || !sessionId) return
      addMessage('user', `<p>${escapeHtml(text)}</p>`)
      setProcessing(true)
      setProcessingMsg('分析中...')
      try {
        const data = await api.sendMessage(sessionId, text)
        setProcessing(false)
        setProcessingMsg('')
        processEvents(data)
      } catch {
        setProcessing(false)
        setProcessingMsg('')
        addMessage('system', '<p>请求失败，请重试。</p>')
      }
    },
    [sessionId, addMessage, processEvents],
  )

  const confirm = useCallback(
    async (pid: PanelId) => {
      if (!sessionId) return
      setProcessing(true)
      setProcessingMsg('确认中...')
      try {
        const data = await api.confirmPanel(sessionId, pid)
        setProcessing(false)
        setProcessingMsg('')
        processEvents(data)
      } catch {
        setProcessing(false)
        setProcessingMsg('')
        addMessage('system', '<p>确认失败，请重试。</p>')
      }
    },
    [sessionId, addMessage, processEvents],
  )

  const revoke = useCallback(
    async (pid: PanelId, reason?: string) => {
      if (!sessionId) return
      setProcessing(true)
      setProcessingMsg('重置中...')
      try {
        const data = await api.revokePanel(sessionId, pid, reason || '')
        setProcessing(false)
        setProcessingMsg('')
        processEvents(data)
        setActivePid(pid)
      } catch {
        setProcessing(false)
        setProcessingMsg('')
        addMessage('system', '<p>重置失败，请重试。</p>')
      }
    },
    [sessionId, addMessage, processEvents],
  )

  const navigateToStep = useCallback(
    (targetPid: PanelId) => {
      if (isStepAccessible(targetPid)) {
        setActivePid(targetPid)
      }
    },
    [isStepAccessible],
  )

  const navigateStep = useCallback(
    (direction: 1 | -1) => {
      const idx = SEQUENCE.indexOf(activePid)
      const targetIdx = idx + direction
      if (targetIdx < 0 || targetIdx >= SEQUENCE.length) return
      const targetPid = SEQUENCE[targetIdx]
      if (isStepAccessible(targetPid)) {
        setActivePid(targetPid)
      }
    },
    [activePid, isStepAccessible],
  )

  const activeIdx = SEQUENCE.indexOf(activePid)

  return {
    sessionId,
    panelStates,
    panelPayloads,
    activePid,
    activeIdx,
    processing,
    processingMsg,
    messages,
    isStepAccessible,
    startSession,
    sendMessage,
    confirm,
    revoke,
    navigateToStep,
    navigateStep,
    applyEvent,
  }
}
