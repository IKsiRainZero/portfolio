import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChainList from '../src/components/ChainEditor/ChainList';

const dims = [
  { id: 'd1', name: '物质层次', description: '', sort_order: 0, layers: [] },
  { id: 'd2', name: '时间维度', description: '', sort_order: 1, layers: [] },
] as any;

describe('ChainList', () => {
  const base = { dimensions: dims, activeId: 'd1', onSelect: vi.fn(), onCreate: vi.fn(), onRename: vi.fn(), onDelete: vi.fn() };

  it('lists all chains', () => {
    render(<ChainList {...base} />);
    expect(screen.getByDisplayValue('物质层次')).toBeInTheDocument();
    expect(screen.getByDisplayValue('时间维度')).toBeInTheDocument();
  });

  it('selects a chain on click', () => {
    const onSelect = vi.fn();
    render(<ChainList {...base} onSelect={onSelect} />);
    fireEvent.click(screen.getByDisplayValue('时间维度').parentElement!);
    expect(onSelect).toHaveBeenCalledWith('d2');
  });

  it('creates a new chain', () => {
    const onCreate = vi.fn();
    render(<ChainList {...base} onCreate={onCreate} />);
    fireEvent.change(screen.getByPlaceholderText('新链名称'), { target: { value: '空间维度' } });
    fireEvent.click(screen.getByText('新建链'));
    expect(onCreate).toHaveBeenCalledWith('空间维度');
  });
});
