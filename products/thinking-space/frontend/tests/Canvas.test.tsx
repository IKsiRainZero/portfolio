import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Canvas from '../src/components/Canvas/Canvas';

const base = {
  entries: [], layers: [], crossLinks: [], selectedId: null,
  onSelect: () => {}, onDragEnd: () => {}, onResizeEnd: () => {},
  onCreateAt: vi.fn(), onSave: () => {}, onDelete: () => {},
  onConnect: () => {}, onDeleteCrossLink: () => {}, onConfirm: () => {}, onIgnore: () => {},
};

describe('Canvas', () => {
  it('renders a card for each entry', () => {
    const entries = [{ id: '1', title: '细胞', content: '', entry_type: 'known', layer_id: null,
      dimension_id: 'd1', source_type: 'manual', source_link: '', status: 'confirmed', tags: [], tag_ids: [],
      confidence: 100, x: 10, y: 10, width: 200, height: 120, z_depth: 0, created_at: '', updated_at: '' }] as any;
    render(<Canvas {...base} entries={entries} />);
    expect(screen.getByText('细胞')).toBeInTheDocument();
  });

  it('double click on empty space creates a card at canvas coords', () => {
    const onCreateAt = vi.fn();
    const { container } = render(<Canvas {...base} onCreateAt={onCreateAt} />);
    const surface = container.querySelector('[data-canvas-surface]')!;
    fireEvent.doubleClick(surface, { clientX: 100, clientY: 100 });
    expect(onCreateAt).toHaveBeenCalled();
  });
});
