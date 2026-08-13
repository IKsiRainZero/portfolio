import { useEffect } from 'react'
import type { WorkbenchEvent } from '../types'

export function useSSE(
  sessionId: string | null,
  onEvent: (evt: WorkbenchEvent) => void,
) {
  useEffect(() => {
    if (!sessionId) return
    const es = new EventSource(`/api/workbench/${sessionId}/events`)
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.event_type && data.event_type !== 'heartbeat') {
          onEvent(data as WorkbenchEvent)
        }
      } catch {
        /* ignore parse errors */
      }
    }
    return () => es.close()
  }, [sessionId, onEvent])
}
