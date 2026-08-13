import type { Project, WorkspaceSummary, TraceRecord, ClaudeSession } from '../types';

const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const api = {
  getWorkspaceSummary: () => get<WorkspaceSummary>('/workspace/summary'),
  getProjects: () => get<Project[]>('/projects'),
  getProject: (name: string) => get<Project>(`/projects/${encodeURIComponent(name)}`),
  getClaudeSessions: (limit?: number) => get<{ sessions: ClaudeSession[] }>(`/claude-sessions${limit ? `?limit=${limit}` : ''}`),
  getTraces: (params?: { project?: string; type?: string; from?: string; to?: string }) => {
    const qs = new URLSearchParams();
    if (params?.project) qs.set('project', params.project);
    if (params?.type) qs.set('type', params.type);
    if (params?.from) qs.set('from', params.from);
    if (params?.to) qs.set('to', params.to);
    const query = qs.toString() ? `?${qs}` : '';
    return get<{ traces: TraceRecord[]; total: number }>(`/observability/traces${query}`);
  },
  chatStream: (
    message: string,
    context: Record<string, unknown>,
    onEvent: (type: string, data: unknown) => void,
    onError: (err: Error) => void,
  ): AbortController => {
    const controller = new AbortController();
    fetch(`${BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, context }),
      signal: controller.signal,
    }).then(async (response) => {
      const reader = response.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        let eventType = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              onEvent(eventType, data);
            } catch { /* skip unparseable */ }
          }
        }
      }
    }).catch(onError);
    return controller;
  },
};
