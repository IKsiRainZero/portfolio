import type { Dimension, Entry, DiagnosisEvent, LayerLink } from '../types';

const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}

export function fetchDimensions(): Promise<Dimension[]> {
  return request<Dimension[]>('/dimensions');
}

export function fetchDimension(id: string): Promise<Dimension> {
  return request<Dimension>(`/dimensions/${id}`);
}

export function fetchEntries(params: Record<string, string> = {}): Promise<Entry[]> {
  const qs = new URLSearchParams(params).toString();
  return request<Entry[]>(`/entries${qs ? `?${qs}` : ''}`);
}

export function createEntry(data: Partial<Entry>): Promise<Entry> {
  return request<Entry>('/entries', { method: 'POST', body: JSON.stringify(data) });
}

export function updateEntry(id: string, data: Partial<Entry>): Promise<Entry> {
  return request<Entry>(`/entries/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export function deleteEntry(id: string): Promise<void> {
  return request<void>(`/entries/${id}`, { method: 'DELETE' });
}

export function confirmEntry(id: string): Promise<Entry> {
  return request<Entry>(`/entries/${id}/confirm`, { method: 'PUT' });
}

export function ignoreEntry(id: string): Promise<Entry> {
  return request<Entry>(`/entries/${id}/ignore`, { method: 'PUT' });
}

export function triggerIndexScan(): Promise<{ scanned: number; new_entries: Entry[] }> {
  return request('/index/scan', { method: 'POST' });
}

export function diagnoseStream(
  question: string,
  dimensionId: string,
  onEvent: (event: DiagnosisEvent) => void,
  onError: (err: Error) => void
): AbortController {
  const controller = new AbortController();
  fetch(`${BASE}/diagnose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, dimension_id: dimensionId }),
    signal: controller.signal,
  })
    .then(async (res) => {
      const reader = res.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          const eventMatch = part.match(/^event: (.+)\ndata: (.+)$/m);
          if (eventMatch) {
            onEvent({ event: eventMatch[1] as DiagnosisEvent['event'], data: JSON.parse(eventMatch[2]) });
          }
        }
      }
    })
    .catch(onError);
  return controller;
}

export interface Geometry { x?: number; y?: number; width?: number; height?: number; z_depth?: number; }

export function updateGeometry(id: string, geo: Geometry): Promise<Entry> {
  return request<Entry>(`/entries/${id}/geometry`, { method: 'PUT', body: JSON.stringify(geo) });
}

export function createDimension(data: { name: string; description?: string }): Promise<Dimension> {
  return request<Dimension>('/dimensions', { method: 'POST', body: JSON.stringify(data) });
}
export function updateDimension(id: string, data: { name?: string; description?: string }): Promise<Dimension> {
  return request<Dimension>(`/dimensions/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}
export function deleteDimension(id: string): Promise<void> {
  return request<void>(`/dimensions/${id}`, { method: 'DELETE' });
}

export function createLayer(dimId: string, data: { name: string; description?: string }): Promise<import('../types').Layer> {
  return request(`/dimensions/${dimId}/layers`, { method: 'POST', body: JSON.stringify(data) });
}
export function updateLayer(id: string, data: { name?: string; description?: string }): Promise<import('../types').Layer> {
  return request(`/layers/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}
export function deleteLayer(id: string): Promise<void> {
  return request<void>(`/layers/${id}`, { method: 'DELETE' });
}
export function reorderLayers(dimId: string, layerIds: string[]): Promise<{ reordered: number }> {
  return request(`/dimensions/${dimId}/layers/reorder`, { method: 'PUT', body: JSON.stringify({ layer_ids: layerIds }) });
}

export function fetchLayerLinks(dimId: string): Promise<LayerLink[]> {
  return request<LayerLink[]>(`/dimensions/${dimId}/layer-links`);
}
export function createLayerLink(data: { source_layer_id: string; target_layer_id: string; relation_type?: string; note?: string }): Promise<LayerLink> {
  return request<LayerLink>('/layer-links', { method: 'POST', body: JSON.stringify(data) });
}
export function deleteLayerLink(id: string): Promise<void> {
  return request<void>(`/layer-links/${id}`, { method: 'DELETE' });
}

export function createCrossLink(data: { source_entry_id: string; target_entry_id: string; relation_type?: string; note?: string }): Promise<{ id: string }> {
  return request('/cross-links', { method: 'POST', body: JSON.stringify(data) });
}
export function deleteCrossLink(id: string): Promise<void> {
  return request<void>(`/cross-links/${id}`, { method: 'DELETE' });
}
