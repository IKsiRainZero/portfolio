import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as client from '../src/api/client';

beforeEach(() => {
  global.fetch = vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({ ok: true }),
  })) as unknown as typeof fetch;
});

describe('client geometry + chain endpoints', () => {
  it('updateGeometry calls PUT /geometry', async () => {
    await client.updateGeometry('e1', { x: 10, y: 20 });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/entries/e1/geometry',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('reorderLayers posts layer_ids', async () => {
    await client.reorderLayers('d1', ['b', 'a']);
    const call = (global.fetch as any).mock.calls[0];
    expect(call[0]).toBe('/api/dimensions/d1/layers/reorder');
    expect(JSON.parse(call[1].body)).toEqual({ layer_ids: ['b', 'a'] });
  });

  it('createLayerLink posts to /layer-links', async () => {
    await client.createLayerLink({ source_layer_id: 's', target_layer_id: 't' });
    expect((global.fetch as any).mock.calls[0][0]).toBe('/api/layer-links');
  });
});
