import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CardNode from '../src/components/Canvas/CardNode';

const entry = (over: any = {}) => ({
  id: '1', title: '线粒体', content: 'ATP', entry_type: 'known',
  layer_id: null, dimension_id: 'd1', source_type: 'manual', source_link: '',
  status: 'confirmed', tags: [], tag_ids: [], confidence: 100,
  x: 40, y: 50, width: 200, height: 120, z_depth: 0, created_at: '', updated_at: '', ...over,
});

describe('CardNode', () => {
  it('renders title at its position', () => {
    render(<CardNode entry={entry()} scale={1} selected={false}
      onSelect={() => {}} onDragEnd={() => {}} onResizeEnd={() => {}} onStartConnect={() => {}} />);
    expect(screen.getByText('线粒体')).toBeInTheDocument();
  });

  it('calls onSelect on click', () => {
    const onSelect = vi.fn();
    render(<CardNode entry={entry()} scale={1} selected={false}
      onSelect={onSelect} onDragEnd={() => {}} onResizeEnd={() => {}} onStartConnect={() => {}} />);
    fireEvent.mouseDown(screen.getByText('线粒体'));
    fireEvent.mouseUp(screen.getByText('线粒体'));
    expect(onSelect).toHaveBeenCalledWith('1');
  });

  it('calls onDragEnd exactly once on drag release with final coords', () => {
    const onDragEnd = vi.fn();
    render(<CardNode entry={entry()} scale={1} selected={false}
      onSelect={() => {}} onDragEnd={onDragEnd} onResizeEnd={() => {}} onStartConnect={() => {}} />);
    fireEvent.mouseDown(screen.getByText('线粒体'), { clientX: 100, clientY: 100 });
    fireEvent.mouseMove(window, { clientX: 130, clientY: 140 });
    fireEvent.mouseUp(window);
    expect(onDragEnd).toHaveBeenCalledTimes(1);
    expect(onDragEnd).toHaveBeenCalledWith('1', 70, 90);
  });

  it('collapses content when width below threshold', () => {
    render(<CardNode entry={entry({ width: 100 })} scale={1} selected={false}
      onSelect={() => {}} onDragEnd={() => {}} onResizeEnd={() => {}} onStartConnect={() => {}} />);
    expect(screen.queryByText('ATP')).not.toBeInTheDocument();
    expect(screen.getByText('线粒体')).toBeInTheDocument();
  });
});
