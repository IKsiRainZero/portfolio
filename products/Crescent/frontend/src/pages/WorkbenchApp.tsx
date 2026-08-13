import { useCallback, useEffect, useRef, useState } from 'react'
import { useWorkbench } from '../hooks/useWorkbench'
import { useSSE } from '../hooks/useSSE'
import { usePageNavigation } from '../hooks/usePageNavigation'
import AmbientLight from '../components/AmbientLight'
import FlowField from '../components/FlowField'
import Spotlight from '../components/Spotlight'
import PageRouter from '../components/PageRouter'
import FloatingInput from '../components/FloatingInput'
import ResponseSheet from '../components/ResponseSheet'

export default function WorkbenchApp() {
  const wb = useWorkbench()
  const { currentPage } = usePageNavigation(wb.sessionId, wb.panelStates)
  const pendingText = useRef<string | null>(null)
  const [forceWelcome, setForceWelcome] = useState(false)
  const [autoOpenInput, setAutoOpenInput] = useState(false)

  const effectivePage = forceWelcome ? 'welcome' : currentPage

  // SSE
  const handleSSEEvent = useCallback(
    (evt: Parameters<typeof wb.applyEvent>[0]) => wb.applyEvent(evt),
    [wb.applyEvent],
  )
  useSSE(wb.sessionId, handleSSEEvent)

  // Sequence: if user sends message before session exists, start session first
  useEffect(() => {
    if (wb.sessionId && pendingText.current) {
      wb.sendMessage(pendingText.current)
      pendingText.current = null
    }
  }, [wb.sessionId, wb.sendMessage])

  const handleSend = useCallback(
    (text: string) => {
      if (!wb.sessionId) {
        pendingText.current = text
        wb.startSession()
      } else {
        wb.sendMessage(text)
      }
    },
    [wb.sessionId, wb.startSession, wb.sendMessage],
  )

  // Response sheets from messages
  const [sheetIds, setSheetIds] = useState<Set<string>>(new Set())
  const [dismissedIds, setDismissedIds] = useState<string[]>([])
  const seenCount = useRef(0)

  useEffect(() => {
    const newMsgs = wb.messages.slice(seenCount.current)
    if (newMsgs.length > 0) {
      seenCount.current = wb.messages.length
      setSheetIds((prev) => {
        const next = new Set(prev)
        newMsgs.forEach((_, i) => next.add(`${wb.messages.length - newMsgs.length + i}`))
        return next
      })
    }
  }, [wb.messages])

  const closeSheet = useCallback((id: string) => {
    setSheetIds((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
    setDismissedIds((prev) => [...prev, id])
  }, [])

  const restoreLastDismissed = useCallback(() => {
    setDismissedIds((prev) => {
      if (prev.length === 0) return prev
      const last = prev[prev.length - 1]
      setSheetIds((s) => new Set([...s, last]))
      return prev.slice(0, -1)
    })
  }, [])

  return (
    <>
      <AmbientLight />
      <FlowField />
      <Spotlight />

      <PageRouter
        currentPage={effectivePage}
        processing={wb.processing}
        hasSession={!!wb.sessionId}
        panelStates={wb.panelStates}
        panelPayloads={wb.panelPayloads}
        onStart={() => {
          pendingText.current = null
          setForceWelcome(false)
          setAutoOpenInput(true)
          wb.startSession()
        }}
        onConfirm={(pid: string) => { wb.confirm(pid as Parameters<typeof wb.confirm>[0]) }}
        onBackToWelcome={effectivePage !== 'welcome' ? () => setForceWelcome(true) : undefined}
      />

      <FloatingInput
        processing={wb.processing}
        processingMsg={wb.processingMsg}
        hasSession={!!wb.sessionId}
        autoOpen={autoOpenInput}
        onAutoOpenDone={() => setAutoOpenInput(false)}
        dismissedCount={dismissedIds.length}
        onRestoreDismissed={restoreLastDismissed}
        onSend={handleSend}
      />

      {Array.from(sheetIds).map((id) => {
        const idx = parseInt(id, 10)
        const msg = wb.messages[idx]
        if (!msg || msg.type === 'user') return null
        return (
          <ResponseSheet
            key={id}
            id={id}
            html={msg.html}
            type={msg.type}
            onClose={closeSheet}
          />
        )
      })}
    </>
  )
}
