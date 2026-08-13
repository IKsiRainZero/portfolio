import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as client from '../src/api/client';
import App from '../src/App';

const dim = { id: 'd1', name: '物质层次', description: '', sort_order: 0,
  layers: [{ id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 }] };

beforeEach(() => {
  vi.spyOn(client, 'fetchDimensions').mockResolvedValue([dim] as any);
  vi.spyOn(client, 'fetchEntries').mockResolvedValue([] as any);
  vi.spyOn(client, 'fetchLayerLinks').mockResolvedValue([] as any);
});

describe('App', () => {
  it('loads and renders canvas surface', async () => {
    const { container } = render(<App />);
    await waitFor(() => expect(container.querySelector('[data-canvas-surface]')).toBeTruthy());
  });
});
