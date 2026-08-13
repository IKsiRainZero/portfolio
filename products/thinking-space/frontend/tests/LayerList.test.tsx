import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LayerList from '../src/components/ChainEditor/LayerList';

const layers = [
  { id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '基本单位', entry_count: 0 },
  { id: 'l2', dimension_id: 'd1', name: '组织', level: 1, description: '', entry_count: 0 },
];

describe('LayerList', () => {
  const base = { layers, onCreate: vi.fn(), onRename: vi.fn(), onUpdateDesc: vi.fn(), onDelete: vi.fn(), onReorder: vi.fn() };

  it('renders layers in order', () => {
    render(<LayerList {...base} />);
    const inputs = screen.getAllByDisplayValue(/细胞|组织/);
    expect(inputs[0]).toHaveValue('细胞');
  });

  it('creates a layer', () => {
    const onCreate = vi.fn();
    render(<LayerList {...base} onCreate={onCreate} />);
    fireEvent.change(screen.getByPlaceholderText('新层级名称'), { target: { value: '器官' } });
    fireEvent.click(screen.getByText('新增层级'));
    expect(onCreate).toHaveBeenCalledWith('器官');
  });

  it('deletes a layer', () => {
    const onDelete = vi.fn();
    render(<LayerList {...base} onDelete={onDelete} />);
    fireEvent.click(screen.getAllByText('×')[0]);
    expect(onDelete).toHaveBeenCalledWith('l1');
  });
});
