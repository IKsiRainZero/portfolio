import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Dock from '../src/components/Dock/Dock';

describe('Dock', () => {
  const base = { onAdd: vi.fn(), onScan: vi.fn(), onToggleView: vi.fn(), view: 'canvas' as const };

  it('shows actions on hover', () => {
    const { container } = render(<Dock {...base} />);
    fireEvent.mouseEnter(container.firstChild as Element);
    expect(screen.getByTitle('添加条目')).toBeInTheDocument();
    expect(screen.getByTitle('扫描知识库')).toBeInTheDocument();
  });

  it('toggles view', () => {
    const onToggleView = vi.fn();
    const { container } = render(<Dock {...base} onToggleView={onToggleView} />);
    fireEvent.mouseEnter(container.firstChild as Element);
    fireEvent.click(screen.getByTitle('切换视图'));
    expect(onToggleView).toHaveBeenCalled();
  });
});
